package de.bs002.tunebridge.data

import android.content.ContentValues
import android.database.sqlite.SQLiteDatabase
import android.os.Build
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.Serializable
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import de.bs002.tunebridge.ui.favorite
import java.util.UUID

/** Einzige Stelle, die die Datenbank anfasst. Die Oberfläche beobachtet nur die StateFlows. */
class Repository(private val db: Db, private val context: android.content.Context) {
    private val io = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    val json = Json { ignoreUnknownKeys = true; explicitNulls = false; encodeDefaults = true }

    private val _history = MutableStateFlow<List<Recognition>>(emptyList())
    val history: StateFlow<List<Recognition>> = _history.asStateFlow()
    private val _playlists = MutableStateFlow<List<Playlist>>(emptyList())
    val playlists: StateFlow<List<Playlist>> = _playlists.asStateFlow()
    private val _settings = MutableStateFlow(loadSettings())
    val settings: StateFlow<Settings> = _settings.asStateFlow()

    // Neu laden im Hintergrund (nie auf dem Haupt-Thread), mehrere Anstöße kurz hintereinander = einmal laden
    private val dirty = java.util.concurrent.atomic.AtomicInteger(0)
    private val reloadReq = kotlinx.coroutines.channels.Channel<Unit>(kotlinx.coroutines.channels.Channel.CONFLATED)

    init {
        migrateLegacyPc()
        io.launch {
            for (u in reloadReq) {
                val m = dirty.getAndSet(0)
                runCatching { if (m and H != 0) loadHistory(); if (m and P != 0) loadPlaylists() }
            }
        }
        reload()
    }

    val host: String = "Handy · ${Build.MODEL}"

    // ------------------------------------------------------------------ Einstellungen & gekoppelte PCs
    /**
     * Ein gekoppelter PC.
     * [addrs] alle Adressen aus seinem QR-Code; [addrMode] welche davon das Handy benutzt:
     * „all“ = alle, „some“ = die in [useAddrs], „one“ = nur die eine in [useAddrs].
     * [sentSeq] bis zu welchem Änderungszähler dieser PC alles vom Handy hat, [cursor] bis wann (PC-Uhr) das Handy
     * alles vom PC hat.
     */
    @Serializable
    data class CatalogEntry(val name: String, val n: Int = 0)

    @Serializable
    data class PcLink(
        val pcId: String,
        val pcName: String,
        val addrs: List<String>,
        val deviceId: String,
        val secret: String,
        val addrMode: String = "all",
        val useAddrs: List<String> = emptyList(),
        val added: Double = 0.0,
        val cursor: Double = 0.0,
        val sentSeq: Long = 0,
        val lastSync: Double = 0.0,
        val lastSyncError: String? = null,
        val lastAddr: String? = null,
        val lists: List<String>? = null,                 // welche PC-Playlists aufs Handy kommen (null = alle)
        val catalog: List<CatalogEntry> = emptyList(),   // alle Playlists des PCs (Name + Anzahl) – zum Auswählen
        val relay: Boolean = false,                      // unterwegs übers Internet abgleichen (verschlüsselte Ablage)
        val relayRid: String? = null,                    // abgelegte Anfrage, auf deren Antwort das Handy wartet
        val relaySeq: Long = 0,
        val relayOps: List<Long> = emptyList(),
        val relayRev: Long = 0,
        val relayAt: Double = 0.0,                       // wann die offene Anfrage abgelegt wurde
        val lastVia: String? = null,                     // "netz" oder "internet"
    ) {
        /** Adressen, die das Handy anspricht – zuletzt erfolgreiche zuerst. */
        val targets: List<String>
            get() {
                val chosen = if (addrMode == "all" || useAddrs.isEmpty()) addrs else useAddrs
                return chosen.sortedBy { if (it == lastAddr) 0 else 1 }
            }
    }

