package de.bs002.tunebridge.sync

import android.net.Uri
import de.bs002.tunebridge.BuildConfig
import de.bs002.tunebridge.data.Playlist
import de.bs002.tunebridge.data.Recognition
import de.bs002.tunebridge.data.Repository
import de.bs002.tunebridge.net.Http
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.builtins.ListSerializer
import kotlinx.serialization.builtins.serializer
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.Base64
import java.util.UUID

/**
 * Handy <-> PCs im eigenen Netz, ohne Server dazwischen. Ein Handy kann mit mehreren PCs gekoppelt sein.
 *
 * Koppeln: Der PC zeigt einen QR-Code (Adressen + Einmal-Code, 5 Minuten gültig). Das Handy zeigt zuerst, was
 * wann wohin geht, und fragt erst nach deiner Bestätigung an. Der PC muss dann ebenfalls zustimmen („Zulassen“);
 * beide zeigen dieselbe Prüfzahl. Aus dem Code leiten beide denselben Schlüssel ab; das Handy schickt damit
 * verschlüsselt ein neues, zufälliges Geräte-Geheimnis.
 * Abgleich: jede Anfrage und Antwort AES-256-GCM-verschlüsselt mit dem Geheimnis, mit Zeitstempel und
 * Einmal-ID gegen Wiederholung. Angesprochen werden nur die gewählten Adressen und nur, wenn das Handy gerade im
 * passenden Netz ist.
 */
class PcSync(private val repo: Repository) {
    class PairError(message: String) : IOException(message)

    data class Invite(val addrs: List<String>, val code: String, val pcName: String, val pcId: String?)

    private val mutex = Mutex()
    private val jsonType = "application/json".toMediaType()

    companion object {
        /** shtb://pair?v=1&a=192.168.1.20:8766,100.101.1.2:8766&c=ABCDE...&n=Wohnzimmer-PC&p=<pc-id> */
        fun parseInvite(text: String): Invite? {
            val t = text.trim()
            if (t.startsWith("shtb://pair")) {
                val u = Uri.parse(t)
                val code = normCode(u.getQueryParameter("c") ?: return null)
                val addrs = u.getQueryParameter("a")?.split(',')?.map { it.trim() }?.filter { it.isNotEmpty() }.orEmpty()
                if (code.length != 20 || addrs.isEmpty()) return null
                return Invite(addrs, code, u.getQueryParameter("n") ?: "PC", u.getQueryParameter("p"))
            }
            return null
        }

        /** Eingetippter Code: Bindestriche, Leerzeichen und Groß-/Kleinschreibung egal. */
        fun normCode(s: String) = s.uppercase().filter { it in 'A'..'Z' || it in '2'..'7' }

        /** Vierstellige Prüfzahl – der PC berechnet sie unabhängig genauso (phone.confirm_code). */
        fun confirmCode(code: String, deviceId: String): String {
            val b = Crypto.hkdf(normCode(code).toByteArray(), "confirm:$deviceId", 4)
            val v = ((b[0].toLong() and 0xff) shl 24) or ((b[1].toLong() and 0xff) shl 16) or ((b[2].toLong() and 0xff) shl 8) or (b[3].toLong() and 0xff)
            return (v % 10000).toString().padStart(4, '0')
        }

        fun newDeviceId(): String = UUID.randomUUID().toString().replace("-", "").take(16)

        private fun pairKey(code: String) = Crypto.hkdf(normCode(code).toByteArray(), "pair")
        private fun syncKey(secret: String) = Crypto.hkdf(Base64.getDecoder().decode(secret), "sync")
    }

    private fun post(client: OkHttpClient, addr: String, path: String, body: String): String {
        val req = Request.Builder().url("http://$addr$path").post(body.toRequestBody(jsonType)).build()
        client.newCall(req).execute().use { r ->
            val text = r.body?.string().orEmpty()
            if (!r.isSuccessful) {
                val detail = runCatching { repo.json.parseToJsonElement(text).jsonObject["detail"]?.jsonPrimitive?.content }.getOrNull()
                throw PairError(detail ?: "PC antwortet mit Fehler ${r.code}")
            }
            return text
        }
    }

