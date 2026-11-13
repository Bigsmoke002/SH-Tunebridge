package de.bs002.tunebridge.sync

import android.net.Uri
import de.bs002.tunebridge.BuildConfig
import de.bs002.tunebridge.data.Playlist
import de.bs002.tunebridge.data.Recognition
import de.bs002.tunebridge.data.Repository
import de.bs002.tunebridge.net.Http
import de.bs002.tunebridge.ui.Fmt
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
        val catalog: List<Repository.CatalogEntry>? = null,
        val more: Boolean = false,
    )

    /** [skipped]: nicht versucht, weil das Handy gerade nicht im Netz dieses PCs ist (kein Fehler). */
    data class Result(val pcId: String, val pcName: String, val sent: Int, val received: Int, val playlists: Int, val skipped: Boolean = false,
                      val queued: Boolean = false)

    /**
     * Mit allen gekoppelten PCs abgleichen, die gerade erreichbar sein können. Fehler je PC landen in dessen Status.
     * Nicht im Netz, aber „Unterwegs“ eingeschaltet: Anfrage übers Internet ablegen und eine fertige Antwort abholen
     * (ohne zu warten – der PC antwortet innerhalb einiger Minuten, abgeholt wird beim nächsten Mal).
     */
    suspend fun syncAll(manual: Boolean = false): List<Result> = repo.settings.value.pcs.map { link ->
        if (reachable(link).isEmpty()) {
            if (link.relay) runCatching { relaySync(link.pcId, manual) }.getOrElse { Result(link.pcId, link.pcName, 0, 0, 0) }
            else Result(link.pcId, link.pcName, 0, 0, 0, skipped = true)
        } else runCatching { sync(link.pcId) }.getOrElse { Result(link.pcId, link.pcName, 0, 0, 0) }
    }

    private fun payload(link: Repository.PcLink, out: Repository.Outgoing, rid: String, round: Int) = buildJsonObject {
        put("ts", System.currentTimeMillis())
        put("rid", rid)
        put("device", buildJsonObject { put("name", repo.deviceName()); put("app", BuildConfig.VERSION_NAME) })
        put("cursor", link.cursor)
        put("recs", repo.json.encodeToJsonElement(ListSerializer(Recognition.serializer()), out.recs))
        put("deleted", repo.json.encodeToJsonElement(ListSerializer(String.serializer()), out.deleted))
        put("ops", repo.json.encodeToJsonElement(ListSerializer(Repository.Op.serializer()), out.ops.map { it.second }))
        put("need_info", repo.json.encodeToJsonElement(ListSerializer(String.serializer()), if (round == 0) out.needInfo else emptyList()))
        link.lists?.let { put("lists", repo.json.encodeToJsonElement(ListSerializer(String.serializer()), it)) }
    }

    /** Ein Abgleich mit einem PC (in Runden, bis beide Seiten alles haben). Wirft PairError mit verständlicher Meldung. */
    suspend fun sync(pcId: String): Result {
        val first = repo.link(pcId) ?: throw PairError("Dieser PC ist nicht (mehr) gekoppelt")
        if (first.relay && reachable(first).isEmpty()) return relaySync(pcId, manual = true)
        return lanSync(pcId)
    }

    private suspend fun lanSync(pcId: String): Result = mutex.withLock {
        withContext(Dispatchers.IO) {
            var link = repo.link(pcId) ?: throw PairError("Dieser PC ist nicht (mehr) gekoppelt")
            if (!Nets.allowed()) throw PairError("Netzwerk-Erkennung ist nicht erlaubt – ohne sie gleicht das Handy nicht ab (Mehr › Datenschutz)")
            val addrs = reachable(link)
            if (addrs.isEmpty()) {
                val where = link.targets.joinToString(", ") { Nets.describe(it) }
                throw PairError("Das Handy ist gerade nicht im Netz von ${link.pcName} ($where)" +
                    " – für unterwegs beim PC „Unterwegs abgleichen“ einschalten")
            }
            var sent = 0; var received = 0; var lists = 0
            try {
                for (round in 0 until 12) {
                    link = repo.link(pcId) ?: break
                    val out = repo.outgoing(link)
                    val rid = UUID.randomUUID().toString()
                    val payload = payload(link, out, rid, round).toString()
                    val key = syncKey(link.secret)
                    val body = buildJsonObject { put("v", 1); put("id", link.deviceId); put("box", Crypto.seal(key, "sync:${link.deviceId}", payload)) }.toString()
                    val (addr, answer) = anyAddr(if (round == 0) addrs else listOfNotNull(link.lastAddr).ifEmpty { addrs }) {
                        post(Http.lan, it, "/phone/v1/sync", body)
                    }
                    val box = repo.json.parseToJsonElement(answer).jsonObject["box"]?.jsonPrimitive?.content ?: throw PairError("Unerwartete Antwort vom PC")
                    val plain = runCatching { Crypto.unseal(key, "sync-ok:${link.deviceId}:$rid", box) }
                        .getOrElse { throw PairError("Antwort des PCs ließ sich nicht prüfen – bitte neu koppeln") }
                    val ans = repo.json.decodeFromString<SyncAnswer>(plain)
                    repo.applyIncoming(link, out, ans.recs, ans.updates, ans.playlists, ans.cursor, ans.pcName, addr, ans.addrs, ans.catalog)
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

    /** Nur abholen, was der PC inzwischen beantwortet hat (ohne neue Anfrage). */
    suspend fun relayPickup() = repo.settings.value.pcs.filter { it.relay && it.relayRid != null }.forEach { l ->
        runCatching { relaySync(l.pcId, manual = false, pickupOnly = true) }
    }

    @Volatile private var relayTried = 0L
    @Volatile private var relayPause = 0L

    /**
     * Abgleich übers Internet: erst eine fertige Antwort auf die zuletzt abgelegte Anfrage abholen, dann (falls keine
     * mehr wartet) eine neue Anfrage ablegen. Der PC schaut etwa alle 6 Minuten nach; die Antwort holt das Handy beim
     * nächsten Abgleich bzw. einige Minuten später still ab – nichts geht verloren.
     * Der Server erlaubt ohne Konto nur wenige Anfragen pro Stunde: automatisch höchstens alle 10 Minuten, nach
     * „zu viele Anfragen“ eine Stunde Pause.
     */
    suspend fun relaySync(pcId: String, manual: Boolean, pickupOnly: Boolean = false): Result = mutex.withLock {
        withContext(Dispatchers.IO) {
            var link = repo.link(pcId) ?: throw PairError("Dieser PC ist nicht (mehr) gekoppelt")
            if (!link.relay) throw PairError("Unterwegs-Abgleich ist für ${link.pcName} aus")
            val now = System.currentTimeMillis()
            if (now < relayPause) throw PairError("Server: gerade zu viele Anfragen – Unterwegs-Abgleich macht bis ${Fmt.clock(relayPause / 1000.0)} Pause")
            if (!manual && !pickupOnly && now - relayTried < 10 * 60_000) return@withContext Result(pcId, link.pcName, 0, 0, 0, queued = link.relayRid != null)
            relayTried = now
            val parse = Relay.parser(repo.json)
            val inbox = Relay.keys(link.secret, "to-phone")
            val outbox = Relay.keys(link.secret, "to-pc")
            var received = 0; var lists = 0
            try {
                // 1) Antwort auf die abgelegte Anfrage abholen
                link.relayRid?.let { rid ->
                    val (doc, _) = Relay.get(inbox, parse)
                    if (doc?.get("rid")?.jsonPrimitive?.content == rid) {
                        val ans = repo.json.decodeFromJsonElement(SyncAnswer.serializer(), doc["ans"] ?: throw PairError("Unerwartete Antwort vom PC"))
                        val dummy = Repository.Op("", "", de.bs002.tunebridge.data.Track(title = ""))
                        val sentOut = Repository.Outgoing(emptyList(), emptyList(), link.relayOps.map { it to dummy }, emptyList(), link.relaySeq)
                        repo.applyIncoming(link, sentOut, ans.recs, ans.updates, ans.playlists, ans.cursor, ans.pcName, repo.RELAY, null, ans.catalog)
                        repo.updateLink(pcId) { it.copy(relayRid = null, relayOps = emptyList()) }
                        received = ans.recs.size
                        lists = ans.playlists?.size ?: 0
                    }
                }
                link = repo.link(pcId) ?: throw PairError("Dieser PC ist nicht (mehr) gekoppelt")
                // 2) Neue Anfrage nur, wenn keine mehr offen ist (oder die offene älter als einen Tag)
                val waiting = link.relayRid != null && now / 1000.0 - link.relayAt < 86_400
                if (pickupOnly || waiting) return@withContext Result(pcId, link.pcName, 0, received, lists, queued = waiting)
                val out = repo.outgoing(link)
                val rid = UUID.randomUUID().toString()
                val doc = buildJsonObject { put("req", payload(link, out, rid, 0)) }.toString()
                var rev = link.relayRev
                for (attempt in 0 until 3) {
                    try { rev = Relay.put(outbox, rev, doc, parse); break } catch (c: Relay.Conflict) { rev = c.rev; if (attempt == 2) throw c }
                }
                repo.updateLink(pcId) {
                    it.copy(relayRid = rid, relaySeq = out.maxSeq, relayOps = out.ops.map { o -> o.first }, relayRev = rev,
                        relayAt = now / 1000.0, lastSyncError = null)
                }
                Result(pcId, link.pcName, out.recs.size + out.deleted.size + out.ops.size, received, lists, queued = true)
            } catch (e: Relay.Limited) {
                relayPause = System.currentTimeMillis() + 3_600_000
                repo.updateLink(pcId) { it.copy(lastSyncError = e.message) }
                throw PairError(e.message ?: "Server: zu viele Anfragen")
            } catch (e: Exception) {
                repo.updateLink(pcId) { it.copy(lastSyncError = e.message) }
                throw if (e is PairError) e else PairError("Unterwegs-Abgleich: ${e.message ?: "fehlgeschlagen"}")
            }
        }
    }

    /** Unterwegs-Abgleich für einen PC ein-/ausschalten. Ausschalten löscht beide Ablagen auf dem Server. */
    suspend fun setRelay(pcId: String, on: Boolean) = withContext(Dispatchers.IO) {
        val link = repo.link(pcId) ?: return@withContext
        if (!on && link.relay) Relay.delete(link.secret)
        repo.updateLink(pcId) { it.copy(relay = on, relayRid = null, relayOps = emptyList(), relayRev = 0) }
    }

    /**
     * Ähnliche Songs vom ersten erreichbaren PC (gleiche Verschlüsselung wie der Abgleich; der PC fragt Last.fm/Deezer).
     * null = gerade kein PC erreichbar.
     */
    suspend fun similar(track: de.bs002.tunebridge.data.Track, limit: Int = 20): List<Pair<de.bs002.tunebridge.data.Track, Double>>? =
        withContext(Dispatchers.IO) {
            if (!Nets.allowed()) return@withContext null
            val nets = Nets.current()
            for (link in repo.settings.value.pcs) {
                val addrs = reachable(link, nets).ifEmpty { continue }
                val rid = UUID.randomUUID().toString()
                val payload = buildJsonObject {
                    put("ts", System.currentTimeMillis()); put("rid", rid); put("limit", limit)
                    put("track", buildJsonObject {
                        put("title", track.title)
                        put("artists", kotlinx.serialization.json.JsonArray(track.artists.map { kotlinx.serialization.json.JsonPrimitive(it) }))
                        track.isrc?.let { put("isrc", it) }
                    })
                }.toString()
                val key = syncKey(link.secret)
                val body = buildJsonObject { put("v", 1); put("id", link.deviceId); put("box", Crypto.seal(key, "similar:${link.deviceId}", payload)) }.toString()
                val answer = try {
                    anyAddr(listOfNotNull(link.lastAddr).filter { it in addrs }.ifEmpty { addrs }) { post(Http.lan, it, "/phone/v1/similar", body) }.second
                } catch (e: PairError) {
                    if (e.message?.startsWith("PC nicht erreichbar") == true) continue else throw e
                }
                val box = repo.json.parseToJsonElement(answer).jsonObject["box"]?.jsonPrimitive?.content ?: throw PairError("Unerwartete Antwort vom PC")
                val plain = runCatching { Crypto.unseal(key, "similar-ok:${link.deviceId}:$rid", box) }
                    .getOrElse { throw PairError("Antwort des PCs ließ sich nicht prüfen – bitte neu koppeln") }
                val items = repo.json.decodeFromString<SimilarAnswer>(plain).items
                return@withContext items.map { it.toTrack() to it.match }
            }
            null
        }

    /**
     * Ersatz-Player: Kennung des YouTube-Videos bzw. Spotify-Songs vom PC (fallback.py) – der PC sucht mit seinem
     * YouTube-Zugang. [kinds] = Anbieter, für die du am Handy eingewilligt hast. null = kein PC erreichbar.
     */
    suspend fun fallback(track: de.bs002.tunebridge.data.Track, kinds: List<String>, known: Map<String, String>): Map<String, String?>? =
        withContext(Dispatchers.IO) {
            if (!Nets.allowed() || kinds.isEmpty()) return@withContext null
            val nets = Nets.current()
            for (link in repo.settings.value.pcs) {
                val addrs = reachable(link, nets).ifEmpty { continue }
                val rid = UUID.randomUUID().toString()
                val payload = buildJsonObject {
                    put("ts", System.currentTimeMillis()); put("rid", rid)
                    put("consent", kotlinx.serialization.json.JsonArray(kinds.map { kotlinx.serialization.json.JsonPrimitive(it) }))
                    put("known", buildJsonObject { known.forEach { (k, v) -> put(k, v) } })
                    put("track", buildJsonObject {
                        put("title", track.title)
                        put("artists", kotlinx.serialization.json.JsonArray(track.artists.map { kotlinx.serialization.json.JsonPrimitive(it) }))
                        track.isrc?.let { put("isrc", it) }
                        if (track.ids.isNotEmpty()) put("ids", buildJsonObject { track.ids.forEach { (k, v) -> put(k, v) } })
                    })
                }.toString()
                val key = syncKey(link.secret)
                val body = buildJsonObject { put("v", 1); put("id", link.deviceId); put("box", Crypto.seal(key, "fallback:${link.deviceId}", payload)) }.toString()
                val answer = try {
                    anyAddr(listOfNotNull(link.lastAddr).filter { it in addrs }.ifEmpty { addrs }) { post(Http.lan, it, "/phone/v1/fallback", body) }.second
                } catch (e: PairError) {
                    if (e.message?.startsWith("PC nicht erreichbar") == true) continue
                    if (e.message?.contains("Not Found") == true) continue          // ältere PC-Version
                    throw e
                }
                val box = repo.json.parseToJsonElement(answer).jsonObject["box"]?.jsonPrimitive?.content ?: throw PairError("Unerwartete Antwort vom PC")
                val plain = runCatching { Crypto.unseal(key, "fallback-ok:${link.deviceId}:$rid", box) }
                    .getOrElse { throw PairError("Antwort des PCs ließ sich nicht prüfen – bitte neu koppeln") }
                val o = repo.json.parseToJsonElement(plain).jsonObject
                return@withContext listOf("youtube", "spotify").associateWith { k ->
                    (o[k] as? kotlinx.serialization.json.JsonPrimitive)?.takeIf { it.isString }?.content
                }
            }
            null
        }

    /** Remixe, Covers & andere Versionen vom PC (remixes.py). null = kein PC erreichbar. */
    suspend fun versions(track: de.bs002.tunebridge.data.Track): de.bs002.tunebridge.net.VersionResult? =
        withContext(Dispatchers.IO) {
            if (!Nets.allowed()) return@withContext null
            val nets = Nets.current()
            for (link in repo.settings.value.pcs) {
                val addrs = reachable(link, nets).ifEmpty { continue }
                val rid = UUID.randomUUID().toString()
                val payload = buildJsonObject {
                    put("ts", System.currentTimeMillis()); put("rid", rid)
                    put("track", buildJsonObject {
                        put("title", track.title)
                        put("artists", kotlinx.serialization.json.JsonArray(track.artists.map { kotlinx.serialization.json.JsonPrimitive(it) }))
                        track.durationMs?.let { put("duration_ms", it) }
                    })
                }.toString()
                val key = syncKey(link.secret)
                val body = buildJsonObject { put("v", 1); put("id", link.deviceId); put("box", Crypto.seal(key, "versions:${link.deviceId}", payload)) }.toString()
                val answer = try {
                    anyAddr(listOfNotNull(link.lastAddr).filter { it in addrs }.ifEmpty { addrs }) { post(Http.lan, it, "/phone/v1/versions", body) }.second
                } catch (e: PairError) {
                    if (e.message?.startsWith("PC nicht erreichbar") == true) continue
                    if (e.message?.contains("404") == true || e.message?.contains("Not Found") == true) continue   // ältere PC-Version
                    throw e
                }
                val box = repo.json.parseToJsonElement(answer).jsonObject["box"]?.jsonPrimitive?.content ?: throw PairError("Unerwartete Antwort vom PC")
                val plain = runCatching { Crypto.unseal(key, "versions-ok:${link.deviceId}:$rid", box) }
                    .getOrElse { throw PairError("Antwort des PCs ließ sich nicht prüfen – bitte neu koppeln") }
                val a = repo.json.decodeFromString<VersionsAnswer>(plain)
                return@withContext de.bs002.tunebridge.net.VersionResult(a.core, a.kinds.map { it.id to it.name },
                    a.items.map { de.bs002.tunebridge.net.Version(it.toTrack(), it.kind, it.label) })
            }
            null
        }

    /**
     * „Entdecken“ über den PC (discover.py): [what] = search/artist/album/charts/genres, [arg] = Suchbegriff bzw. Deezer-Kennung.
     * Antwort als JSON-Text (Felder wie am PC). null = kein PC erreichbar bzw. PC zu alt.
     */
    suspend fun discover(what: String, arg: String?, kind: String? = null): String? =
        withContext(Dispatchers.IO) {
            if (!Nets.allowed()) return@withContext null
            val nets = Nets.current()
            for (link in repo.settings.value.pcs) {
                val addrs = reachable(link, nets).ifEmpty { continue }
                val rid = UUID.randomUUID().toString()
                val payload = buildJsonObject {
                    put("ts", System.currentTimeMillis()); put("rid", rid); put("what", what)
                    arg?.let { put("arg", it) }; kind?.let { put("kind", it) }
                }.toString()
                val key = syncKey(link.secret)
                val body = buildJsonObject { put("v", 1); put("id", link.deviceId); put("box", Crypto.seal(key, "discover:${link.deviceId}", payload)) }.toString()
                val answer = try {
                    anyAddr(listOfNotNull(link.lastAddr).filter { it in addrs }.ifEmpty { addrs }) { post(Http.lan, it, "/phone/v1/discover", body) }.second
                } catch (e: PairError) {
                    if (e.message?.startsWith("PC nicht erreichbar") == true) continue
                    if (e.message == "Not Found" || e.message?.endsWith("Fehler 404") == true) continue   // ältere PC-Version
                    throw e
                }
                val box = repo.json.parseToJsonElement(answer).jsonObject["box"]?.jsonPrimitive?.content ?: throw PairError("Unerwartete Antwort vom PC")
                return@withContext runCatching { Crypto.unseal(key, "discover-ok:${link.deviceId}:$rid", box) }
                    .getOrElse { throw PairError("Antwort des PCs ließ sich nicht prüfen – bitte neu koppeln") }
            }
            null
        }

    @Serializable
    private data class VersionsAnswer(val core: String = "", val kinds: List<VersionKind> = emptyList(), val items: List<VersionItem> = emptyList())

    @Serializable
    private data class VersionKind(val id: String, val name: String)

    @Serializable
    private data class VersionItem(
        val title: String, val artists: List<String> = emptyList(), val album: String? = null,
        @SerialName("duration_ms") val durationMs: Long? = null, val ids: Map<String, String> = emptyMap(),
        val cover: String? = null, val kind: String = "andere", val label: String = "",
    ) {
        fun toTrack() = de.bs002.tunebridge.data.Track(title = title, artists = artists, album = album, durationMs = durationMs,
            ids = ids, cover = cover?.takeIf { it.startsWith("https://") })
    }

    /** Erster erreichbarer PC (für Mix/Set-Planer). */
    fun firstReachable(): Repository.PcLink? =
        if (!Nets.allowed()) null else Nets.current().let { nets -> repo.settings.value.pcs.firstOrNull { reachable(it, nets).isNotEmpty() } }

    /**
     * Auftrag an einen PC (Mix erstellen, Set-Planer): Anfrage [act] mit [fields], verschlüsselt wie der Abgleich.
     * Der PC rechnet; das Handy fragt den Stand ab. Fehler des PCs kommen als [PairError] mit seinem Text.
     */
    suspend fun job(link: Repository.PcLink, act: String, fields: kotlinx.serialization.json.JsonObject = kotlinx.serialization.json.JsonObject(emptyMap())):
        kotlinx.serialization.json.JsonObject = withContext(Dispatchers.IO) {
        val addrs = reachable(link).ifEmpty { throw PairError("PC nicht erreichbar – gleiches Netz/VPN?") }
        val rid = UUID.randomUUID().toString()
        val payload = kotlinx.serialization.json.JsonObject(fields + mapOf(
            "ts" to kotlinx.serialization.json.JsonPrimitive(System.currentTimeMillis()),
            "rid" to kotlinx.serialization.json.JsonPrimitive(rid), "act" to kotlinx.serialization.json.JsonPrimitive(act))).toString()
        val key = syncKey(link.secret)
        val body = buildJsonObject { put("v", 1); put("id", link.deviceId); put("box", Crypto.seal(key, "job:${link.deviceId}", payload)) }.toString()
        val answer = anyAddr(listOfNotNull(link.lastAddr).filter { it in addrs }.ifEmpty { addrs }) { post(Http.lan, it, "/phone/v1/job", body) }.second
        val box = repo.json.parseToJsonElement(answer).jsonObject["box"]?.jsonPrimitive?.content ?: throw PairError("Unerwartete Antwort vom PC")
        val plain = runCatching { Crypto.unseal(key, "job-ok:${link.deviceId}:$rid", box) }
            .getOrElse { throw PairError("Antwort des PCs ließ sich nicht prüfen – bitte neu koppeln") }
        repo.json.parseToJsonElement(plain).jsonObject
    }

    @Serializable
    private data class SimilarAnswer(val items: List<SimilarItem> = emptyList())

    @Serializable
    private data class SimilarItem(
        val title: String, val artists: List<String> = emptyList(), val album: String? = null,
        @SerialName("duration_ms") val durationMs: Long? = null, val isrc: String? = null,
        val ids: Map<String, String> = emptyMap(), val genre: String? = null, val subgenre: String? = null,
        val cover: String? = null, @SerialName("preview_url") val previewUrl: String? = null, val match: Double = 0.0,
    ) {
        fun toTrack() = de.bs002.tunebridge.data.Track(title = title, artists = artists, album = album, durationMs = durationMs,
            isrc = isrc, ids = ids, genre = genre, subgenre = subgenre, cover = cover, previewUrl = previewUrl?.takeIf { it.startsWith("http") })
    }

    /** Adressen-Auswahl für einen gekoppelten PC ändern. */
    fun setAddrs(pcId: String, mode: String, use: List<String>) =
        repo.updateLink(pcId) { it.copy(addrMode = mode, useAddrs = if (mode == "all") emptyList() else use.filter { a -> a in it.addrs }) }

    suspend fun unpair(pcId: String) {
        repo.link(pcId)?.takeIf { it.relay }?.let { l -> withContext(Dispatchers.IO) { Relay.delete(l.secret) } }
        repo.removePc(pcId)
    }
}
