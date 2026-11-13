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

// Felder wie discover.py am PC (gleiche JSON-Namen), damit PC-Antwort und Direktabfrage dieselben Klassen füllen.
@Serializable
data class DTrack(
    val title: String, val artists: List<String> = emptyList(),
    @SerialName("artist_ids") val artistIds: List<Long?> = emptyList(), @SerialName("artist_id") val artistId: Long? = null,
    val album: String? = null, @SerialName("album_id") val albumId: Long? = null, val cover: String? = null,
    @SerialName("duration_ms") val durationMs: Long? = null, val rank: Long = 0, val explicit: Boolean = false,
    val isrc: String? = null, val ids: Map<String, String> = emptyMap(), val with: List<String> = emptyList(),
) {
    /** Als Song der App – die Hörprobe holt der Player frisch über die Deezer-ID. */
    fun toTrack() = Track(title = title, artists = artists, album = album, durationMs = durationMs, isrc = isrc, ids = ids,
        cover = cover?.takeIf { it.startsWith("https://") })
}

@Serializable
data class DArtist(
    val id: Long, val name: String, val picture: String? = null, val fans: Long? = null, val albums: Int? = null,
    @SerialName("picture_big") val pictureBig: String? = null, val link: String? = null,
)

@Serializable
data class DAlbum(
    val id: Long, val title: String, val artist: String? = null, @SerialName("artist_id") val artistId: Long? = null,
    val cover: String? = null, val year: String? = null, val type: String = "", val tracks: Int? = null, val explicit: Boolean = false,
    @SerialName("cover_big") val coverBig: String? = null, val label: String? = null, val date: String? = null,
    @SerialName("duration_ms") val durationMs: Long? = null, val genres: List<String> = emptyList(),
    val artists: List<String> = emptyList(), val link: String? = null,
)

@Serializable
data class DSearch(val q: String = "", val tracks: List<DTrack> = emptyList(), val artists: List<DArtist> = emptyList(),
                   val albums: List<DAlbum> = emptyList())

@Serializable
data class DArtistSearch(val q: String = "", val items: List<DArtist> = emptyList())

@Serializable
data class DArtistPage(val artist: DArtist, val top: List<DTrack> = emptyList(), val albums: List<DAlbum> = emptyList(),
                       val singles: List<DAlbum> = emptyList(), val related: List<DArtist> = emptyList())

@Serializable
data class DAlbumPage(val album: DAlbum, val tracks: List<DTrack> = emptyList())

@Serializable
data class DCharts(val genre: Long = 0, val tracks: List<DTrack> = emptyList(), val artists: List<DArtist> = emptyList(),
                   val albums: List<DAlbum> = emptyList())

@Serializable
data class DGenre(val id: Long, val name: String = "", val picture: String? = null)

