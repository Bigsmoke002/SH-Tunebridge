package de.bs002.tunebridge.audio

import android.annotation.SuppressLint
import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFormat
import android.media.AudioPlaybackCaptureConfiguration
import android.media.projection.MediaProjection
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.withContext
import kotlin.coroutines.coroutineContext
import kotlin.math.log10
import kotlin.math.max
import kotlin.math.sqrt

/**
 * Nimmt über das Mikrofon auf – nur im Arbeitsspeicher, nie als Datei. Liefert 16-kHz-Mono-PCM
 * für den Fingerabdruck und unterwegs Pegel + grobes Spektrum für die Anzeige.
 */
class Recorder(private val context: Context) {

    class Frame(val levelDb: Float, val bands: FloatArray, val progress: Float)

    @SuppressLint("MissingPermission")   // Berechtigung prüft der Aufrufer, bevor er aufnimmt
    suspend fun record(seconds: Float, projection: MediaProjection? = null, externalMic: Boolean = false, onFrame: (Frame) -> Unit): ShortArray = withContext(Dispatchers.IO) {
        val rate = ShazamSignature.RATE
        val minBuf = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = if (projection == null) AudioRecord(source(), rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, max(minBuf, rate))
        else {
            // Handy-Ton: nur Medien-, Spiele- und unbekannte Wiedergabe – Telefonate und Sprachanrufe gibt Android nie heraus.
            val cfg = AudioPlaybackCaptureConfiguration.Builder(projection)
                .addMatchingUsage(AudioAttributes.USAGE_MEDIA)
                .addMatchingUsage(AudioAttributes.USAGE_GAME)
                .addMatchingUsage(AudioAttributes.USAGE_UNKNOWN)
                .build()
            AudioRecord.Builder()
                .setAudioFormat(AudioFormat.Builder().setEncoding(AudioFormat.ENCODING_PCM_16BIT).setSampleRate(rate)
                    .setChannelMask(AudioFormat.CHANNEL_IN_MONO).build())
                .setBufferSizeInBytes(max(minBuf, rate * 2))
                .setAudioPlaybackCaptureConfig(cfg)
                .build()
        }
        check(rec.state == AudioRecord.STATE_INITIALIZED) {
            if (projection == null) "Mikrofon ist belegt oder nicht verfügbar" else "Handy-Ton lässt sich gerade nicht abgreifen"
        }
        // USB-Soundkarte/Headset mit Eingang: Android nähme sonst deren (oft stummen) Eingang statt des Handy-Mikrofons
        if (projection == null && !externalMic) AudioRoutes.builtinMic(context)?.let { rec.setPreferredDevice(it) }
        val total = (seconds * rate).toInt()
        val out = ShortArray(total)
        val chunk = ShortArray(512)
        val fft = RealFft(512)
        val win = FloatArray(512)
        val power = DoubleArray(257)
        var n = 0
        try {
            rec.startRecording()
            while (n < total) {
                coroutineContext.ensureActive()
                val got = rec.read(chunk, 0, minOf(chunk.size, total - n))
                if (got <= 0) continue
                System.arraycopy(chunk, 0, out, n, got)
                n += got
                onFrame(analyse(chunk, got, fft, win, power, n.toFloat() / total))
            }
        } finally {
            runCatching { rec.stop() }
            rec.release()
        }
        out
    }

    /** Unbearbeitete Quelle, wenn das Gerät sie anbietet – Rauschunterdrückung verfälscht Musik. */
    private fun source(): Int {
        val am = context.getSystemService(AudioManager::class.java)
        val raw = am?.getProperty(AudioManager.PROPERTY_SUPPORT_AUDIO_SOURCE_UNPROCESSED) == "true"
        return if (raw) MediaRecorder.AudioSource.UNPROCESSED else MediaRecorder.AudioSource.VOICE_RECOGNITION
    }

    private fun analyse(buf: ShortArray, len: Int, fft: RealFft, win: FloatArray, power: DoubleArray, progress: Float): Frame {
        var sum = 0.0
        for (i in 0 until len) sum += buf[i].toDouble() * buf[i]
        val rms = sqrt(sum / max(1, len)) / 32768.0
        val db = (20 * log10(max(rms, 1e-6))).toFloat()
        for (i in 0 until 512) win[i] = if (i < len) buf[i].toFloat() else 0f
        fft.power(win, power)
        // 24 Bänder, logarithmisch von ~60 Hz bis 8 kHz – wie die Anzeige am Desktop
        val bands = FloatArray(BANDS)
        for (b in 0 until BANDS) {
            val lo = edge(b); val hi = max(lo + 1, edge(b + 1))
            var s = 0.0
            for (k in lo until hi) s += power[k]
            val v = 10 * log10(s / (hi - lo) + 1e-9) - 60
            bands[b] = ((v + 30) / 60).toFloat().coerceIn(0f, 1f)
        }
        return Frame(db, bands, progress)
    }

    private fun edge(b: Int): Int {
        val f = 60.0 * Math.pow(8000.0 / 60.0, b.toDouble() / BANDS)
        return (f / 8000.0 * 256).toInt().coerceIn(1, 256)
    }

    companion object {
        const val BANDS = 24
        const val SILENT_DB = -62f
    }
}
