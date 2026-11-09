package de.bs002.tunebridge.audio

import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/**
 * Reelle FFT fester Länge (Zweierpotenz) über eine komplexe Radix-2-FFT halber Länge.
 * Vorberechnete Drehfaktoren, keine Allokation pro Aufruf – läuft für jeden 128er-Block der Aufnahme.
 */
internal class RealFft(private val n: Int) {
    private val half = n / 2
    private val re = DoubleArray(half)
    private val im = DoubleArray(half)
    private val cosT = DoubleArray(half) { cos(-2 * PI * it / half) }
    private val sinT = DoubleArray(half) { sin(-2 * PI * it / half) }
    private val cosN = DoubleArray(half) { cos(-2 * PI * it / n) }
    private val sinN = DoubleArray(half) { sin(-2 * PI * it / n) }
    private val rev = IntArray(half).also { r ->
        val bits = Integer.numberOfTrailingZeros(half)
        for (i in 0 until half) r[i] = Integer.reverse(i) ushr (32 - bits)
    }

    init {
        require(n >= 4 && n and (n - 1) == 0) { "Länge muss Zweierpotenz sein" }
    }

    /** Leistung |X[k]|² für k = 0..n/2 in [out] (Länge n/2 + 1). */
    fun power(input: FloatArray, out: DoubleArray) {
        for (i in 0 until half) {
            val j = rev[i]
            re[j] = input[2 * i].toDouble()
            im[j] = input[2 * i + 1].toDouble()
        }
        var size = 2
        while (size <= half) {
            val step = half / size
            val h = size / 2
            var start = 0
            while (start < half) {
                var k = 0
                for (j in start until start + h) {
                    val wr = cosT[k]; val wi = sinT[k]
                    val l = j + h
                    val tr = wr * re[l] - wi * im[l]
                    val ti = wr * im[l] + wi * re[l]
                    re[l] = re[j] - tr; im[l] = im[j] - ti
                    re[j] += tr; im[j] += ti
                    k += step
                }
                start += size
            }
            size *= 2
        }
        // Spektrum des reellen Signals aus der halben komplexen FFT zurückgewinnen
        out[0] = (re[0] + im[0]).let { it * it }
        out[half] = (re[0] - im[0]).let { it * it }
        for (k in 1 until half) {
            val ar = re[k]; val ai = im[k]
            val br = re[half - k]; val bi = -im[half - k]
            val er = 0.5 * (ar + br); val ei = 0.5 * (ai + bi)
            val orr = 0.5 * (ai - bi); val oi = -0.5 * (ar - br)
            val xr = er + cosN[k] * orr - sinN[k] * oi
            val xi = ei + cosN[k] * oi + sinN[k] * orr
            out[k] = xr * xr + xi * xi
        }
    }
}
