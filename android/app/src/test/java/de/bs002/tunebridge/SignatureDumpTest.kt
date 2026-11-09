package de.bs002.tunebridge

import de.bs002.tunebridge.audio.ShazamSignature
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Nur auf Wunsch (TB_SIG_WAV gesetzt): Signatur einer echten Aufnahme (16 kHz mono WAV) in eine Datei schreiben,
 * um sie von außen bei Shazam zu prüfen – ohne Mikrofon. Im normalen Testlauf übersprungen.
 */
class SignatureDumpTest {
    @Test
    fun dump() {
        val wav = System.getenv("TB_SIG_WAV")
        assumeTrue(!wav.isNullOrBlank())
        val bytes = File(wav!!).readBytes()
        val data = ByteBuffer.wrap(bytes, 44, bytes.size - 44).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        val pcm = ShortArray(data.remaining()).also { data.get(it) }
        val sig = ShazamSignature.from(ShazamSignature.middle(pcm, 10))
        File(System.getenv("TB_SIG_OUT")!!).writeText("${sig.durationMs}\n${sig.toUri()}")
    }
}
