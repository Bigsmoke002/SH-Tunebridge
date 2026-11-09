package de.bs002.tunebridge.update

import org.bouncycastle.crypto.params.Ed25519PublicKeyParameters
import org.bouncycastle.crypto.signers.Ed25519Signer
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.security.MessageDigest
import java.util.Base64

/**
 * SSH-Signaturen („SSHSIG“, wie `ssh-keygen -Y verify`) prüfen – Gegenstück zu src/tunebridge/sshsig.py.
 * Nur Ed25519 (unser Release-Schlüssel). Zugelassene Schlüssel kommen aus src/tunebridge/release_signers.
 */
object SshSig {
    class SigError(msg: String) : Exception(msg)

    /** Wirft [SigError], wenn [signature] (armored) keine gültige Signatur von einem der [allowedKeys] ist. */
    fun verify(message: ByteArray, signature: String, allowedKeys: List<String>, namespace: String) {
        val blob = unarmor(signature)
        val b = ByteBuffer.wrap(blob)
        if (blob.size < 10 || String(blob, 0, 6) != "SSHSIG") throw SigError("Kein SSHSIG-Format")
        b.position(6)
        if (b.int != 1) throw SigError("Unbekannte Signatur-Version")
        val pubkey = str(b)
        val ns = str(b)
        val reserved = str(b)
        val hashAlg = str(b)
        val sig = str(b)
        if (String(ns) != namespace) throw SigError("Falscher Namensraum")
        val alg = String(hashAlg)
        if (alg != "sha512" && alg != "sha256") throw SigError("Unbekanntes Hash-Verfahren")
        val allowed = allowedKeys.mapNotNull { runCatching { Base64.getDecoder().decode(it.trim()) }.getOrNull() }
        if (allowed.none { it.contentEquals(pubkey) }) throw SigError("Schlüssel nicht zugelassen")
        val kb = ByteBuffer.wrap(pubkey)
        val ktype = String(str(kb)); val rawKey = str(kb)
        val sb = ByteBuffer.wrap(sig)
        val stype = String(str(sb)); val rawSig = str(sb)
        if (ktype != "ssh-ed25519" || stype != "ssh-ed25519" || rawKey.size != 32 || rawSig.size != 64) throw SigError("Nur Ed25519 wird unterstützt")
        val digest = MessageDigest.getInstance(if (alg == "sha512") "SHA-512" else "SHA-256").digest(message)
        val signed = ByteArrayOutputStream().apply {
            write("SSHSIG".toByteArray()); write(string(ns)); write(string(reserved)); write(string(hashAlg)); write(string(digest))
        }.toByteArray()
        val v = Ed25519Signer().apply { init(false, Ed25519PublicKeyParameters(rawKey, 0)); update(signed, 0, signed.size) }
        if (!v.verifySignature(rawSig)) throw SigError("Signatur ungültig")
    }

    private fun unarmor(text: String): ByteArray {
        val body = text.lines().map { it.trim() }
            .dropWhile { !it.startsWith("-----BEGIN SSH SIGNATURE-----") }.drop(1)
            .takeWhile { !it.startsWith("-----END SSH SIGNATURE-----") }.joinToString("")
        if (body.isEmpty()) throw SigError("Signatur fehlt")
        return runCatching { Base64.getDecoder().decode(body) }.getOrElse { throw SigError("Signatur beschädigt") }
    }

    private fun str(b: ByteBuffer): ByteArray {
        if (b.remaining() < 4) throw SigError("Signatur abgeschnitten")
        val n = b.int
        if (n < 0 || n > b.remaining()) throw SigError("Signatur abgeschnitten")
        return ByteArray(n).also { b.get(it) }
    }

    private fun string(x: ByteArray): ByteArray = ByteBuffer.allocate(4 + x.size).putInt(x.size).put(x).array()
}