    @Serializable
    data class Settings(
        val consent: Int = 0,             // akzeptierte Fassung der Datenschutz-Hinweise (0 = noch nicht)
        val micAck: Boolean = false,      // § 201 StGB-Hinweis gelesen
        val covers: Boolean = true,       // Cover-Bilder laden (Apple-Server sieht die IP)
        val autoSync: Boolean = true,     // nach jeder Erkennung und beim Öffnen abgleichen, falls ein PC erreichbar ist
        val netConsent: Boolean = false,  // eigene Netzwerkkarten auslesen erlaubt (für den PC-Abgleich)
        val rootAck: Int = 0,             // Warnung „Shazam per Root auslesen“ gelesen und bestätigt (Fassung)
        val system: Boolean = false,      // Quelle: Handy-Ton statt Mikrofon
        val systemAck: Boolean = false,   // Hinweis zum Handy-Ton gelesen
        val autoUpdate: Boolean = false,  // einmal am Tag bei GitHub nach einer neuen Version fragen
        val lastUpdateCheck: Double = 0.0,
        val similarDirect: Boolean = false, // ähnliche Songs ohne PC direkt bei Deezer holen (Einwilligung)
        val fallbackYoutube: Boolean = false, // Ersatz-Hörprobe: offizieller YouTube-Player eingebettet (Einwilligung)
        val fallbackSpotify: Boolean = false, // Ersatz-Hörprobe: offizieller Spotify-Player eingebettet (Einwilligung)
        val externalMic: Boolean = false, // angeschlossenes Mikrofon (USB/Headset) statt des eingebauten nehmen
        val offlineQueue: Boolean = true, // ohne Internet den Fingerabdruck (kein Ton) merken und später nachfragen
        val seconds: Int = 10,
        val pcs: List<PcLink> = emptyList(),
        // bis Version 1 (ein einziger PC) – nur noch zum Übernehmen gelesen
        val pc: PcLink? = null,
        val lastSync: Double = 0.0,
        val cursor: Double = 0.0,
        val lastSyncError: String? = null,
    )

    private fun loadSettings(): Settings =
        db.meta("settings")?.let { runCatching { json.decodeFromString<Settings>(it) }.getOrNull() } ?: Settings()

    @Synchronized
    fun updateSettings(change: (Settings) -> Settings) {
        val next = change(_settings.value)
        _settings.value = next
        db.meta("settings", json.encodeToString(next))
    }

    fun link(pcId: String): PcLink? = _settings.value.pcs.firstOrNull { it.pcId == pcId }

    fun updateLink(pcId: String, change: (PcLink) -> PcLink) =
        updateSettings { s -> s.copy(pcs = s.pcs.map { if (it.pcId == pcId) change(it) else it }) }

    /** Neu gekoppelten PC übernehmen. Derselbe PC noch einmal ersetzt den alten Eintrag; der erste Abgleich schickt
     *  dann alles noch einmal (der PC erkennt Doppelte an der Kennung jedes Eintrags). */
    fun addPc(link: PcLink) = updateSettings { s -> s.copy(pcs = s.pcs.filterNot { it.pcId == link.pcId } + link) }

    /** PC entkoppeln: seine Playlists und offenen Änderungen verschwinden vom Handy, der Verlauf bleibt. */
    fun removePc(pcId: String) {
        val w = db.writableDatabase
        w.delete("playlists", "pc=?", arrayOf(pcId))
        w.delete("ops", "pc=?", arrayOf(pcId))
        updateSettings { s -> s.copy(pcs = s.pcs.filterNot { it.pcId == pcId }) }
        purgeTombstones()
        reload(P)
    }

    private fun migrateLegacyPc() {
        val s = _settings.value
        val legacy = s.pc
        val w = db.writableDatabase
        if (legacy != null && s.pcs.none { it.pcId == legacy.pcId }) {
            updateSettings {
                it.copy(pcs = it.pcs + legacy.copy(cursor = s.cursor, lastSync = s.lastSync), pc = null, lastSyncError = null)
            }
            w.execSQL("UPDATE playlists SET pc=? WHERE pc='legacy'", arrayOf(legacy.pcId))
            w.execSQL("UPDATE ops SET pc=? WHERE pc='legacy'", arrayOf(legacy.pcId))
        } else {
            if (legacy != null) updateSettings { it.copy(pc = null) }
            w.delete("playlists", "pc='legacy'", null)
            w.delete("ops", "pc='legacy'", null)
        }
    }