@Serializable
data class DGenres(val genres: List<DGenre> = emptyList())

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
    private suspend fun <T> fetch(what: String, arg: String?, kind: String?, ser: KSerializer<T>, direct: () -> T): Got<T> {
        val pc = App.sync.discover(what, arg, kind)
        if (pc != null) return Got("vom PC", json.decodeFromString(ser, pc))
        if (!App.repo.settings.value.similarDirect) throw DiscoverNeedsConsent()
        return Got("von Deezer", withContext(Dispatchers.IO) { direct() })
    }

    private fun clean(q: String) = q.replace(Regex("""\s+"""), " ").trim().take(100)

    suspend fun search(q: String): Got<DSearch> = fetch("search", clean(q), "all", DSearch.serializer()) { searchAll(clean(q)) }
    suspend fun artists(q: String): Got<DArtistSearch> =
        fetch("search", clean(q), "artist", DArtistSearch.serializer()) { DArtistSearch(clean(q), searchKind(clean(q), "artist", 10, ::artist)) }
    suspend fun artist(id: Long): Got<DArtistPage> = fetch("artist", "$id", null, DArtistPage.serializer()) { artistPage(id) }
    suspend fun album(id: Long): Got<DAlbumPage> = fetch("album", "$id", null, DAlbumPage.serializer()) { albumPage(id) }
    suspend fun charts(genre: Long): Got<DCharts> = fetch("charts", "$genre", null, DCharts.serializer()) { charts0(genre) }
    suspend fun genres(): Got<DGenres> = fetch("genres", null, null, DGenres.serializer()) { DGenres(genres0()) }

    /** Künstler zu einem Namen (für die Interpreten eines Songs): gleicher Name bevorzugt, sonst bester Treffer. */
    suspend fun artistByName(name: String): Long? {
        val items = artists(name).value.items
        val n = name.trim().lowercase()
        return (items.firstOrNull { it.name.trim().lowercase() == n } ?: items.firstOrNull())?.id
    }

    // ---------------------------------------------------------------- Deezer direkt (Kurzfassung von discover.py)
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

    private fun track(t: JsonObject, album: JsonObject? = null, aid: Long? = null): DTrack? {
        val id = t.long("id") ?: return null
        val title = t.str("title") ?: t.str("title_short") ?: return null
        val alb = t.obj("album") ?: album
        val art = t.obj("artist")
        val people = ((t.get("contributors") as? JsonArray)?.mapNotNull { it as? JsonObject }?.filter { it.str("name") != null })
            ?.takeIf { it.isNotEmpty() } ?: listOfNotNull(art?.takeIf { it.str("name") != null })
        val names = people.map { it.str("name")!! }
        return DTrack(title = title, artists = names, artistIds = people.map { it.long("id") }, artistId = art?.long("id"),
            album = alb?.str("title"), albumId = alb?.long("id"), cover = alb?.str("cover_medium") ?: album?.str("cover_medium"),
            durationMs = t.long("duration")?.takeIf { it > 0 }?.times(1000), rank = t.long("rank") ?: 0,
            explicit = t["explicit_lyrics"]?.jsonPrimitive?.contentOrNull == "true", isrc = t.str("isrc"),
            ids = mapOf("deezer" to "$id"),
            with = if (aid == null) emptyList() else people.filter { it.long("id") != aid }.map { it.str("name")!! })
    }

    private fun artist(a: JsonObject): DArtist? {
        val id = a.long("id") ?: return null
        return DArtist(id, a.str("name") ?: return null, a.str("picture_medium"), a.long("nb_fan"), a["nb_album"]?.jsonPrimitive?.intOrNull)
    }

    private fun album(a: JsonObject, fallbackArtist: JsonObject? = null): DAlbum? {
        val id = a.long("id") ?: return null
        val art = a.obj("artist") ?: fallbackArtist
        return DAlbum(id, a.str("title") ?: return null, art?.str("name"), art?.long("id"), a.str("cover_medium"),
            a.str("release_date")?.take(4)?.takeIf { it.isNotBlank() }, RECORD[a.str("record_type").orEmpty()].orEmpty(),
            a["nb_tracks"]?.jsonPrimitive?.intOrNull, a["explicit_lyrics"]?.jsonPrimitive?.contentOrNull == "true")
    }

    private fun <T> searchKind(q: String, kind: String, limit: Int, fn: (JsonObject) -> T?): List<T> {
        if (q.isEmpty()) return emptyList()
        val data = cached("s:$kind:${q.lowercase()}:$limit") { get("search/$kind", "q" to q, "limit" to "$limit").data() }
        return data.mapNotNull(fn)
    }

    private fun searchAll(q: String) = DSearch(q, searchKind(q, "track", 20) { track(it) }, searchKind(q, "artist", 8, ::artist),
        searchKind(q, "album", 10) { album(it) })

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
        val me = artist(a)!!.copy(pictureBig = a.str("picture_xl") ?: a.str("picture_big"), link = a.str("link"))
        DArtistPage(me, top, alb.filter { it.type == "Album" || it.type == "Zusammenstellung" },
            alb.filter { it.type == "Single" || it.type == "EP" || it.type.isEmpty() },
            get("artist/$aid/related", "limit" to "20").data().mapNotNull(::artist))
    }

    private fun albumPage(alid: Long): DAlbumPage = cached("al:$alid") {
        val a = get("album/$alid")
        if ("error" in a || a.long("id") == null) throw NoSuchElementException("Album bei Deezer nicht gefunden")
        val base = album(a)!!
        val people = (a["contributors"] as? JsonArray)?.mapNotNull { (it as? JsonObject)?.str("name") }.orEmpty()
        DAlbumPage(base.copy(coverBig = a.str("cover_xl") ?: a.str("cover_big"), label = a.str("label"), date = a.str("release_date"),
            durationMs = a.long("duration")?.takeIf { it > 0 }?.times(1000),
            genres = a.obj("genres")?.data()?.mapNotNull { it.str("name") }.orEmpty(),
            artists = people.ifEmpty { listOfNotNull(base.artist) }, link = a.str("link")),
            a.obj("tracks")?.data()?.mapNotNull { track(it, album = a) }.orEmpty())
    }

    private fun genres0(): List<DGenre> = cached("genres") {
        get("genre").data().mapNotNull { g -> g.long("id")?.takeIf { it !in NO_MUSIC }?.let { DGenre(it, g.str("name").orEmpty(), g.str("picture_medium")) } }
    }

    private fun charts0(gid: Long): DCharts = cached("c:$gid") {
        DCharts(gid, get("chart/$gid/tracks", "limit" to "50").also { if ("error" in it) throw NoSuchElementException("Charts bei Deezer nicht gefunden") }
            .data().mapNotNull { track(it) },
            get("chart/$gid/artists", "limit" to "20").data().mapNotNull(::artist),
            get("chart/$gid/albums", "limit" to "20").data().mapNotNull { album(it) })
    }
}
