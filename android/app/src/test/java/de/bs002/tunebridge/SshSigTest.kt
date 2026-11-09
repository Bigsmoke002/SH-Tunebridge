package de.bs002.tunebridge

import de.bs002.tunebridge.update.SshSig
import org.junit.Assert.assertThrows
import org.junit.Test
import java.util.Base64

/** Gegenprobe zu src/tunebridge/sshsig.py: Signatur aus `ssh-keygen -Y sign` (Wegwerf-Schlüssel nur für diesen Test). */
class SshSigTest {
    private val pub = "AAAAC3NzaC1lZDI1NTE5AAAAIH30OvxHPLmxE+upxlDylaCoaFLxUgVScaIxx42rH+4X"
    private val msg = Base64.getDecoder().decode("U0gtVHVuZWJyaWRnZS1SZWxlYXNlIDEKdmVyc2lvbj05LjkuOQpmaWxlPVNILVR1bmVicmlkZ2UtOS45LjkuYXBrCnNpemU9MwpzaGEyNTY9YWJjCgpUZXN0Cg==")
    private val sig = """
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgffQ6/Ec8ubET66nGUPKVoKhoUv
FSBVJxojHHjasf7hcAAAAVc2gtdHVuZWJyaWRnZS1yZWxlYXNlAAAAAAAAAAZzaGE1MTIA
AABTAAAAC3NzaC1lZDI1NTE5AAAAQG4gskqpvBawKM7TZNcj3RzuzFkJkxw5ryyFz0nrM5
dgMjkENPAWDBkJrI/0pjIJGQ4MpiGWvcJI485G3wVcoQc=
-----END SSH SIGNATURE-----
""".trimIndent()

    @Test fun validSignatureFromAllowedKey() = SshSig.verify(msg, sig, listOf(pub), "sh-tunebridge-release")

    @Test fun rejectsWrongNamespace() {
        assertThrows(SshSig.SigError::class.java) { SshSig.verify(msg, sig, listOf(pub), "sh-tunebridge-genredb") }
    }

    @Test fun rejectsOtherKey() {
        assertThrows(SshSig.SigError::class.java) {
            SshSig.verify(msg, sig, listOf(BuildConfig.RELEASE_KEYS), "sh-tunebridge-release")
        }
    }

    @Test fun rejectsChangedManifest() {
        val bad = msg.copyOf().also { it[it.size - 2] = 'X'.code.toByte() }
        assertThrows(SshSig.SigError::class.java) { SshSig.verify(bad, sig, listOf(pub), "sh-tunebridge-release") }
    }

    @Test fun rejectsMissingSignature() {
        assertThrows(SshSig.SigError::class.java) { SshSig.verify(msg, "", listOf(pub), "sh-tunebridge-release") }
    }
}