    // ------------------------------------------------------------------ Verlauf
    /** Verlauf und/oder Playlists im Hintergrund neu laden. */
    private fun reload(what: Int = H or P) {
        dirty.updateAndGet { it or what }
        reloadReq.trySend(Unit)
    }

    private fun loadHistory() {
        val list = db.readableDatabase.rawQuery(
            "SELECT id, uid, ts, host, source, engine, track, extra FROM recognitions WHERE deleted=0 ORDER BY ts DESC LIMIT $HISTORY_MAX", null,
        ).use { c ->
            buildList {
                while (c.moveToNext()) {
                    val track = runCatching { json.decodeFromString<Track>(c.getString(6)) }.getOrNull() ?: continue
                    add(Recognition(c.getLong(0), c.getString(1), c.getDouble(2), c.getString(3).orEmpty(), c.getString(4).orEmpty(),
                        c.getString(5).orEmpty(), track, runCatching { json.decodeFromString<JsonObject>(c.getString(7)) }.getOrDefault(JsonObject(emptyMap()))))
                }
            }
        }
        _history.value = list
    }

    private fun loadPlaylists() {
        _playlists.value = db.readableDatabase.rawQuery("SELECT pc, name, tracks, updated FROM playlists ORDER BY name COLLATE NOCASE", null).use { c ->
            buildList {
                while (c.moveToNext()) add(Playlist(c.getString(1), runCatching { json.decodeFromString<List<Track>>(c.getString(2)) }.getOrDefault(emptyList()),
                    c.getDouble(3), c.getString(0)))
            }
        }
    }

    fun refresh() = reload()

    fun add(track: Track, source: String, extra: JsonObject, ts: Double = System.currentTimeMillis() / 1000.0): Recognition {
        val rec = Recognition(uid = "android-" + UUID.randomUUID().toString(), ts = ts,
            host = host, source = source, engine = "shazam", track = track, extra = extra)
        val id = db.writableDatabase.insert("recognitions", null, values(rec).apply { put("seq", db.nextSeq()) })
        val saved = rec.copy(id = id)
        _history.value = (_history.value + saved).sortedByDescending { it.ts }
        reload(H)
        return saved
    }

    // ---- Offline gemerkte Fingerabdrücke (kein Ton) – warten auf Internet ----

    /** Ein offline gemerkter Fingerabdruck: Zahlenwerte wie an Shazam, keine Aufnahme. */
    @kotlinx.serialization.Serializable
    data class PendingTag(val id: String, val ts: Double, val uri: String, val samplems: Int, val system: Boolean, val level: Float)

    private val _pending = MutableStateFlow(loadPending())
    val pending: StateFlow<List<PendingTag>> = _pending.asStateFlow()

    private fun loadPending(): List<PendingTag> =
        db.meta("pending")?.let { runCatching { json.decodeFromString<List<PendingTag>>(it) }.getOrNull() } ?: emptyList()

    @Synchronized
    private fun savePending(change: (List<PendingTag>) -> List<PendingTag>) {
        val cutoff = System.currentTimeMillis() / 1000.0 - PENDING_DAYS * 86400
        val next = change(_pending.value).filter { it.ts >= cutoff }.takeLast(PENDING_MAX)
        _pending.value = next
        db.meta("pending", if (next.isEmpty()) null else json.encodeToString(next))
    }

    fun addPending(t: PendingTag) = savePending { it + t }
    fun removePending(id: String) = savePending { l -> l.filterNot { it.id == id } }
    fun clearPending() = savePending { emptyList() }

    /** Alle bekannten uids mit diesem Anfang – auch gelöschte, damit Gelöschtes nicht wiederkommt. */
    fun knownUids(prefix: String): Set<String> =
        db.readableDatabase.rawQuery("SELECT uid FROM recognitions WHERE uid LIKE ?", arrayOf("$prefix%")).use { c ->
            buildSet { while (c.moveToNext()) add(c.getString(0)) }
        }

