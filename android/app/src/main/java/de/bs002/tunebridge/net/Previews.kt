package de.bs002.tunebridge.net

import de.bs002.tunebridge.data.Track
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.contentOrNull
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.Request

/**
 * Aktuelle Adresse der offiziellen 30-s-Hörprobe – wie preview.py am PC. Deezer-Links sind signiert und laufen
 * ab (…hdnea=exp=…); dann fragt die App bei Deezer nach einer frischen Adresse: per Deezer-Nummer, sonst ISRC,
 * sonst Künstler + Titel. Nur beim Abspielen, nur die Adresse im Arbeitsspeicher – gestreamt wird direkt vom Anbieter.
 */
object Previews {
    private val json = Json { ignoreUnknownKeys = true }
    private val ram = HashMap<String, Pair<Long, String>>()     // Schlüssel -> (gültig bis ms, Adresse)

    private fun expires(url: String): Long =
        Regex("""exp=(\d{9,11})""").find(url)?.groupValues?.get(1)?.toLong()?.let { it * 1000 - 60_000 }
            ?: (System.currentTimeMillis() + 30 * 60_000)

    private fun isDeezer(url: String) = "dzcdn" in url || "deezer" in url

    /** Abspielbare Adresse oder null (dann gibt es für diesen Song keine Hörprobe). Blockiert – im Hintergrund aufrufen. */
    fun resolve(t: Track): String? {
        val stored = t.previewUrl?.takeIf { it.startsWith("http") }
        if (stored != null && (!isDeezer(stored) || expires(stored) > System.currentTimeMillis())) return stored
        val key = t.key
        synchronized(ram) { ram[key]?.let { (until, url) -> if (until > System.currentTimeMillis()) return url } }
        val fresh = runCatching { fresh(t) }.getOrNull() ?: return null
        synchronized(ram) {
            if (ram.size > 500) ram.clear()
            ram[key] = minOf(expires(fresh), System.currentTimeMillis() + 30 * 60_000) to fresh
        }
        return fresh
    }

    private fun get(url: String): kotlinx.serialization.json.JsonObject? =
        Http.client.newCall(Request.Builder().url(url).header("User-Agent", "SH-Tunebridge-Android").build()).execute().use { r ->
            if (!r.isSuccessful) null else json.parseToJsonElement(r.body!!.string()).jsonObject
        }

    private fun preview(o: kotlinx.serialization.json.JsonObject?): String? =
        o?.get("preview")?.jsonPrimitive?.contentOrNull?.takeIf { it.startsWith("http") }

    private fun fresh(t: Track): String? {
        t.ids["deezer"]?.let { id -> preview(get("https://api.deezer.com/track/$id"))?.let { return it } }
        t.isrc?.let { isrc -> preview(get("https://api.deezer.com/track/isrc:$isrc"))?.let { return it } }
        val artist = t.artists.firstOrNull() ?: return null
        val url = "https://api.deezer.com/search".toHttpUrl().newBuilder()
            .addQueryParameter("q", "artist:\"$artist\" track:\"${t.title}\"").addQueryParameter("limit", "3").build().toString()
        val data = get(url)?.get("data")?.jsonArray ?: return null
        return data.firstNotNullOfOrNull { preview(it.jsonObject) }
    }
}
