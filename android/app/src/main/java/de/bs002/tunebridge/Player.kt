package de.bs002.tunebridge

import android.media.AudioAttributes
import android.media.MediaPlayer
import de.bs002.tunebridge.data.Track
import de.bs002.tunebridge.net.Previews
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Hörproben-Player (30 s, direkt vom Anbieter gestreamt) – erst nach Tippen, nichts wird gespeichert.
 * Spielt einzelne Songs („Reinhören“) oder eine Warteschlange (Playlist/Verlauf) mit Vor/Zurück; Songs ohne
 * Hörprobe werden übersprungen. Komplette Songs gibt es nur in deiner Musik-App (Knopf „Öffnen“).
 */
object Player {
    data class State(
        val queue: List<Track> = emptyList(),
        val index: Int = -1,
        val playing: Boolean = false,
        val loading: Boolean = false,
        val title: String? = null,          // Herkunft, z. B. Name der Playlist
    ) {
        val current: Track? get() = queue.getOrNull(index)
        val hasPrev: Boolean get() = (0 until index.coerceAtLeast(0)).any { queue[it].playable }
        val hasNext: Boolean get() = (index + 1 until queue.size).any { queue[it].playable }
    }

    private var mp: MediaPlayer? = null
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var job: Job? = null
    private var misses = 0
    @Volatile private var prepared = false
    private val _state = MutableStateFlow(State())
    val state: StateFlow<State> = _state.asStateFlow()

    /** URL der gerade laufenden Hörprobe (für die „Reinhören“-Knöpfe). */
    private val _playing = MutableStateFlow<String?>(null)
    val playing: StateFlow<String?> = _playing.asStateFlow()

    /** Einzelner Song: an/aus. */
    fun toggle(url: String, track: Track? = null) {
        if (_playing.value == url) return stop()
        val t = track ?: Track(title = "Hörprobe", previewUrl = url)
        play(listOf(t), 0, null)
    }

    /** Warteschlange ab [start] abspielen (Songs ohne Hörprobe werden übersprungen). */
    fun play(tracks: List<Track>, start: Int = 0, title: String? = null) {
        val i = (start until tracks.size).firstOrNull { tracks[it].playable } ?: return
        _state.value = State(tracks, i, playing = false, loading = true, title = title)
        load(i)
    }

    fun playPause() {
        val m = mp ?: return _state.value.let { if (it.current != null) load(it.index) }
        val s = _state.value
        if (s.loading) return
        if (m.isPlaying) { m.pause(); _state.value = s.copy(playing = false) }
        else { m.start(); _state.value = s.copy(playing = true) }
    }

    fun next() {
        val s = _state.value
        val i = (s.index + 1 until s.queue.size).firstOrNull { s.queue[it].playable } ?: return stop()
        load(i)
    }

    fun prev() {
        val s = _state.value
        // Wie überall: nach den ersten Sekunden zurück an den Anfang, sonst zum vorigen Song
        if (prepared && (mp?.currentPosition ?: 0) > 3000) { mp?.seekTo(0); return }
        val i = (s.index - 1 downTo 0).firstOrNull { s.queue[it].playable } ?: run { if (prepared) mp?.seekTo(0); return }
        load(i)
    }

    /** Fortschritt der laufenden Hörprobe (0…1) für die Leiste im Mini-Player. */
    fun progress(): Float = if (!prepared) 0f else mp?.runCatching { if (duration > 0) currentPosition.toFloat() / duration else 0f }?.getOrNull() ?: 0f

    fun stop() {
        job?.cancel()
        release()
        _playing.value = null
        _state.value = State()
    }

    private fun release() {
        prepared = false
        mp?.runCatching { stop(); release() }
        mp = null
    }

    private fun load(i: Int) {
        release()
        job?.cancel()
        val s = _state.value
        val t = s.queue.getOrNull(i) ?: return stop()
        _state.value = s.copy(index = i, playing = false, loading = true)
        _playing.value = t.previewUrl
        // Abgelaufene Deezer-Adressen erst frisch holen (im Hintergrund), dann streamen
        job = scope.launch {
            val url = withContext(Dispatchers.IO) { Previews.resolve(t) }
            if (url == null) {
                // Keine Hörprobe zu finden: nächster Song – nach 5 Fehlschlägen in Folge aufhören
                if (++misses >= 5) { misses = 0; stop() } else next()
                return@launch
            }
            start(url)
        }
    }

    private fun start(url: String) {
        mp = MediaPlayer().apply {
            setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
            setOnPreparedListener {
                if (mp !== it) return@setOnPreparedListener
                misses = 0
                prepared = true
                it.start(); _state.value = _state.value.copy(playing = true, loading = false)
            }
            setOnCompletionListener { if (mp === it) next() }
            setOnErrorListener { p, _, _ -> if (mp === p) { if (++misses >= 5) { misses = 0; stop() } else next() }; true }
            runCatching { setDataSource(url); prepareAsync() }.onFailure { next() }
        }
    }
}

/** Hat (oder bekommt bei Deezer) eine Hörprobe. */
val Track.playable: Boolean get() = previewUrl != null || ids["deezer"] != null || isrc != null