    /** Songs aus dem Shazam-Verlauf der Shazam-App übernehmen (per Root ausgelesen). -> Anzahl neu. */
    fun importShazamApp(items: List<de.bs002.tunebridge.sync.ShazamRoot.Item>, hits: Map<String, de.bs002.tunebridge.net.Shazam.Hit?>): Int {
        if (items.isEmpty()) return 0
        val w = db.writableDatabase
        var n = 0
        w.beginTransaction()
        try {
            for (it in items) {
                val hit = hits[it.key]
                val track = hit?.track ?: Track(title = it.title ?: continue, artists = it.artists)
                val extra = kotlinx.serialization.json.buildJsonObject {
                    put("engines", kotlinx.serialization.json.JsonArray(listOf(kotlinx.serialization.json.JsonPrimitive("shazam"))))
                    hit?.let { h ->
                        put("links", JsonObject(h.links.mapValues { (_, v) -> kotlinx.serialization.json.JsonPrimitive(v) }))
                        h.label?.let { v -> put("label", kotlinx.serialization.json.JsonPrimitive(v)) }
                        h.year?.let { v -> put("year", kotlinx.serialization.json.JsonPrimitive(v)) }
                        if (h.genres.isNotEmpty()) put("shazam_genre", kotlinx.serialization.json.JsonPrimitive(h.genres.first()))
                    }
                    put("shazam_key", kotlinx.serialization.json.JsonPrimitive(it.key))
                    put("device", kotlinx.serialization.json.JsonPrimitive("handy"))
                    put("shazam_app", kotlinx.serialization.json.JsonPrimitive(true))
                }
                val rec = Recognition(uid = "android-shz-${it.requestId}", ts = if (it.ts > 100_000_000_000L) it.ts / 1000.0 else it.ts.toDouble(), host = host, source = "shazam-app",
                    engine = "shazam", track = track, extra = extra)
                if (w.insertWithOnConflict("recognitions", null, values(rec).apply { put("seq", db.nextSeq()) }, SQLiteDatabase.CONFLICT_IGNORE) > 0) n++
            }
            w.setTransactionSuccessful()
        } finally {
            w.endTransaction()
        }
        reload(H)
        return n
    }

    fun byUid(uid: String): Recognition? = _history.value.firstOrNull { it.uid == uid }

    /** Favorit an/aus (steht in extra.favorite und geht beim Abgleich mit an den PC). */
    fun setFavorite(rec: Recognition, on: Boolean) {
        val e = rec.extra - "favorite"
        updateExtra(rec.uid, JsonObject(if (on) e + ("favorite" to kotlinx.serialization.json.JsonPrimitive(true)) else e))
    }

    fun updateExtra(uid: String, extra: JsonObject) {
        _history.value = _history.value.map { if (it.uid == uid) it.copy(extra = extra) else it }
        db.writableDatabase.update("recognitions", ContentValues().apply {
            put("extra", json.encodeToString(extra)); put("seq", db.nextSeq())
        }, "uid=?", arrayOf(uid))
    }

    /** Mehrere auf einmal als Favorit markieren bzw. die Markierung entfernen. */
    fun setFavorites(uids: Collection<String>, on: Boolean) {
        val set = uids.toSet()
        val changed = _history.value.filter { it.uid in set && it.favorite != on }.associate { r ->
            val e = r.extra - "favorite"
            r.uid to JsonObject(if (on) e + ("favorite" to kotlinx.serialization.json.JsonPrimitive(true)) else e)
        }
        if (changed.isEmpty()) return
        _history.value = _history.value.map { r -> changed[r.uid]?.let { r.copy(extra = it) } ?: r }
        val w = db.writableDatabase
        w.beginTransaction()
        try {
            changed.forEach { (uid, extra) ->
                w.update("recognitions", ContentValues().apply { put("extra", json.encodeToString(extra)); put("seq", db.nextSeq()) }, "uid=?", arrayOf(uid))
            }
            w.setTransactionSuccessful()
        } finally { w.endTransaction() }
    }

