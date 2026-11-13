package de.bs002.tunebridge.net

import de.bs002.tunebridge.App
import de.bs002.tunebridge.data.Track
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.KSerializer
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.Request

// Felder wie discover/ am PC (gleiche JSON-Namen), damit PC-Antwort und Direktabfrage dieselben Klassen füllen.
// Kennungen sind Text mit Quelle: „dz:123“ (Deezer), „it:…“ (Apple), „mb:…“ (MusicBrainz), „dg:…“ (Discogs), „lf:…“ (Last.fm).
@Serializable
data class DTrack(
    val title: String, val artists: List<String> = emptyList(),
    @SerialName("artist_ids") val artistIds: List<String?> = emptyList(),
    val album: String? = null, @SerialName("album_id") val albumId: String? = null, val cover: String? = null,
    @SerialName("duration_ms") val durationMs: Long? = null, val rank: Long = 0, val explicit: Boolean = false,
    val isrc: String? = null, val ids: Map<String, String> = emptyMap(), val with: List<String> = emptyList(),
    @SerialName("preview_url") val previewUrl: String? = null, val link: String? = null, val sources: List<String> = emptyList(),
) {
    /** Als Song der App (zum Speichern) – Hörprobe holt der Player frisch über die Deezer-ID bzw. die Suche. */
    fun toTrack() = Track(title = title, artists = artists, album = album, durationMs = durationMs, isrc = isrc,
        ids = ids.filterKeys { it in KEEP_IDS }, cover = cover?.takeIf { it.startsWith("https://") },
        previewUrl = previewUrl?.takeIf { it.startsWith("https://") })

    /** Zum Abspielen: ohne eigene Hörprobe sucht der Player sie bei Deezer (Künstler + Titel). */
    fun toPlayable() = toTrack().let { t -> if (t.previewUrl == null && t.ids["deezer"] == null && t.isrc == null) t.copy(previewUrl = "deezer:suche") else t }

    companion object { val KEEP_IDS = setOf("deezer", "apple", "musicbrainz") }
}

@Serializable
data class DArtist(
    val id: String, val name: String, val picture: String? = null, val fans: Long? = null, val albums: Int? = null,
    val note: String? = null, @SerialName("picture_big") val pictureBig: String? = null, val link: String? = null,
    val refs: Map<String, String> = emptyMap(), val sources: List<String> = emptyList(),
    val links: Map<String, String> = emptyMap(), val tags: List<String> = emptyList(), val life: String? = null, val plays: Long? = null,
) {
    /** Kennungen der anderen Quellen (für die Künstlerseite). */
    val also: List<String> get() = refs.values.filter { it != id }
}

@Serializable
data class DAlbum(
    val id: String, val title: String, val artist: String? = null, @SerialName("artist_id") val artistId: String? = null,
    val cover: String? = null, val year: String? = null, val type: String = "", val tracks: Int? = null, val explicit: Boolean = false,
    @SerialName("cover_big") val coverBig: String? = null, val label: String? = null, val date: String? = null,
    @SerialName("duration_ms") val durationMs: Long? = null, val genres: List<String> = emptyList(),
    val artists: List<String> = emptyList(), val link: String? = null, val links: Map<String, String> = emptyMap(),
    val sources: List<String> = emptyList(),
)

@Serializable
data class DSearch(val q: String = "", val tracks: List<DTrack> = emptyList(), val artists: List<DArtist> = emptyList(),
                   val albums: List<DAlbum> = emptyList(), val sources: List<String> = emptyList(),
                   val failed: Map<String, String> = emptyMap())

@Serializable
data class DArtistSearch(val q: String = "", val items: List<DArtist> = emptyList())

@Serializable
data class DArtistPage(val artist: DArtist, val top: List<DTrack> = emptyList(), val albums: List<DAlbum> = emptyList(),
                       val singles: List<DAlbum> = emptyList(), val related: List<DArtist> = emptyList(),
                       val sources: List<String> = emptyList(), val failed: Map<String, String> = emptyMap())

@Serializable
data class DAlbumPage(val album: DAlbum, val tracks: List<DTrack> = emptyList(), val sources: List<String> = emptyList())

