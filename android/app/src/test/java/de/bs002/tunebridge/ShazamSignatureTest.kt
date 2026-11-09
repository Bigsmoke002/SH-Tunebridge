package de.bs002.tunebridge

import de.bs002.tunebridge.audio.ShazamSignature
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test
import java.nio.ByteBuffer
import java.nio.ByteOrder
import java.util.Base64
import java.util.zip.CRC32

/** Vergleich mit der Referenz aus shazamio-core (Desktop): gleiche Datei -> (nahezu) gleiche Spitzen. */
class ShazamSignatureTest {
    private fun resource(name: String) = javaClass.classLoader!!.getResourceAsStream(name)!!.readBytes()

    private fun pcm(): ShortArray {
        val wav = resource("probe16k.wav")
        val data = ByteBuffer.wrap(wav, 44, wav.size - 44).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        return ShortArray(data.remaining()).also { data.get(it) }
    }

    /** Spitzen aus einer Signatur lesen: Band -> Liste (Durchlauf, Stärke, Frequenz-Bin). */
    private fun parse(bin: ByteArray): Map<Int, List<Triple<Int, Int, Int>>> {
        val b = ByteBuffer.wrap(bin).order(ByteOrder.LITTLE_ENDIAN)
        assertEquals(0xcafe2580.toInt(), b.getInt(0))
        val crc = CRC32().apply { update(bin, 8, bin.size - 8) }.value.toInt()
        assertEquals("CRC32", crc, b.getInt(4))
        assertEquals("Größe", bin.size - 48, b.getInt(8))
        b.position(56)
        val out = sortedMapOf<Int, List<Triple<Int, Int, Int>>>()
        while (b.remaining() >= 8) {
            val band = b.getInt() - 0x60030040
            val size = b.getInt()
            val end = b.position() + size
            var pass = 0
            val list = mutableListOf<Triple<Int, Int, Int>>()
            while (b.position() < end) {
                var d = b.get().toInt() and 0xff
                if (d == 0xff) { pass = b.getInt(); d = b.get().toInt() and 0xff }
                pass += d
                list += Triple(pass, b.getShort().toInt() and 0xffff, b.getShort().toInt() and 0xffff)
            }
            out[band] = list
            b.position(end + (4 - size % 4) % 4)
        }
        return out
    }

    @Test
    fun gleicheSpitzenWieDieDesktopBibliothek() {
        val ref = parse(Base64.getDecoder().decode(String(resource("probe16k.uri")).substringAfter("base64,")))
        val sig = ShazamSignature.from(pcm())
        val mine = parse(sig.encode())
        assertEquals(10000, sig.durationMs)
        assertEquals(ref.keys, mine.keys)
        for (band in ref.keys) {
            val r = ref.getValue(band)
            val m = mine.getValue(band)
            // eigene FFT rechnet genauer (double statt float): an der Schwelle kann eine Spitze kippen,
            // Stärke und Frequenz dürfen minimal abweichen. Shazam vergleicht ohnehin unscharf.
            val matched = r.count { a ->
                m.any { b -> a.first == b.first && kotlin.math.abs(a.third - b.third) <= 2 && kotlin.math.abs(a.second - b.second) <= 16 }
            }
            val score = matched.toDouble() / maxOf(r.size, m.size)
            println("Band $band: Referenz ${r.size}, eigene ${m.size}, passend $matched")
            assertTrue("Band $band weicht zu stark ab ($score)", score >= 0.95)
        }
    }

    @Test
    fun mitteWieShazamio() {
        val pcm = ShortArray(16_000 * 14) { (it / 16_000).toShort() }
        val mid = ShazamSignature.middle(pcm)
        assertEquals(160_000, mid.size)
        assertEquals(2.toShort(), mid.first())
    }
}
