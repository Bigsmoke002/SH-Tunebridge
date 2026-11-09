package de.bs002.tunebridge.net

import de.bs002.tunebridge.audio.ShazamSignature
import de.bs002.tunebridge.data.Track
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonElement
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.doubleOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonObject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.io.IOException
import java.util.Locale
import java.util.TimeZone
import java.util.UUID
import kotlin.math.abs

/**
 * Anfrage an Shazam – gleiche Schnittstelle wie die Desktop-App (shazamio). Gesendet wird nur der
 * Fingerabdruck, kein Ton. Shazam nennt keine feste Grenze; [Throttle] sorgt für Abstand.
 */
object Shazam {
    class Busy(message: String, val waitSeconds: Int) : IOException(message)

    data class Hit(
        val track: Track,
        val shazamKey: String?,
        val url: String?,
        val label: String?,
        val year: String?,
        val genres: List<String>,
        val links: Map<String, String>,
        val skew: Double?,
        val offset: Double?,
    )

    private val json = Json { ignoreUnknownKeys = true }
    private const val TAG_URL = "https://amp.shazam.com/discovery/v5/%s/%s/iphone/-/tag/%s/%s" +
        "?sync=true&webv3=true&sampling=true&connected=&shazamapiversion=v3&sharehub=true&hubv5minorversion=v5.1&hidelb=true&video=v3"
    private const val TRACK_URL = "https://amp.shazam.com/discovery/v5/%s/%s/iphone/-/track/%s?shazamapiversion=v3&video=v3"
    private const val USER_AGENT = "Dalvik/2.1.0 (Linux; U; Android 14; SM-S918B Build/UP1A.231005.007)"

    private fun lang() = Locale.getDefault().language.ifBlank { "de" }
    private fun country() = Locale.getDefault().country.ifBlank { "DE" }

    private fun request(url: String) = Request.Builder().url(url)
        .header("User-Agent", USER_AGENT)
        .header("X-Shazam-Platform", "IPHONE")
        .header("X-Shazam-AppVersion", "14.1.0")
        .header("Accept", "*/*")
        .header("Accept-Language", lang())

    suspend fun recognize(sig: ShazamSignature): Hit? = recognize(sig.toUri(), sig.durationMs)

    /** Mit einem schon berechneten Fingerabdruck (z. B. offline gemerkt). */
    suspend fun recognize(uri: String, samplems: Int): Hit? = withContext(Dispatchers.IO) {
        Throttle.acquire()
        val body = buildJsonObject {
            put("timezone", TimeZone.getDefault().id)
            putJsonObject("signature") { put("uri", uri); put("samplems", samplems) }
            put("timestamp", System.currentTimeMillis())
            putJsonObject("context") {}
            putJsonObject("geolocation") {}
        }.toString().toRequestBody("application/json".toMediaType())
        val url = TAG_URL.format(lang(), country(), UUID.randomUUID().toString().uppercase(), UUID.randomUUID().toString().uppercase())
        Http.client.newCall(request(url).post(body).build()).execute().use { r ->
            if (r.code == 429) throw Busy("Shazam bremst gerade (zu viele Anfragen)", Throttle.block(null))
            if (!r.isSuccessful) throw IOException("Shazam antwortet mit Fehler ${r.code}")
            val root = json.parseToJsonElement(r.body!!.string()).jsonObject
            val t = root["track"]?.jsonObject ?: return@withContext null
            val first = (root["matches"] as? JsonArray)?.firstOrNull()?.jsonObject
            parse(t, first)
        }
    }

    /** Song zu einer Shazam-Nummer (z. B. aus einem geteilten Link). */
    suspend fun track(key: String): Hit? = withContext(Dispatchers.IO) {
        Http.client.newCall(request(TRACK_URL.format(lang(), country(), key)).get().build()).execute().use { r ->
            if (r.code == 404) return@withContext null
            if (!r.isSuccessful) throw IOException("Shazam antwortet mit Fehler ${r.code}")
            val t = json.parseToJsonElement(r.body!!.string()).jsonObject
            if (t["title"] == null) null else parse(t, null)
        }
    }