@Serializable
data class DCharts(val source: String = "deezer", val genre: String = "", val tracks: List<DTrack> = emptyList(),
                   val artists: List<DArtist> = emptyList(), val albums: List<DAlbum> = emptyList())

@Serializable
data class DGenre(val id: String, val name: String = "", val picture: String? = null)

@Serializable
data class DChartSource(val id: String, val name: String)

@Serializable
data class DGenres(val source: String = "deezer", val genres: List<DGenre> = emptyList(), val charts: List<DChartSource> = emptyList())

/** Kürzel und Namen der Quellen (wie am PC). */
val DSOURCES = mapOf("deezer" to ("D" to "Deezer"), "apple" to ("A" to "Apple Music"), "musicbrainz" to ("MB" to "MusicBrainz"),
    "discogs" to ("DG" to "Discogs"), "lastfm" to ("LF" to "Last.fm"))

/** Kein PC erreichbar und keine Einwilligung für Deezer direkt. */
class DiscoverNeedsConsent : Exception("Kein PC erreichbar")

/** Ergebnis + Herkunft („vom PC“ / „von Deezer“). */
data class Got<T>(val from: String, val value: T)

/**
 * „Entdecken“: im Deezer-Katalog stöbern. Normalerweise fragt der PC (discover.py, /phone/v1/discover).
 * Ohne erreichbaren PC – nur nach Einwilligung (Mehr › Datenschutz, wie „Ähnliche Songs“) – fragt die App Deezer direkt.
 * Gesendet wird nur der Suchbegriff bzw. die Deezer-Kennung; Ergebnisse bleiben nur im Arbeitsspeicher (1 Stunde).
 */
object Discover {
    private val json = Json { ignoreUnknownKeys = true; coerceInputValues = true }
    private const val TTL = 3_600_000L
    private val ram = LinkedHashMap<String, Pair<Long, Any>>()
    private val NO_MUSIC = setOf(457L)                       // Hörbücher
    private val RECORD = mapOf("album" to "Album", "single" to "Single", "ep" to "EP", "compile" to "Zusammenstellung")

    // ---------------------------------------------------------------- Quelle wählen
    private suspend fun <T> fetch(what: String, arg: String?, kind: String?, ser: KSerializer<T>, source: String? = null,
                                  also: List<String> = emptyList(), direct: () -> T): Got<T> {
        val pc = App.sync.discover(what, arg, kind, source, also)
        if (pc != null) return Got("vom PC", json.decodeFromString(ser, pc))
        if (!App.repo.settings.value.similarDirect) throw DiscoverNeedsConsent()
        return Got("von Deezer", withContext(Dispatchers.IO) { direct() })
    }

    private fun clean(q: String) = q.replace(Regex("""\s+"""), " ").trim().take(100)

    /** Ohne PC gibt es nur Deezer – Kennungen anderer Quellen gehen nur über den PC. */
    private fun dz(id: String): Long = id.removePrefix("dz:").takeIf { it.length <= 15 }?.toLongOrNull()
        ?: throw IllegalStateException("Diese Quelle geht nur über den PC – ohne PC fragt die App nur Deezer")

    suspend fun search(q: String): Got<DSearch> = fetch("search", clean(q), "all", DSearch.serializer()) { searchAll(clean(q)) }
    suspend fun artists(q: String): Got<DArtistSearch> =
        fetch("search", clean(q), "artist", DArtistSearch.serializer()) { DArtistSearch(clean(q), searchKind(clean(q), "artist", 10, ::artist)) }
    suspend fun artist(id: String, also: List<String> = emptyList()): Got<DArtistPage> =
        fetch("artist", id, null, DArtistPage.serializer(), also = also.take(5)) { artistPage(dz(id)) }
    suspend fun album(id: String): Got<DAlbumPage> = fetch("album", id, null, DAlbumPage.serializer()) { albumPage(dz(id)) }
    suspend fun charts(source: String, genre: String): Got<DCharts> = fetch("charts", genre, null, DCharts.serializer(), source) {
        if (source != "deezer") throw IllegalStateException("Diese Charts gibt es nur über den PC")
        charts0(genre.ifBlank { "0" }.toLongOrNull() ?: 0L)
    }
    suspend fun genres(source: String): Got<DGenres> = fetch("genres", null, null, DGenres.serializer(), source) {
        DGenres("deezer", if (source == "deezer") genres0() else emptyList(), listOf(DChartSource("deezer", "Deezer")))
    }