    /** Erste Adresse, unter der der PC antwortet. Antwortet der PC mit einem Fehler, wird nicht weiter probiert. */
    private fun <T> anyAddr(addrs: List<String>, block: (String) -> T): Pair<String, T> {
        var last: Exception? = null
        for (a in addrs) {
            try { return a to block(a) } catch (e: PairError) { throw e } catch (e: Exception) { last = e }
        }
        throw PairError("PC nicht erreichbar – ist SH-Tunebridge am PC offen und sind beide im selben Netz?" +
            (last?.message?.let { " ($it)" } ?: ""))
    }

    /** Adressen dieses PCs, die das Handy jetzt ansprechen darf und kann (gewählt + im passenden Netz). */
    fun reachable(link: Repository.PcLink, nets: List<Nets.Net> = Nets.current()): List<String> =
        link.targets.filter { Nets.reachable(it, nets) }

    /**
     * Koppeln – erst nach Bestätigung am Handy aufrufen. Wartet bis zu zwei Minuten, bis am PC „Zulassen“ geklickt
     * wird. [addrMode]/[useAddrs]: welche Adressen des PCs das Handy künftig benutzt.
     */
    suspend fun pair(invite: Invite, deviceId: String, addrMode: String, useAddrs: List<String>): Repository.PcLink = withContext(Dispatchers.IO) {
        if (!Nets.allowed()) throw PairError("Bitte erst erlauben, dass die App die Netzwerke des Handys erkennt")
        val secret = Base64.getEncoder().encodeToString(Crypto.randomBytes(32))
        val key = pairKey(invite.code)
        val inner = buildJsonObject {
            put("name", repo.deviceName()); put("secret", secret); put("app", BuildConfig.VERSION_NAME)
        }.toString()
        val body = buildJsonObject { put("v", 1); put("id", deviceId); put("box", Crypto.seal(key, "pair:$deviceId", inner)) }.toString()
        val chosen = if (addrMode == "all" || useAddrs.isEmpty()) invite.addrs else useAddrs
        val nets = Nets.current()
        val order = chosen.sortedBy { if (Nets.reachable(it, nets)) 0 else 1 }
        val (addr, answer) = anyAddr(order) { post(Http.pairing, it, "/phone/v1/pair", body) }
        val box = repo.json.parseToJsonElement(answer).jsonObject["box"]?.jsonPrimitive?.content ?: throw PairError("Unerwartete Antwort vom PC")
        val ok = runCatching { repo.json.parseToJsonElement(Crypto.unseal(key, "pair-ok:$deviceId", box)).jsonObject }
            .getOrElse { throw PairError("Antwort des PCs ließ sich nicht prüfen – Code abgelaufen?") }
        val link = Repository.PcLink(
            pcId = ok["pc_id"]!!.jsonPrimitive.content, pcName = ok["pc_name"]?.jsonPrimitive?.content ?: invite.pcName,
            addrs = (invite.addrs + (ok["addrs"] as? kotlinx.serialization.json.JsonArray).orEmpty().map { it.jsonPrimitive.content }).distinct(),
            deviceId = deviceId, secret = secret, addrMode = addrMode,
            useAddrs = if (addrMode == "all") emptyList() else useAddrs, added = System.currentTimeMillis() / 1000.0, lastAddr = addr,
        )
        repo.addPc(link)
        link
    }

    @Serializable
    private data class SyncAnswer(
        val cursor: Double = 0.0,
        val recs: List<Recognition> = emptyList(),
        val updates: List<Recognition> = emptyList(),
        val playlists: List<Playlist>? = null,
        @SerialName("pc_name") val pcName: String? = null,
        val addrs: List<String>? = null,
        val more: Boolean = false,
    )

    /** [skipped]: nicht versucht, weil das Handy gerade nicht im Netz dieses PCs ist (kein Fehler). */
    data class Result(val pcId: String, val pcName: String, val sent: Int, val received: Int, val playlists: Int, val skipped: Boolean = false)

