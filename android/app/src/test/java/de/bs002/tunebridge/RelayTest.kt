package de.bs002.tunebridge

import de.bs002.tunebridge.sync.Relay
import org.junit.Assert.assertEquals
import org.junit.Test

/** Gegenprobe zu src/tunebridge/phone.py (_relay_keys = share.derive(_kdf(secret, "relay-<richtung>"))). */
class RelayTest {
    private val secret = "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8="   // Bytes 0..31

    private fun hex(b: ByteArray) = b.joinToString("") { "%02x".format(it) }

    @Test
    fun keysMatchDesktop() {
        val a = Relay.keys(secret, "to-pc")
        assertEquals("d5612651eaec24b6d997d948e63b691d", a.space)
        assertEquals("MT1K21GTValZctuhCRA0Qipvv_Z-CUC0XBMU4hW0nZY", a.token)
        assertEquals("27c8d29caf50019e6451497d78641cdc0a959f6bdec49a19250260a8bb2a62c7", hex(a.key))
        val b = Relay.keys(secret, "to-phone")
        assertEquals("d190f5036b852ba242d7f589d8d27c40", b.space)
        assertEquals("_yfiZybqDLt63L1Mg9w_1glQy6jCaSvxlprqkabfttE", b.token)
        assertEquals("5fa2e071539627f59d69ff3336db73da7ce4419758b5af291ddf09966b5ab597", hex(b.key))
    }
}