    /** Aus dem Verlauf entfernen – beim nächsten Abgleich auch an jedem gekoppelten PC. Gibt die Einträge zurück
     *  (für „Rückgängig“). */
    fun delete(uid: String): List<Recognition> = deleteMany(listOf(uid))

    fun deleteMany(uids: Collection<String>): List<Recognition> {
        val set = uids.toSet()
        val gone = _history.value.filter { it.uid in set }
        _history.value = _history.value.filterNot { it.uid in set }
        val w = db.writableDatabase
        w.beginTransaction()
        try {
            for (uid in set) {
                if (_settings.value.pcs.isEmpty()) w.delete("recognitions", "uid=?", arrayOf(uid))
                else w.update("recognitions", ContentValues().apply { put("deleted", 1); put("seq", db.nextSeq()) }, "uid=?", arrayOf(uid))
            }
            w.setTransactionSuccessful()
        } finally { w.endTransaction() }
        return gone
    }

    /** „Rückgängig“ nach dem Löschen: Einträge wieder herstellen (auch wenn der PC die Löschung schon hat). */
    fun restore(recs: List<Recognition>) {
        if (recs.isEmpty()) return
        val w = db.writableDatabase
        w.beginTransaction()
        try {
            recs.forEach { r ->
                w.insertWithOnConflict("recognitions", null, values(r).apply { put("deleted", 0); put("seq", db.nextSeq()) },
                    SQLiteDatabase.CONFLICT_REPLACE)
            }
            w.setTransactionSuccessful()
        } finally { w.endTransaction() }
        val back = recs.map { it.uid }.toSet()
        _history.value = (_history.value.filterNot { it.uid in back } + recs).sortedByDescending { it.ts }
        reload(H)
    }

    /** Gelöschte Einträge endgültig entfernen, sobald jeder gekoppelte PC die Löschung bekommen hat. */
    private fun purgeTombstones() {
        val pcs = _settings.value.pcs
        val upTo = if (pcs.isEmpty()) Long.MAX_VALUE else pcs.minOf { it.sentSeq }
        db.writableDatabase.delete("recognitions", "deleted=1 AND seq<=?", arrayOf(upTo.toString()))
    }

    private fun values(r: Recognition) = ContentValues().apply {
        put("uid", r.uid); put("ts", r.ts); put("host", r.host); put("source", r.source); put("engine", r.engine)
        put("track", json.encodeToString(r.track)); put("extra", json.encodeToString(r.extra))
    }

    // ------------------------------------------------------------------ Playlists (Spiegel der Playlists je PC)
    @Serializable
    data class Op(val op: String, val playlist: String, val track: Track)

    fun addToPlaylist(pc: String, name: String, track: Track) = addAllToPlaylist(pc, name, listOf(track))

    /** Songs ans Ende einer Playlist (Doppelte bleiben draußen). Bei PC-Playlists geht die Änderung beim nächsten
     *  Abgleich an den PC; Handy-Playlists ([PHONE]) bleiben nur hier. -> Anzahl neu */
    /** Eine Playlist frisch aus der Datenbank (nicht aus dem Speicher – der kann kurz nach dem Start noch leer sein). */
    private fun stored(pc: String, name: String): Playlist? =
        db.readableDatabase.rawQuery("SELECT tracks, updated FROM playlists WHERE pc=? AND name=?", arrayOf(pc, name)).use { c ->
            if (!c.moveToFirst()) null
            else Playlist(name, runCatching { json.decodeFromString<List<Track>>(c.getString(0)) }.getOrDefault(emptyList()), c.getDouble(1), pc)
        }

    @Synchronized
    fun addAllToPlaylist(pc: String, name: String, tracks: List<Track>): Int {
        val cur = stored(pc, name)
        val have = cur?.tracks.orEmpty().map { it.key }.toMutableSet()
        val fresh = tracks.filter { have.add(it.key) }
        if (pc != PHONE) {
            fresh.forEach { queue(pc, Op("add", name, it)) }
            // Am Handy angelegt/befüllt: bleibt auch bei einer Auswahl auf dem Handy
            link(pc)?.lists?.let { l -> if (name !in l) updateLink(pc) { it.copy(lists = l + name) } }
        }
        savePlaylist(Playlist(name, cur?.tracks.orEmpty() + fresh, System.currentTimeMillis() / 1000.0, pc))
        return fresh.size
    }