    /** Mit allen gekoppelten PCs abgleichen, die gerade erreichbar sein können. Fehler je PC landen in dessen Status. */
    suspend fun syncAll(): List<Result> = repo.settings.value.pcs.map { link ->
        if (reachable(link).isEmpty()) Result(link.pcId, link.pcName, 0, 0, 0, skipped = true)
        else runCatching { sync(link.pcId) }.getOrElse { Result(link.pcId, link.pcName, 0, 0, 0) }
    }

    /** Ein Abgleich mit einem PC (in Runden, bis beide Seiten alles haben). Wirft PairError mit verständlicher Meldung. */
    suspend fun sync(pcId: String): Result = mutex.withLock {
        withContext(Dispatchers.IO) {
            var link = repo.link(pcId) ?: throw PairError("Dieser PC ist nicht (mehr) gekoppelt")
            if (!Nets.allowed()) throw PairError("Netzwerk-Erkennung ist nicht erlaubt – ohne sie gleicht das Handy nicht ab (Mehr › Datenschutz)")
            val addrs = reachable(link)
            if (addrs.isEmpty()) {
                val where = link.targets.joinToString(", ") { Nets.describe(it) }
                throw PairError("Das Handy ist gerade nicht im Netz von ${link.pcName} ($where)")
            }
            var sent = 0; var received = 0; var lists = 0
            try {
                for (round in 0 until 12) {
                    link = repo.link(pcId) ?: break
                    val out = repo.outgoing(link)
                    val rid = UUID.randomUUID().toString()
                    val payload = buildJsonObject {
                        put("ts", System.currentTimeMillis())
                        put("rid", rid)
                        put("device", buildJsonObject { put("name", repo.deviceName()); put("app", BuildConfig.VERSION_NAME) })
                        put("cursor", link.cursor)
                        put("recs", repo.json.encodeToJsonElement(ListSerializer(Recognition.serializer()), out.recs))
                        put("deleted", repo.json.encodeToJsonElement(ListSerializer(String.serializer()), out.deleted))
                        put("ops", repo.json.encodeToJsonElement(ListSerializer(Repository.Op.serializer()), out.ops.map { it.second }))
                        put("need_info", repo.json.encodeToJsonElement(ListSerializer(String.serializer()), if (round == 0) out.needInfo else emptyList()))
                    }.toString()
                    val key = syncKey(link.secret)
                    val body = buildJsonObject { put("v", 1); put("id", link.deviceId); put("box", Crypto.seal(key, "sync:${link.deviceId}", payload)) }.toString()
                    val (addr, answer) = anyAddr(if (round == 0) addrs else listOfNotNull(link.lastAddr).ifEmpty { addrs }) {
                        post(Http.lan, it, "/phone/v1/sync", body)
                    }
                    val box = repo.json.parseToJsonElement(answer).jsonObject["box"]?.jsonPrimitive?.content ?: throw PairError("Unerwartete Antwort vom PC")
                    val plain = runCatching { Crypto.unseal(key, "sync-ok:${link.deviceId}:$rid", box) }
                        .getOrElse { throw PairError("Antwort des PCs ließ sich nicht prüfen – bitte neu koppeln") }
                    val ans = repo.json.decodeFromString<SyncAnswer>(plain)
                    repo.applyIncoming(link, out, ans.recs, ans.updates, ans.playlists, ans.cursor, ans.pcName, addr, ans.addrs)
                    sent += out.recs.size + out.deleted.size + out.ops.size
                    received += ans.recs.size
                    lists = ans.playlists?.size ?: lists
                    if (out.isEmpty && !ans.more) break
                }
                Result(pcId, repo.link(pcId)?.pcName ?: link.pcName, sent, received, lists)
            } catch (e: Exception) {
                repo.updateLink(pcId) { it.copy(lastSyncError = e.message) }
                throw if (e is PairError) e else PairError(e.message ?: "Abgleich fehlgeschlagen")
            }
        }
    }

    /** Adressen-Auswahl für einen gekoppelten PC ändern. */
    fun setAddrs(pcId: String, mode: String, use: List<String>) =
        repo.updateLink(pcId) { it.copy(addrMode = mode, useAddrs = if (mode == "all") emptyList() else use.filter { a -> a in it.addrs }) }

    fun unpair(pcId: String) = repo.removePc(pcId)
}