    private fun JsonElement?.str(): String? = (this as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }

    private fun parse(t: JsonObject, match: JsonObject?): Hit {
        val meta = HashMap<String, String>()
        (t["sections"] as? JsonArray)?.forEach { s ->
            (s.jsonObject["metadata"] as? JsonArray)?.forEach { m ->
                val k = m.jsonObject["title"].str(); val v = m.jsonObject["text"].str()
                if (k != null && v != null) meta[k] = v
            }
        }
        val images = t["images"] as? JsonObject
        val hub = t["hub"] as? JsonObject
        val preview = (hub?.get("actions") as? JsonArray)?.mapNotNull { it.jsonObject }
            ?.firstOrNull { it["type"].str() == "uri" && it["uri"].str()?.startsWith("http") == true }?.get("uri").str()
        val links = LinkedHashMap<String, String>()
        t["url"].str()?.let { links["shazam"] = it }
        (hub?.get("providers") as? JsonArray)?.forEach { p ->
            val type = p.jsonObject["type"].str()?.lowercase() ?: return@forEach
            (p.jsonObject["actions"] as? JsonArray)?.forEach { a ->
                val uri = a.jsonObject["uri"].str()
                if (uri != null && (uri.startsWith("https://") || uri.startsWith("spotify:"))) links.putIfAbsent(type, uri)
            }
        }
        val genres = (t["genres"] as? JsonObject)?.values?.mapNotNull { it.str() }.orEmpty()
        val key = t["key"].str()
        val album = meta["Album"]
        val track = Track(
            title = t["title"].str() ?: "?",
            artists = listOfNotNull(t["subtitle"].str()),
            album = album,
            isrc = t["isrc"].str(),
            ids = key?.let { mapOf("shazam" to it) } ?: emptyMap(),
            genre = null,
            cover = images?.get("coverarthq").str() ?: images?.get("coverart").str(),
            previewUrl = preview,
        )
        return Hit(
            track = track, shazamKey = key, url = t["url"].str(),
            label = meta["Label"], year = meta["Released"],
            genres = genres, links = links,
            skew = match?.get("timeskew")?.jsonPrimitive?.doubleOrNull?.let { abs(it) },
            offset = match?.get("offset")?.jsonPrimitive?.doubleOrNull,
        )
    }
}

/** Wie `ratelimit.py` am Desktop: höchstens 10 Anfragen pro Minute, 2 s Abstand, Pause nach Sperre. */
object Throttle {
    private const val PER_MINUTE = 10
    private const val GAP_MS = 2_000L
    private const val PAUSE_S = 90
    private val hits = ArrayDeque<Long>()
    @Volatile private var pausedUntil = 0L

    fun pausedSeconds(): Int = ((pausedUntil - System.currentTimeMillis()) / 1000).toInt().coerceAtLeast(0)

    fun block(retryAfter: Int?): Int {
        val s = retryAfter ?: PAUSE_S
        pausedUntil = System.currentTimeMillis() + s * 1000L
        return s
    }

    @Synchronized
    fun acquire() {
        pausedSeconds().takeIf { it > 0 }?.let { throw Shazam.Busy("Shazam macht eine Pause – wieder frei in $it s", it) }
        val now = System.currentTimeMillis()
        while (hits.isNotEmpty() && now - hits.first() > 60_000) hits.removeFirst()
        if (hits.size >= PER_MINUTE) {
            val wait = ((60_000 - (now - hits.first())) / 1000).toInt() + 1
            throw Shazam.Busy("Gerade viele Anfragen – in $wait s wieder", wait)
        }
        hits.lastOrNull()?.let { last -> (GAP_MS - (now - last)).takeIf { it > 0 }?.let { Thread.sleep(it) } }
        hits.addLast(System.currentTimeMillis())
    }
}
