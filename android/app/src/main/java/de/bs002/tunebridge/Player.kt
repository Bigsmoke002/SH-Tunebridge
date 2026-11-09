package de.bs002.tunebridge

import android.media.AudioAttributes
import android.media.MediaPlayer
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/** Hörproben (30 s, vom Anbieter gestreamt) – erst nach Tippen, nichts wird gespeichert. */
object Player {
    private var mp: MediaPlayer? = null
    private val _playing = MutableStateFlow<String?>(null)
    val playing: StateFlow<String?> = _playing.asStateFlow()

    fun toggle(url: String) {
        if (_playing.value == url) return stop()
        stop()
        _playing.value = url
        mp = MediaPlayer().apply {
            setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).setContentType(AudioAttributes.CONTENT_TYPE_MUSIC).build())
            setOnPreparedListener { it.start() }
            setOnCompletionListener { stop() }
            setOnErrorListener { _, _, _ -> stop(); true }
            runCatching { setDataSource(url); prepareAsync() }.onFailure { stop() }
        }
    }

    fun stop() {
        mp?.runCatching { stop(); release() }
        mp = null
        _playing.value = null
    }
}
