package de.bs002.tunebridge

import de.bs002.tunebridge.audio.ShazamSignature
import de.bs002.tunebridge.net.Shazam
import kotlinx.coroutines.runBlocking
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer
import java.nio.ByteOrder

/**
 * Nur von Hand: echte Anfrage an Shazam mit build/livetest/clip.raw (16 kHz, mono, s16le).
 * Läuft nur mit TB_LIVETEST=1 – sonst würde eine liegengebliebene Aufnahme den (Release-)Bau vom Internet abhängig machen.
 */
class LiveShazamTest {
    @Test fun recognizesClip() = runBlocking {
        val f = File("build/livetest/clip.raw")
        assumeTrue(System.getenv("TB_LIVETEST") == "1" && f.exists())
        val b = ByteBuffer.wrap(f.readBytes()).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer()
        val pcm = ShortArray(b.remaining()).also { b.get(it) }
        val sig = ShazamSignature.from(ShazamSignature.middle(pcm))
        println("LIVE samplems=${sig.durationMs} uri=${sig.toUri().take(60)}…")
        val hit = Shazam.recognize(sig)
        println("LIVE Treffer: ${hit?.track?.title} – ${hit?.track?.artists}")
    }
}
