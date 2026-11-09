package de.bs002.tunebridge.sync

import java.io.ByteArrayOutputStream
import java.security.SecureRandom
import java.util.Base64
import java.util.zip.Deflater
import java.util.zip.Inflater
import javax.crypto.Cipher
import javax.crypto.Mac
import javax.crypto.spec.GCMParameterSpec
import javax.crypto.spec.SecretKeySpec

/**
 * Gleiche Verschlüsselung wie beim Teilen am Desktop (share.seal/unseal):
 * JSON -> zlib -> AES-256-GCM (12-Byte-Nonce vorn, Zusatzdaten = Zweck + Geräte-ID) -> Base64.
 */
object Crypto {
    private val random = SecureRandom()
    private const val SALT = "sh-tunebridge-phone-v1"
    private const val MAX_PLAIN = 16 shl 20

    fun randomBytes(n: Int) = ByteArray(n).also { random.nextBytes(it) }

    /** HKDF-SHA256 (RFC 5869) – wie `cryptography`'s HKDF in Python. */
    fun hkdf(ikm: ByteArray, info: String, length: Int = 32, salt: ByteArray = SALT.toByteArray()): ByteArray {
        val mac = Mac.getInstance("HmacSHA256")
        mac.init(SecretKeySpec(salt, "HmacSHA256"))
        val prk = mac.doFinal(ikm)
        mac.init(SecretKeySpec(prk, "HmacSHA256"))
        val out = ByteArrayOutputStream()
        var block = ByteArray(0)
        var counter = 1
        while (out.size() < length) {
            mac.update(block); mac.update(info.toByteArray()); mac.update(counter.toByte())
            block = mac.doFinal()
            out.write(block)
            counter++
        }
        return out.toByteArray().copyOf(length)
    }

    fun seal(key: ByteArray, aad: String, plain: String): String {
        val deflater = Deflater(9)
        deflater.setInput(plain.toByteArray()); deflater.finish()
        val z = ByteArrayOutputStream()
        val buf = ByteArray(8192)
        while (!deflater.finished()) z.write(buf, 0, deflater.deflate(buf))
        deflater.end()
        val nonce = randomBytes(12)
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.ENCRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, nonce))
        c.updateAAD(aad.toByteArray())
        return Base64.getEncoder().encodeToString(nonce + c.doFinal(z.toByteArray()))
    }

    fun unseal(key: ByteArray, aad: String, b64: String): String {
        val blob = Base64.getDecoder().decode(b64)
        val c = Cipher.getInstance("AES/GCM/NoPadding")
        c.init(Cipher.DECRYPT_MODE, SecretKeySpec(key, "AES"), GCMParameterSpec(128, blob, 0, 12))
        c.updateAAD(aad.toByteArray())
        val z = c.doFinal(blob, 12, blob.size - 12)
        val inf = Inflater().apply { setInput(z) }
        val out = ByteArrayOutputStream()
        val buf = ByteArray(8192)
        while (!inf.finished()) {
            val n = inf.inflate(buf)
            if (n == 0 && (inf.needsInput() || inf.needsDictionary())) break
            out.write(buf, 0, n)
            check(out.size() <= MAX_PLAIN) { "Antwort zu groß" }
        }
        inf.end()
        return out.toString(Charsets.UTF_8.name())
    }
}