    @Synchronized
    fun removeFromPlaylist(pc: String, name: String, track: Track) {
        if (pc != PHONE) queue(pc, Op("remove", name, track))
        stored(pc, name)?.let { savePlaylist(it.copy(tracks = it.tracks.filterNot { t -> t.key == track.key })) }
    }

    /** Leere Handy-Playlist anlegen. false = Name schon vergeben. */
    @Synchronized
    fun createPhonePlaylist(name: String): Boolean {
        if (_playlists.value.any { it.pc == PHONE && it.name.equals(name, true) } || stored(PHONE, name) != null) return false
        savePlaylist(Playlist(name, emptyList(), System.currentTimeMillis() / 1000.0, PHONE))
        return true
    }

    /** Handy-Playlist umbenennen. false = Name schon vergeben. */
    @Synchronized
    fun renamePhonePlaylist(old: String, new: String): Boolean {
        val p = stored(PHONE, old) ?: return false
        if (old == new) return true
        if (_playlists.value.any { it.pc == PHONE && it.name.equals(new, true) && it.name != old }) return false
        db.writableDatabase.delete("playlists", "pc=? AND name=?", arrayOf(PHONE, old))
        _playlists.value = _playlists.value.filterNot { it.pc == PHONE && it.name == old }
        savePlaylist(p.copy(name = new, updated = System.currentTimeMillis() / 1000.0))
        return true
    }

    /** Handy-Playlist löschen (PC-Playlists löscht man am PC). Gibt sie zurück – für „Rückgängig“. */
    @Synchronized
    fun deletePhonePlaylist(name: String): Playlist? {
        val p = stored(PHONE, name) ?: return null
        db.writableDatabase.delete("playlists", "pc=? AND name=?", arrayOf(PHONE, name))
        _playlists.value = _playlists.value.filterNot { it.pc == PHONE && it.name == name }
        return p
    }

    @Synchronized
    fun restorePlaylist(p: Playlist) = savePlaylist(p)

    private fun queue(pc: String, op: Op) {
        db.writableDatabase.insert("ops", null, ContentValues().apply {
            put("pc", pc); put("body", json.encodeToString(op)); put("ts", System.currentTimeMillis() / 1000.0)
        })
    }

    private fun savePlaylist(p: Playlist) {
        db.writableDatabase.insertWithOnConflict("playlists", null, ContentValues().apply {
            put("pc", p.pc); put("name", p.name); put("tracks", json.encodeToString(p.tracks)); put("updated", p.updated)
        }, SQLiteDatabase.CONFLICT_REPLACE)
        // sofort im Speicher – mehrere Änderungen kurz hintereinander bauen aufeinander auf
        _playlists.value = (_playlists.value.filterNot { it.pc == p.pc && it.name == p.name } + p)
            .sortedBy { it.name.lowercase() }
    }

    // ------------------------------------------------------------------ Sicherung (Datei, die du selbst speicherst)
    @Serializable
    data class Backup(
        val format: String = BACKUP_FORMAT,
        val v: Int = 1,
        val created: Double = System.currentTimeMillis() / 1000.0,
        val app: String = "",
        val recognitions: List<Recognition> = emptyList(),
        val playlists: List<Playlist> = emptyList(),
    )

