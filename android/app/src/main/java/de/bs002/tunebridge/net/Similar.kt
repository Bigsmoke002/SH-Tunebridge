package de.bs002.tunebridge.net

import de.bs002.tunebridge.data.Track
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.Request

/**
 * Ähnliche Songs direkt bei Deezer (ohne Key) – wie similar.deezer_similar am PC: Top-Song ähnlicher Künstler,
 * aufgefüllt mit dem Künstler-Radio. Nur nach Einwilligung (Mehr › Datenschutz) und nur, wenn kein PC erreichbar ist.
 */
object Similar {
    private const val PER_ARTIST = 2
    private val json = Json { ignoreUnknownKeys = true }

    private fun get(url: String): JsonObject? =
        Http.client.newCall(Request.Builder().url(url).header("User-Agent", "SH-Tunebridge-Android").build()).execute().use { r ->
            if (!r.isSuccessful) null else json.parseToJsonElement(r.body!!.string()).jsonObject
        }

    private fun data(o: JsonObject?) = (o?.get("data") as? kotlinx.serialization.json.JsonArray)?.map { it.jsonObject }.orEmpty()

    private fun JsonObject.str(k: String) = get(k)?.jsonPrimitive?.contentOrNull

    private fun track(h: JsonObject): Track? {
        val title = h.str("title") ?: return null
        val artist = h["artist"]?.jsonObject?.str("name") ?: return null
        return Track(title = title, artists = listOf(artist), isrc = h.str("isrc"),
            durationMs = h["duration"]?.jsonPrimitive?.longOrNull?.times(1000),
            ids = h.str("id")?.let { mapOf("deezer" to it) }.orEmpty(),
            cover = h["album"]?.jsonObject?.str("cover_medium"),
            previewUrl = h.str("preview")?.takeIf { it.startsWith("http") })
    }

    /** Blockiert – im Hintergrund aufrufen. */
    fun find(seed: Track, limit: Int = 20): List<Pair<Track, Double>> {
        val base = seed.ids["deezer"]?.let { get("https://api.deezer.com/track/$it") }?.takeIf { it["artist"] != null }
            ?: seed.isrc?.let { get("https://api.deezer.com/track/isrc:$it") }?.takeIf { it["artist"] != null }
            ?: run {
                val a = seed.artists.firstOrNull() ?: return emptyList()
                val url = "https://api.deezer.com/search".toHttpUrl().newBuilder()
                    .addQueryParameter("q", "artist:\"$a\" track:\"${seed.title}\"").addQueryParameter("limit", "1").build().toString()
                data(get(url)).firstOrNull()
            } ?: return emptyList()
        val aid = base["artist"]?.jsonObject?.get("id")?.jsonPrimitive?.longOrNull ?: return emptyList()
        val out = ArrayList<Pair<Track, Double>>()
        val seen = hashSetOf(key(seed)); val per = HashMap<String, Int>()
        fun add(t: Track?, m: Double) {
            t ?: return
            val k = key(t); val a = k.substringBefore('|')
            if (k in seen || (per[a] ?: 0) >= PER_ARTIST || out.size >= limit) return
            seen += k; per[a] = (per[a] ?: 0) + 1; out += t to m
        }
        data(get("https://api.deezer.com/artist/$aid/related?limit=10")).take(10).forEachIndexed { i, a ->
            val id = a["id"]?.jsonPrimitive?.longOrNull ?: return@forEachIndexed
            add(data(get("https://api.deezer.com/artist/$id/top?limit=1")).firstOrNull()?.let(::track), 0.85 - i * 0.03)
        }
        if (out.size < limit) data(get("https://api.deezer.com/artist/$aid/radio?limit=40")).forEachIndexed { i, h ->
            if (h["artist"]?.jsonObject?.get("id")?.jsonPrimitive?.longOrNull == aid) return@forEachIndexed
            add(track(h), maxOf(0.3, 0.7 - i * 0.01))
        }
        return out.sortedByDescending { it.second }
    }

    private fun key(t: Track) = "${t.artists.firstOrNull().orEmpty().lowercase().trim()}|${t.title.lowercase().trim()}"
}
