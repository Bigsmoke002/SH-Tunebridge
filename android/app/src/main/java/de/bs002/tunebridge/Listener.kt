package de.bs002.tunebridge

import android.content.Context
import de.bs002.tunebridge.audio.CaptureService
import de.bs002.tunebridge.audio.Recorder
import de.bs002.tunebridge.audio.ShazamSignature
import de.bs002.tunebridge.data.Recognition
import de.bs002.tunebridge.data.Repository
import de.bs002.tunebridge.net.Shazam
import de.bs002.tunebridge.sync.PcSync
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject
import java.io.IOException
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.sqrt

/** Ein Erkennungsvorgang: aufnehmen -> Fingerabdruck -> Shazam -> Verlauf (-> PC). Eine Instanz für die ganze App. */
class Listener(context: Context, private val repo: Repository, private val sync: PcSync) {
    sealed interface State {
        data object Idle : State
        data class Recording(val progress: Float, val bands: FloatArray, val levelDb: Float) : State
        data object Analysing : State
        data class Found(val rec: Recognition, val unsure: Boolean) : State
        data class NotFound(val levelDb: Float) : State
        data class Silent(val levelDb: Float) : State
        data class Limited(val waitSeconds: Int, val message: String) : State
        data class Failed(val message: String) : State
    }

    private val appContext = context.applicationContext
    private val recorder = Recorder(context.applicationContext)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private val _state = MutableStateFlow<State>(State.Idle)
    val state: StateFlow<State> = _state.asStateFlow()
    private var job: Job? = null
    /** Kam die letzte Aufnahme vom Handy-Ton? (für passende Hinweise bei „kein Ton“) */
    var lastSystem = false
        private set

    val busy: Boolean get() = _state.value is State.Recording || _state.value is State.Analysing

    /** [system] = Handy-Ton statt Mikrofon (braucht eine aktive Freigabe, siehe CaptureService). */
    fun start(seconds: Int = repo.settings.value.seconds, system: Boolean = false) {
        if (job?.isActive == true) return
        lastSystem = system
        job = scope.launch {
            try {
                val projection = if (system) {
                    CaptureService.used()
                    CaptureService.projection.value ?: throw IllegalStateException("Freigabe für den Handy-Ton ist abgelaufen – bitte nochmal tippen")
                } else null
                _state.value = State.Recording(0f, FloatArray(Recorder.BANDS), -90f)
                val pcm = recorder.record(seconds.toFloat(), projection) { f ->
                    _state.value = State.Recording(f.progress, f.bands, f.levelDb)
                }
                val level = withContext(Dispatchers.Default) { levelDb(pcm) }
                if (level <= Recorder.SILENT_DB) {
                    _state.value = State.Silent(level)
                    return@launch
                }
                _state.value = State.Analysing
                val sig = withContext(Dispatchers.Default) { ShazamSignature.from(ShazamSignature.middle(pcm)) }
                val hit = Shazam.recognize(sig)
                if (hit == null) {
                    _state.value = State.NotFound(level)
                    return@launch
                }
                val unsure = (hit.skew ?: 0.0) > TRUSTED_SKEW
                val extra = buildJsonObject {
                    putJsonArray("engines") { add(JsonPrimitive("shazam")) }
                    put("agreement", 1)
                    putJsonObject("links") { hit.links.forEach { (k, v) -> put(k, v) } }
                    hit.label?.let { put("label", it) }
                    hit.year?.let { put("year", it) }
                    hit.shazamKey?.let { put("shazam_key", it) }
                    if (hit.genres.isNotEmpty()) put("shazam_genre", hit.genres.first())
                    hit.skew?.let { put("skew", it) }
                    put("level_db", level.toDouble())
                    put("device", "handy")
                    if (unsure) put("unsure", true)
                    if (system) put("handy_ton", true)
                }
                val rec = repo.add(hit.track, if (system) "handy-ton" else "handy-mikrofon", extra)
                _state.value = State.Found(rec, unsure)
                de.bs002.tunebridge.quick.ListenWidget.refresh(appContext)
                autoSync()
            } catch (e: CancellationException) {
                _state.value = State.Idle
                throw e
            } catch (e: Shazam.Busy) {
                _state.value = State.Limited(e.waitSeconds, e.message ?: "Shazam macht eine Pause")
            } catch (e: IOException) {
                _state.value = State.Failed("Keine Verbindung zu Shazam – Internet prüfen")
            } catch (e: Exception) {
                _state.value = State.Failed(e.message ?: "Unbekannter Fehler")
            }
        }
    }

    fun cancel() {
        job?.cancel()
        _state.value = State.Idle
    }

    fun reset() {
        if (!busy) _state.value = State.Idle
    }

    /** Nach einem Treffer bzw. beim Öffnen still mit den gekoppelten PCs abgleichen – nur mit denen, in deren Netz
     *  das Handy gerade ist. Fehler stören hier nicht (stehen beim PC unter „Mehr“). */
    fun autoSync() {
        val s = repo.settings.value
        if (s.pcs.isEmpty() || !s.autoSync) return
        scope.launch { runCatching { sync.syncAll() } }
    }

    private fun levelDb(pcm: ShortArray): Float {
        var sum = 0.0
        for (v in pcm) sum += v.toDouble() * v
        return (20 * log10(max(sqrt(sum / max(1, pcm.size)) / 32768.0, 1e-6))).toFloat()
    }

    companion object {
        const val TRUSTED_SKEW = 0.005     // wie am Desktop (variants.TRUSTED_SKEW)
    }
}
