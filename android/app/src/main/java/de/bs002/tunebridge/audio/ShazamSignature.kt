package de.bs002.tunebridge.audio

import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Base64
import java.util.zip.CRC32
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.ln
import kotlin.math.max

/**
 * Shazam-Fingerabdruck aus 16-kHz-Mono-PCM – eigene Umsetzung des öffentlich dokumentierten Formats
 * (Spektrum-Spitzen in vier Frequenzbändern). Verglichen mit shazamio-core (MIT), das die Desktop-App nutzt.
 *
 * Aus dem Fingerabdruck lässt sich kein Ton zurückgewinnen; nur er verlässt das Gerät.
 */
class ShazamSignature private constructor(
    val sampleRate: Int,
    val sampleCount: Int,
    val bands: Map<Int, List<Peak>>,
) {
    data class Peak(val pass: Int, val magnitude: Int, val bin: Int)

    /** Länge der ausgewerteten Aufnahme in Millisekunden (Feld `samplems` der Anfrage). */
    val durationMs: Int get() = (sampleCount.toFloat() / sampleRate * 1000f).toInt()

    val peakCount: Int get() = bands.values.sumOf { it.size }

    fun toUri(): String = URI_PREFIX + Base64.getEncoder().encodeToString(encode())

    fun encode(): ByteArray {
        val body = ByteArrayOutputStream()
        for (band in bands.keys.sorted()) {
            val peaks = ByteArrayOutputStream()
            var last = 0
            for (p in bands.getValue(band)) {
                if (p.pass - last >= 255) {
                    peaks.write(0xff)
                    peaks.write(le32(p.pass))
                    last = p.pass
                }
                peaks.write(p.pass - last)
                peaks.write(le16(p.magnitude))
                peaks.write(le16(p.bin))
                last = p.pass
            }
            val bytes = peaks.toByteArray()
            body.write(le32(0x60030040 + band))
            body.write(le32(bytes.size))
            body.write(bytes)
            repeat((4 - bytes.size % 4) % 4) { body.write(0) }
        }
        val content = body.toByteArray()
        val buf = ByteBuffer.allocate(HEADER + 8 + content.size).order(ByteOrder.LITTLE_ENDIAN)
        val sizeMinusHeader = 8 + content.size
        buf.putInt(0xcafe2580.toInt())
        buf.putInt(0)                                   // CRC32 – unten
        buf.putInt(sizeMinusHeader)
        buf.putInt(0x94119c00.toInt())
        buf.putInt(0); buf.putInt(0); buf.putInt(0)
        buf.putInt(rateId(sampleRate) shl 27)
        buf.putInt(0); buf.putInt(0)
        buf.putInt(sampleCount + (sampleRate * 0.24f).toInt())
        buf.putInt((15 shl 19) + 0x40000)
        buf.putInt(0x40000000)
        buf.putInt(sizeMinusHeader)
        buf.put(content)
        val out = buf.array()
        val crc = CRC32().apply { update(out, 8, out.size - 8) }.value.toInt()
        ByteBuffer.wrap(out, 4, 4).order(ByteOrder.LITTLE_ENDIAN).putInt(crc)
        return out
    }

    companion object {
        const val RATE = 16_000
        const val WINDOW_SECONDS = 10                  // Shazam-Clients senden 10 s; ab 12 s gibt es keine Treffer
        private const val URI_PREFIX = "data:audio/vnd.shazam.sig;base64,"
        private const val HEADER = 48
        private const val FFT = 2048
        private const val BINS = FFT / 2 + 1
        private val HANN = FloatArray(FFT) { (0.5 * (1 - cos(2 * PI * (it + 1) / (FFT + 1)))).toFloat() }
        private val NEIGHBOURS = intArrayOf(-10, -7, -4, -3, 1, 2, 5, 8)
        private val OTHER_FFTS = intArrayOf(-53, -45, 165, 172, 179, 186, 193, 200, 214, 221, 228, 235, 242, 249)

        private fun rateId(rate: Int) = when (rate) {
            8000 -> 1; 11025 -> 2; 16000 -> 3; 32000 -> 4; 44100 -> 5; 48000 -> 6
            else -> error("Abtastrate $rate wird nicht unterstützt")
        }

        private fun le32(v: Int) = ByteBuffer.allocate(4).order(ByteOrder.LITTLE_ENDIAN).putInt(v).array()
        private fun le16(v: Int) = ByteBuffer.allocate(2).order(ByteOrder.LITTLE_ENDIAN).putShort(v.toShort()).array()

        /** Die mittleren [WINDOW_SECONDS] Sekunden – wie die Desktop-App (shazamio). */
        fun middle(pcm: ShortArray, seconds: Int = WINDOW_SECONDS): ShortArray {
            val n = seconds * RATE
            if (pcm.size <= n) return pcm
            val start = pcm.size / 2 - n / 2
            return pcm.copyOfRange(start, start + n)
        }

        fun from(pcm16k: ShortArray): ShazamSignature = Builder(pcm16k.size).run {
            var i = 0
            while (i + 128 <= pcm16k.size) {
                feed(pcm16k, i)
                i += 128
            }
            ShazamSignature(RATE, pcm16k.size, bands)
        }
    }

    private class Builder(@Suppress("unused") val total: Int) {
        val bands = sortedMapOf<Int, MutableList<Peak>>()
        private val ring = ShortArray(FFT)
        private var ringPos = 0
        private val windowed = FloatArray(FFT)
        private val fft = RealFft(FFT)
        private val power = DoubleArray(BINS)
        private val ffts = Array(256) { FloatArray(BINS) }
        private val spread = Array(256) { FloatArray(BINS) }
        private var fftPos = 0
        private var spreadPos = 0
        private var spreadDone = 0

        fun feed(src: ShortArray, off: Int) {
            System.arraycopy(src, off, ring, ringPos, 128)
            ringPos = (ringPos + 128) and (FFT - 1)
            for (k in 0 until FFT) windowed[k] = ring[(k + ringPos) and (FFT - 1)] * HANN[k]
            fft.power(windowed, power)
            val dst = ffts[fftPos]
            for (k in 0 until BINS) dst[k] = max((power[k] / (1 shl 17)).toFloat(), 1e-10f)
            fftPos = (fftPos + 1) and 255
            spreadPeaks()
            spreadDone++
            if (spreadDone >= 46) recognisePeaks()
        }

        private fun spreadPeaks() {
            val src = ffts[(fftPos - 1) and 255]
            val cur = spread[spreadPos]
            System.arraycopy(src, 0, cur, 0, BINS)
            for (p in 0..1022) cur[p] = max(cur[p], max(cur[p + 1], cur[p + 2]))
            for (back in intArrayOf(1, 3, 6)) {
                val former = spread[(spreadPos - back) and 255]
                for (p in 0 until BINS) former[p] = max(former[p], cur[p])
            }
            spreadPos = (spreadPos + 1) and 255
        }

        private fun mag(v: Float) = max(ln(v.toDouble()).toFloat(), 1f / 64f) * 1477.3f + 6144f

        private fun recognisePeaks() {
            val f46 = ffts[(fftPos - 46) and 255]
            val s49 = spread[(spreadPos - 49) and 255]
            for (bin in 10..1014) {
                val v = f46[bin]
                if (v < 1f / 64f || v < s49[bin - 1]) continue
                var near = 0f
                for (o in NEIGHBOURS) near = max(near, s49[bin + o])
                if (v <= near) continue
                var other = near
                for (o in OTHER_FFTS) other = max(other, spread[(spreadPos + o) and 255][bin - 1])
                if (v <= other) continue

                val m = mag(v)
                val before = mag(f46[bin - 1])
                val after = mag(f46[bin + 1])
                val var1 = m * 2 - before - after
                val var2 = (after - before) * 32 / var1
                val corrected = (bin * 64 + var2.toInt()) and 0xffff
                val hz = corrected * (16000f / 2f / 1024f / 64f)
                val band = when (hz.toInt()) {
                    in 250..519 -> 0
                    in 520..1449 -> 1
                    in 1450..3499 -> 2
                    in 3500..5500 -> 3
                    else -> continue
                }
                bands.getOrPut(band) { mutableListOf() } += Peak(spreadDone - 46, m.toInt() and 0xffff, corrected)
            }
        }
    }
}