    /** Künstler zu einem Namen (für die Interpreten eines Songs): gleicher Name bevorzugt, sonst bester Treffer. */
    suspend fun artistByName(name: String): DArtist? {
        val items = artists(name).value.items
        val n = name.trim().lowercase()
        return items.firstOrNull { it.name.trim().lowercase() == n } ?: items.firstOrNull()
    }

    // ---------------------------------------------------------------- Deezer direkt (Kurzfassung von discover/deezer.py)
    @Suppress("UNCHECKED_CAST")
    private fun <T : Any> cached(key: String, fn: () -> T): T {
        synchronized(ram) { ram[key]?.let { (at, v) -> if (System.currentTimeMillis() - at < TTL) return v as T } }
        val v = fn()
        synchronized(ram) {
            if (ram.size > 200) ram.keys.take(80).toList().forEach { ram.remove(it) }
            ram[key] = System.currentTimeMillis() to v
        }
        return v
    }

    private fun get(path: String, vararg params: Pair<String, String>): JsonObject {
        val url = "https://api.deezer.com/$path".toHttpUrl().newBuilder().apply { params.forEach { (k, v) -> addQueryParameter(k, v) } }.build()
        return Http.client.newCall(Request.Builder().url(url).header("User-Agent", "SH-Tunebridge-Android").build()).execute().use { r ->
            if (!r.isSuccessful) throw IllegalStateException("Deezer antwortet mit Fehler ${r.code}")
            json.parseToJsonElement(r.body!!.string()).jsonObject
        }
    }

    private fun JsonObject.str(k: String) = (get(k) as? kotlinx.serialization.json.JsonPrimitive)?.contentOrNull
    private fun JsonObject.long(k: String) = (get(k) as? kotlinx.serialization.json.JsonPrimitive)?.longOrNull
    private fun JsonObject.obj(k: String) = get(k) as? JsonObject
    private fun JsonObject.data(): List<JsonObject> = (get("data") as? JsonArray)?.mapNotNull { it as? JsonObject }.orEmpty()
    private fun ref(id: Long?) = id?.let { "dz:$it" }
    private val SRC = listOf("deezer")

    private fun track(t: JsonObject, album: JsonObject? = null, aid: Long? = null): DTrack? {
        val id = t.long("id") ?: return null
        val title = t.str("title") ?: t.str("title_short") ?: return null
        val alb = t.obj("album") ?: album
        val art = t.obj("artist")
        val people = ((t.get("contributors") as? JsonArray)?.mapNotNull { it as? JsonObject }?.filter { it.str("name") != null })
            ?.takeIf { it.isNotEmpty() } ?: listOfNotNull(art?.takeIf { it.str("name") != null })
        return DTrack(title = title, artists = people.map { it.str("name")!! }, artistIds = people.map { ref(it.long("id")) },
            album = alb?.str("title"), albumId = ref(alb?.long("id")), cover = alb?.str("cover_medium") ?: album?.str("cover_medium"),
            durationMs = t.long("duration")?.takeIf { it > 0 }?.times(1000), rank = t.long("rank") ?: 0,
            explicit = t["explicit_lyrics"]?.jsonPrimitive?.contentOrNull == "true", isrc = t.str("isrc"),
            ids = mapOf("deezer" to "$id"), link = t.str("link"), sources = SRC,
            with = if (aid == null) emptyList() else people.filter { it.long("id") != aid }.map { it.str("name")!! })
    }

    private fun artist(a: JsonObject): DArtist? {
        val id = ref(a.long("id")) ?: return null
        return DArtist(id, a.str("name") ?: return null, a.str("picture_medium"), a.long("nb_fan"), a["nb_album"]?.jsonPrimitive?.intOrNull,
            link = a.str("link"), refs = mapOf("deezer" to id), sources = SRC)
    }