    /** Ganzer Verlauf (ohne Obergrenze) und die Handy-Playlists. Gekoppelte PCs, Schlüssel und Einstellungen nie. */
    fun backup(appVersion: String): Backup {
        val recs = db.readableDatabase.rawQuery(
            "SELECT uid, ts, host, source, engine, track, extra FROM recognitions WHERE deleted=0 ORDER BY ts", null,
        ).use { c ->
            buildList {
                while (c.moveToNext()) {
                    val t = runCatching { json.decodeFromString<Track>(c.getString(5)) }.getOrNull() ?: continue
                    add(Recognition(0, c.getString(0), c.getDouble(1), c.getString(2).orEmpty(), c.getString(3).orEmpty(), c.getString(4).orEmpty(), t,
                        runCatching { json.decodeFromString<JsonObject>(c.getString(6)) }.getOrDefault(JsonObject(emptyMap()))))
                }
            }
        }
        return Backup(app = appVersion, recognitions = recs, playlists = _playlists.value.filter { it.pc == PHONE })
    }

    /** Sicherung zusammenführen: Fehlendes kommt dazu, Vorhandenes bleibt. -> (neue Einträge, neue Playlist-Songs) */
    fun restoreBackup(b: Backup): Pair<Int, Int> {
        require(b.format == BACKUP_FORMAT) { "Das ist keine Sicherung von SH-Tunebridge (Handy)" }
        val w = db.writableDatabase
        var n = 0
        w.beginTransaction()
        try {
            b.recognitions.forEach { r ->
                if (r.uid.isBlank()) return@forEach
                if (w.insertWithOnConflict("recognitions", null, values(r).apply { put("seq", db.nextSeq()) }, SQLiteDatabase.CONFLICT_IGNORE) > 0) n++
            }
            w.setTransactionSuccessful()
        } finally { w.endTransaction() }
        var songs = 0
        b.playlists.forEach { p -> if (p.name.isNotBlank()) songs += addAllToPlaylist(PHONE, p.name.take(120), p.tracks) }
        reload(H)
        return n to songs
    }

    // ------------------------------------------------------------------ Abgleich mit einem PC
    /** Platzhalter-Adresse für Antworten, die übers Internet kamen. */
    val RELAY = "internet"

    data class Outgoing(
        val recs: List<Recognition>, val deleted: List<String>, val ops: List<Pair<Long, Op>>, val needInfo: List<String>, val maxSeq: Long,
    ) {
        val isEmpty get() = recs.isEmpty() && deleted.isEmpty() && ops.isEmpty()
    }

    /** Was dieser PC noch nicht hat: eigene Erkennungen/Löschungen nach seinem Stand, seine offenen Playlist-Änderungen. */
    fun outgoing(link: PcLink): Outgoing {
        val d = db.readableDatabase
        val recs = mutableListOf<Recognition>(); val deleted = mutableListOf<String>()
        var maxSeq = link.sentSeq
        d.rawQuery(
            "SELECT uid, ts, host, source, engine, track, extra, deleted, seq FROM recognitions WHERE uid LIKE 'android-%' AND seq>? ORDER BY seq LIMIT 300",
            arrayOf(link.sentSeq.toString()),
        ).use { c ->
            while (c.moveToNext()) {
                maxSeq = maxOf(maxSeq, c.getLong(8))
                if (c.getInt(7) == 1) { deleted += c.getString(0); continue }
                val t = runCatching { json.decodeFromString<Track>(c.getString(5)) }.getOrNull() ?: continue
                recs += Recognition(0, c.getString(0), c.getDouble(1), c.getString(2).orEmpty(), c.getString(3).orEmpty(), c.getString(4).orEmpty(), t,
                    runCatching { json.decodeFromString<JsonObject>(c.getString(6)) }.getOrDefault(JsonObject(emptyMap())))
            }
        }
        val ops = d.rawQuery("SELECT id, body FROM ops WHERE pc=? ORDER BY id LIMIT 500", arrayOf(link.pcId)).use { c ->
            buildList { while (c.moveToNext()) runCatching { add(c.getLong(0) to json.decodeFromString<Op>(c.getString(1))) } }
        }
        val needInfo = _history.value.filter { it.track.genre == null && it.uid.startsWith("android-") }.take(200).map { it.uid }
        return Outgoing(recs, deleted, ops, needInfo, maxSeq)
    }

    /** Antwort eines PCs übernehmen: neue Erkennungen vom PC, ergänzte Song-Infos, seine Playlists, neuer Stand. */
    /** Auswahl der PC-Playlists auf dem Handy (null = alle) – wirkt beim nächsten Abgleich. */
    fun setLists(pc: String, lists: List<String>?) = updateLink(pc) { it.copy(lists = lists) }

