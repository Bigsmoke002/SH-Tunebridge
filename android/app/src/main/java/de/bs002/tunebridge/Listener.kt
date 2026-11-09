package de.bs002.tunebridge

import android.content.Context
import de.bs002.tunebridge.audio.AudioRoutes
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
        data class Silent(val levelDb: Float, val usbOut: Boolean = false, val bitPerfect: Boolean = false) : State
        data class Limited(val waitSeconds: Int, val message: String) : State
        data class Failed(val message: String) : State
        /** Kein Internet: Fingerabdruck gemerkt, Shazam wird später gefragt. */
        data class Queued(val count: Int) : State
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
    /** Für Dauer-Erkennen: einen Durchgang starten und auf das Ergebnis warten. */
    suspend fun runOnce(seconds: Int, system: Boolean): State {
        job?.join()
        start(seconds, system, auto = true)
        job?.join()
        return _state.value
    }

    /** [auto] = Dauer-Erkennen: derselbe Song kurz hintereinander landet nur einmal im Verlauf. */
    fun start(seconds: Int = repo.settings.value.seconds, system: Boolean = false, auto: Boolean = false) {
        if (job?.isActive == true) return
        lastSystem = system
        job = scope.launch {
            try {
                val projection = if (system) {
                    CaptureService.used()
                    CaptureService.projection.value ?: throw IllegalStateException("Freigabe für den Handy-Ton ist abgelaufen – bitte nochmal tippen")
                } else null
                _state.value = State.Recording(0f, FloatArray(Recorder.BANDS), -90f)
                val pcm = recorder.record(seconds.toFloat(), projection, repo.settings.value.externalMic) { f ->
                    _state.value = State.Recording(f.progress, f.bands, f.levelDb)
                }
                val level = withContext(Dispatchers.Default) { levelDb(pcm) }
                if (level <= Recorder.SILENT_DB) {
                    _state.value = if (system) State.Silent(level, AudioRoutes.usbOutput(appContext) != null, AudioRoutes.bitPerfect(appContext))
                    else State.Silent(level)
                    return@launch
                }
                _state.value = State.Analysing
                val sig = withContext(Dispatchers.Default) { ShazamSignature.from(ShazamSignature.middle(pcm)) }
                val hit = try {
                    Shazam.recognize(sig)
                } catch (e: IOException) {
                    if (e is Shazam.Busy || !repo.settings.value.offlineQueue) throw e
                    // Kein Netz: nur den Fingerabdruck merken (Zahlenwerte, kein Ton) und später nachfragen
                    repo.addPending(Repository.PendingTag(java.util.UUID.randomUUID().toString(), System.currentTimeMillis() / 1000.0,
                        sig.toUri(), sig.durationMs, system, level))
                    _state.value = State.Queued(repo.pending.value.size)
                    return@launch
                }
                if (hit == null) {
                    _state.value = State.NotFound(level)
                    return@launch
                }
                if (auto) {
                    // Läuft der Song noch (oder lief vor Kurzem)? Dann nicht nochmal eintragen.
                    val now = System.currentTimeMillis() / 1000.0
                    val same = repo.history.value.firstOrNull { it.track.key == hit.track.key && now - it.ts < AUTO_DEDUPE_S }
                    if (same != null) { _state.value = State.Found(same, false); return@launch }
                }
                val rec = save(hit, system, level, auto = auto)
                _state.value = State.Found(rec, (hit.skew ?: 0.0) > TRUSTED_SKEW)
                de.bs002.tunebridge.quick.ListenWidget.refresh(appContext)
                autoSync()
                retryPending()          // Netz ist offenbar da: Gemerktes gleich mit erledigen
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

    private fun save(hit: Shazam.Hit, system: Boolean, level: Float, ts: Double? = null, later: Boolean = false, auto: Boolean = false): Recognition {
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
            if (later) put("offline", true)     // offline gemerkt, später erkannt
            if (auto) put("auto", true)         // beim Dauer-Erkennen
        }
        val source = if (system) "handy-ton" else "handy-mikrofon"
        return if (ts != null) repo.add(hit.track, source, extra, ts) else repo.add(hit.track, source, extra)
    }

    private val pendingLock = kotlinx.coroutines.sync.Mutex()
    private val _notices = kotlinx.coroutines.flow.MutableSharedFlow<String>(extraBufferCapacity = 4)
    /** Kurze Meldungen (z. B. „2 Songs nachträglich erkannt“). */
    val notices: kotlinx.coroutines.flow.SharedFlow<String> = _notices

    /** Offline gemerkte Fingerabdrücke jetzt bei Shazam nachfragen – einer nach dem anderen, Abbruch ohne Netz/bei Pause. */
    fun retryPending(manual: Boolean = false) {
        if (repo.pending.value.isEmpty() || pendingLock.isLocked) return
        scope.launch {
            pendingLock.lock()
            var found = 0; var none = 0
            try {
                for (p in repo.pending.value.toList()) {
                    val hit = try { Shazam.recognize(p.uri, p.samplems) } catch (e: IOException) {
                        if (manual) _notices.tryEmit(if (e is Shazam.Busy) "Shazam macht eine Pause – später nochmal" else "Noch kein Internet – bleibt gemerkt")
                        break
                    }
                    repo.removePending(p.id)
                    if (hit == null) none++ else { save(hit, p.system, p.level, p.ts, later = true); found++ }
                }
            } finally { pendingLock.unlock() }
            if (found + none > 0) {
                if (_state.value is State.Queued) _state.value = State.Idle
                val n = found + none
                _notices.tryEmit(when {
                    none == 0 -> if (found == 1) "1 gemerkter Song erkannt" else "$found gemerkte Songs erkannt"
                    found == 0 -> if (n == 1) "Gemerkter Song: Shazam kennt ihn nicht" else "$n gemerkte Songs: Shazam kennt keinen davon"
                    else -> "$found von $n gemerkten Songs erkannt"
                })
                if (found > 0) { de.bs002.tunebridge.quick.ListenWidget.refresh(appContext); autoSync() }
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
        const val AUTO_DEDUPE_S = 20 * 60.0   // Dauer-Erkennen: gleicher Song innerhalb 20 min = derselbe Durchlauf
        const val TRUSTED_SKEW = 0.005     // wie am Desktop (variants.TRUSTED_SKEW)
    }
}