    private fun album(a: JsonObject, fallbackArtist: JsonObject? = null): DAlbum? {
        val id = ref(a.long("id")) ?: return null
        val art = a.obj("artist") ?: fallbackArtist
        return DAlbum(id, a.str("title") ?: return null, art?.str("name"), ref(art?.long("id")), a.str("cover_medium"),
            a.str("release_date")?.take(4)?.takeIf { it.isNotBlank() }, RECORD[a.str("record_type").orEmpty()].orEmpty(),
            a["nb_tracks"]?.jsonPrimitive?.intOrNull, a["explicit_lyrics"]?.jsonPrimitive?.contentOrNull == "true",
            link = a.str("link"), sources = SRC)
    }

    private fun <T> searchKind(q: String, kind: String, limit: Int, fn: (JsonObject) -> T?): List<T> {
        if (q.isEmpty()) return emptyList()
        val data = cached("s:$kind:${q.lowercase()}:$limit") { get("search/$kind", "q" to q, "limit" to "$limit").data() }
        return data.mapNotNull(fn)
    }

    private fun searchAll(q: String) = DSearch(q, searchKind(q, "track", 20) { track(it) }, searchKind(q, "artist", 8, ::artist),
        searchKind(q, "album", 10) { album(it) }, SRC)

    private fun artistPage(aid: Long): DArtistPage = cached("a:$aid") {
        val a = get("artist/$aid")
        if ("error" in a || a.long("id") == null) throw NoSuchElementException("Künstler bei Deezer nicht gefunden")
        val seen = HashSet<String>()
        val top = get("artist/$aid/top", "limit" to "50").data().mapNotNull { track(it, aid = aid) }
            .filter { seen.add(it.title.lowercase() + "|" + it.artists.joinToString { n -> n.lowercase() }) }
        val self = kotlinx.serialization.json.buildJsonObject {
            put("id", kotlinx.serialization.json.JsonPrimitive(aid)); put("name", a["name"] ?: kotlinx.serialization.json.JsonPrimitive(""))
        }
        val alb = get("artist/$aid/albums", "limit" to "100").data().mapNotNull { album(it, self) }.sortedByDescending { it.year.orEmpty() }
        val me = artist(a)!!.let { it.copy(pictureBig = a.str("picture_xl") ?: a.str("picture_big"), links = listOfNotNull(it.link?.let { l -> "deezer" to l }).toMap()) }
        DArtistPage(me, top, alb.filter { it.type != "Single" && it.type != "EP" }, alb.filter { it.type == "Single" || it.type == "EP" },
            get("artist/$aid/related", "limit" to "20").data().mapNotNull(::artist), SRC)
    }

    private fun albumPage(alid: Long): DAlbumPage = cached("al:$alid") {
        val a = get("album/$alid")
        if ("error" in a || a.long("id") == null) throw NoSuchElementException("Album bei Deezer nicht gefunden")
        val base = album(a)!!
        val people = (a["contributors"] as? JsonArray)?.mapNotNull { (it as? JsonObject)?.str("name") }.orEmpty()
        DAlbumPage(base.copy(coverBig = a.str("cover_xl") ?: a.str("cover_big"), label = a.str("label"), date = a.str("release_date"),
            durationMs = a.long("duration")?.takeIf { it > 0 }?.times(1000),
            genres = a.obj("genres")?.data()?.mapNotNull { it.str("name") }.orEmpty(),
            artists = people.ifEmpty { listOfNotNull(base.artist) }, links = listOfNotNull(base.link?.let { "deezer" to it }).toMap()),
            a.obj("tracks")?.data()?.mapNotNull { track(it, album = a) }.orEmpty(), SRC)
    }

    private fun genres0(): List<DGenre> = cached("genres") {
        get("genre").data().mapNotNull { g -> g.long("id")?.takeIf { it !in NO_MUSIC }?.let { DGenre("$it", g.str("name").orEmpty(), g.str("picture_medium")) } }
    }

    private fun charts0(gid: Long): DCharts = cached("c:$gid") {
        DCharts("deezer", "$gid", get("chart/$gid/tracks", "limit" to "50").also { if ("error" in it) throw NoSuchElementException("Charts bei Deezer nicht gefunden") }
            .data().mapNotNull { track(it) },
            get("chart/$gid/artists", "limit" to "20").data().mapNotNull(::artist),
            get("chart/$gid/albums", "limit" to "20").data().mapNotNull { album(it) })
    }
}
