package de.bs002.tunebridge.sync

import de.bs002.tunebridge.net.Http
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.Base64

/**
 * Abgleich übers Internet (unterwegs): Handy und PC tauschen Anfrage und Antwort über zwei Ablagen auf
 * shtunebridge.bs002.de aus – dieselben Teilen-Räume wie „Playlists teilen“ am PC (desktop: phone.py, Relais).
 *
 * Raum-ID, Schreib-Token und Schlüssel leiten beide aus dem Geräte-Geheimnis der Kopplung ab (HKDF):
 * „to-pc“ (Handy schreibt, PC liest) und „to-phone“ (PC schreibt, Handy liest). Der Inhalt ist mit AES-256-GCM
 * verschlüsselt; der Server sieht nur zufällige Kennungen, unlesbare Blöcke und das Datum.
 */
object Relay {
    const val HOST = "https://shtunebridge.bs002.de"
    private const val SHARE_SALT = "sh-tunebridge-share-v1"
    private val jsonType = "application/json".toMediaType()

    class Keys(val space: String, val token: String, val key: ByteArray) {
        val aad get() = "$space/private"
    }

    class Conflict(val rev: Long) : IOException("Inzwischen geändert")
    class Limited : IOException("Server: gerade zu viele Anfragen – Unterwegs-Abgleich macht eine Stunde Pause")

    /** Wie share.derive(phone._kdf(secret, "relay-<richtung>")) am PC. */
    fun keys(secret: String, direction: String): Keys {
        val root = Crypto.hkdf(Base64.getDecoder().decode(secret), "relay-$direction")
        val salt = SHARE_SALT.toByteArray()
        val space = Crypto.hkdf(root, "space", 16, salt).joinToString("") { "%02x".format(it) }
        val token = Base64.getUrlEncoder().withoutPadding().encodeToString(Crypto.hkdf(root, "write", 32, salt))
        return Keys(space, token, Crypto.hkdf(root, "private", 32, salt))
    }

    private fun req(k: Keys, path: String = "") =
        Request.Builder().url("$HOST/v1/share/${k.space}$path").header("X-Share-Token", k.token).header("User-Agent", "SH-Tunebridge-Android")

    /** Inhalt der Ablage (entschlüsselt) und ihre Version; null = leer. */
    fun get(k: Keys, parse: (String) -> JsonObject): Pair<JsonObject?, Long> {
        Http.client.newCall(req(k, "/private").get().build()).execute().use { r ->
            if (r.code == 404) return null to 0
            if (r.code == 429) throw Limited()
            if (!r.isSuccessful) throw IOException("Server-Ablage: Fehler ${r.code}")
            val j = parse(r.body?.string().orEmpty())
            val blob = j["blob"]?.jsonPrimitive?.content ?: throw IOException("Unerwartete Antwort vom Server")
            val rev = j["rev"]?.jsonPrimitive?.longOrNull ?: 0
            val plain = runCatching { Crypto.unseal(k.key, k.aad, blob) }.getOrElse { throw IOException("Ablage ließ sich nicht entschlüsseln") }
            return parse(plain) to rev
        }
    }

    /** Ablage überschreiben, wenn sie noch Version [rev] hat. Neue Version zurück; [Conflict] mit der aktuellen. */
    fun put(k: Keys, rev: Long, doc: String, parse: (String) -> JsonObject): Long {
        val blob = Crypto.seal(k.key, k.aad, doc)
        if (Base64.getDecoder().decode(blob).size > 190 * 1024) throw IOException("Zu viel auf einmal für unterwegs")
        val body = buildJsonObject { put("rev", rev); put("priv", blob) }.toString()
        Http.client.newCall(req(k).put(body.toRequestBody(jsonType)).build()).execute().use { r ->
            val text = r.body?.string().orEmpty()
            val j = runCatching { parse(text) }.getOrNull()
            if (r.code == 409) throw Conflict(j?.get("rev")?.jsonPrimitive?.longOrNull ?: 0)
            if (r.code == 429) throw Limited()
            if (!r.isSuccessful) throw IOException("Server-Ablage: Fehler ${r.code}")
            return j?.get("rev")?.jsonPrimitive?.longOrNull ?: (rev + 1)
        }
    }

    /** Beide Ablagen löschen (beim Ausschalten oder Entkoppeln). Fehler egal – sonst löscht der Server nach einem Jahr. */
    fun delete(secret: String) {
        for (dir in listOf("to-pc", "to-phone")) runCatching {
            Http.client.newCall(req(keys(secret, dir)).delete().build()).execute().close()
        }
    }

    fun parser(json: kotlinx.serialization.json.Json): (String) -> JsonObject = { json.parseToJsonElement(it).jsonObject }
}