    fun applyIncoming(
        link: PcLink, sent: Outgoing, recs: List<Recognition>, updates: List<Recognition>, playlists: List<Playlist>?,
        cursor: Double, pcName: String?, addr: String, addrs: List<String>? = null, catalog: List<CatalogEntry>? = null,
    ) {
        val w = db.writableDatabase
        w.beginTransaction()
        try {
            sent.ops.forEach { w.delete("ops", "id=?", arrayOf(it.first.toString())) }
            recs.filterNot { it.uid.startsWith("android-") }.forEach { w.insertWithOnConflict("recognitions", null, values(it), SQLiteDatabase.CONFLICT_IGNORE) }
            // Nur am Handy gepflegt (Favorit): bleibt erhalten, wenn der PC den Eintrag aktualisiert
            val favs = _history.value.filter { (it.extra["favorite"] as? kotlinx.serialization.json.JsonPrimitive)?.content == "true" }.map { it.uid }.toSet()
            updates.forEach { u ->
                val extra = if (u.uid in favs) JsonObject(u.extra + ("favorite" to kotlinx.serialization.json.JsonPrimitive(true))) else u.extra
                w.update("recognitions", ContentValues().apply {
                    put("track", json.encodeToString(u.track)); put("extra", json.encodeToString(extra))
                }, "uid=? AND deleted=0", arrayOf(u.uid))
            }
            if (playlists != null) {
                w.delete("playlists", "pc=?", arrayOf(link.pcId))
                playlists.forEach { p ->
                    w.insertWithOnConflict("playlists", null, ContentValues().apply {
                        put("pc", link.pcId); put("name", p.name); put("tracks", json.encodeToString(p.tracks)); put("updated", p.updated)
                    }, SQLiteDatabase.CONFLICT_REPLACE)
                }
            }
            w.setTransactionSuccessful()
        } finally {
            w.endTransaction()
        }
        updateLink(link.pcId) {
            it.copy(sentSeq = maxOf(it.sentSeq, sent.maxSeq), cursor = cursor, lastSync = System.currentTimeMillis() / 1000.0,
                lastSyncError = null, lastAddr = if (addr == RELAY) it.lastAddr else addr, pcName = pcName ?: it.pcName,
                catalog = catalog?.takeIf { c -> c.isNotEmpty() } ?: it.catalog, lastVia = if (addr == RELAY) "internet" else "netz",
                // Neue Adressen des PCs (z. B. neue IP vom Router) übernehmen; bei „Bestimmte/Nur diese“ bleibt die Auswahl.
                addrs = addrs?.filter { a -> ':' in a }?.takeIf { l -> l.isNotEmpty() } ?: it.addrs)
        }
        purgeTombstones()
        reload(if (playlists != null) H or P else H)
    }

    /** Name, den du dem Handy in den Android-Einstellungen gegeben hast (z. B. „Galaxy S23 Ultra“), sonst Hersteller + Modell. */
    fun deviceName(): String =
        runCatching { android.provider.Settings.Global.getString(context.contentResolver, android.provider.Settings.Global.DEVICE_NAME) }
            .getOrNull()?.trim()?.takeIf { it.isNotEmpty() }?.take(60)
            ?: "${Build.MANUFACTURER.replaceFirstChar { it.uppercase() }} ${Build.MODEL}"
}

/** Kennung der Sicherungsdatei. */
const val BACKUP_FORMAT = "sh-tunebridge-handy-sicherung"

/** Playlists, die nur auf dem Handy liegen (ohne PC). */
const val PHONE = "handy"
private const val H = 1
private const val P = 2
/** So viele Einträge hält der Verlauf im Speicher (Suche, Filter, Rückblick). */
private const val HISTORY_MAX = 10_000

/** Offline gemerkte Fingerabdrücke: höchstens so viele, so lange. */
private const val PENDING_MAX = 50
private const val PENDING_DAYS = 30
