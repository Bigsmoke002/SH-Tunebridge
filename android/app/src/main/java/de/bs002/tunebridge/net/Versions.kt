package de.bs002.tunebridge.net

import de.bs002.tunebridge.data.Track
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.longOrNull
import okhttp3.HttpUrl.Companion.toHttpUrl
import okhttp3.Request
import java.text.Normalizer

/** Eine gefundene Version: Song + Art (siehe [Versions.KINDS]) + Beschriftung („Remix von …“). */
data class Version(val track: Track, val kind: String, val label: String)

data class VersionResult(val core: String, val kinds: List<Pair<String, String>>, val items: List<Version>)

/**
 * Remixe, Covers & andere Versionen eines Songs. Normalerweise rechnet der PC (remixes.py, /phone/v1/versions).
 * Ohne erreichbaren PC – nur nach Einwilligung (Mehr › Datenschutz, wie „Ähnliche Songs“) – fragt die App Deezer direkt.
 * Die Einordnung hier ist eine verkürzte Fassung von remixes.py; die maßgebliche bleibt die am PC.
 */
object Versions {
    val KINDS = listOf("original" to "Original", "remix" to "Remixe", "edit" to "Edits & Mix-Versionen", "live" to "Live",
        "akustik" to "Akustik", "instrumental" to "Instrumental", "tempo" to "Slowed & Sped Up",
        "andere" to "Andere Künstler – gleicher Titel")
    private const val MAX_PER_KIND = 25
    private val json = Json { ignoreUnknownKeys = true }

    private val BRACKET = Regex("""\s*[(\[]([^)\]]*)[)\]]""")
    private val DASH = Regex("""\s+[-–—|]\s+(.+)$""")
    private val FEAT = Regex("""\s*[(\[]?\s*(feat\.?|ft\.?|featuring|with)\s+[^)\]]*[)\]]?""", RegexOption.IGNORE_CASE)
    private val VERSIONISH = Regex("""re-?mix|rmx|bootleg|flip|rework|edit|vip|refix|mash-?up|\bmix\b|version|\bver\.?|live|acoustic|akustik|unplugged|""" +
        """stripped|piano|orchestral|instrumental|remaster|radio|extended|club|\bdub\b|original|mono|stereo|single|album|""" +
        """slowed|sped|speed|nightcore|reverb|8d|bass boosted|cover|demo|session|\d{4}""", RegexOption.IGNORE_CASE)
    private val REMIX = Regex("""\b(re-?mix|rmx|bootleg|flip|rework|re-?edit|vip|refix|mash-?up)\b""", RegexOption.IGNORE_CASE)
    private val LIVE = Regex("""\blive\b|\bin concert\b""", RegexOption.IGNORE_CASE)
    private val ACOUSTIC = Regex("""\bacoustic|\bunplugged\b|\bakustik|\bpiano version\b|\bstripped\b|\borchestral\b""", RegexOption.IGNORE_CASE)
    private val INSTR = Regex("""\binstrumental\b""", RegexOption.IGNORE_CASE)
    private val EDIT = Regex("""\b(radio edit|extended|club mix|dub mix|dub|edit|mix|version|radio)\b""", RegexOption.IGNORE_CASE)
    private val ORIGINAL = Regex("""\b(original mix|original version|remaster(ed)?|album version|single version|mono|stereo)\b""", RegexOption.IGNORE_CASE)
    private val SLOWED = Regex("""slowed|reverb""", RegexOption.IGNORE_CASE)
    private val SPED = Regex("""sped up|speed up|nightcore|\b8d\b|bass boosted""", RegexOption.IGNORE_CASE)
    private val JUNK = Regex("""karaoke|tribute|made famous|in the style of|originally performed|as made popular|cover version of|""" +
        """backing track|cover band|lullaby|rockabye baby|8-?bit|ringtone|workout|tabata|fitness|\bbpm\b""", RegexOption.IGNORE_CASE)
    private val STYLE = Regex("""^(?:(?:deep|tech|future|progressive|tropical|bass|melodic)\s+)?(?:house|techno|hardstyle|hardtekk|tekk|""" +
        """trance|psy|phonk|trap|drill|dubstep|dnb|edm|dance|club|disco|lo-?fi|jersey|amapiano|reggaeton|afro|garage|hyperpop|""" +
        """slap|bootleg|workout|extended|radio|official|original|the|festival|mashup|vip|remix)$""", RegexOption.IGNORE_CASE)

    private fun norm(s: String) = Normalizer.normalize(s, Normalizer.Form.NFKD).replace(Regex("\\p{M}+"), "").lowercase()
        .replace("&", " and ").replace(Regex("[^a-z0-9]+"), "")

    private fun parts(title: String): Pair<String, List<String>> {
        val p = ArrayList<String>()
        var t = BRACKET.replace(title) { m -> if (VERSIONISH.containsMatchIn(m.groupValues[1])) { p += m.groupValues[1].trim(); "" } else m.value }
        DASH.find(t)?.let { m -> if (VERSIONISH.containsMatchIn(m.groupValues[1])) { p += m.groupValues[1].trim(); t = t.substring(0, m.range.first) } }
        return t.trim() to p
    }

    fun coreTitle(title: String): String = parts(FEAT.replace(title, "")).first.ifBlank { title.trim() }

    private fun versionText(title: String, version: String): String {
        val p = parts(FEAT.replace(title, "")).second.toMutableList()
        if (version.isNotBlank() && VERSIONISH.containsMatchIn(version)) p += version.trim('(', ')', '[', ']', ' ')
        return p.filter { it.isNotBlank() }.distinct().joinToString(" · ")
    }

    private fun sameArtist(a: String, seed: String): Boolean {
        val na = norm(a); val ns = norm(seed)
        return na.isNotEmpty() && ns.isNotEmpty() && (na == ns || ns in na || na in ns)
    }

    private fun remixLabel(v: String): String {
        for (part in v.split(Regex("""\s*·\s*"""))) {
            val m = Regex("""^(.*?)\s*(?:re-?mix|rmx|bootleg|flip|rework|re-?edit|vip mix|vip|refix)\b""", RegexOption.IGNORE_CASE).find(part) ?: continue
            var name = m.groupValues[1].trim(' ', '-', '–').replace(Regex("""\s+(extended|radio|club|edit|official)$""", RegexOption.IGNORE_CASE), "").trim()
            if ("'s" in name) name = name.substringBefore("'s").trim()
            if (name.isEmpty()) continue
            return if (STYLE.matches(name)) "${name.replaceFirstChar { it.uppercase() }}-Remix" else "Remix von $name"
        }
        return "Remix"
    }

    fun classify(title: String, version: String, artist: String, seed: String): Pair<String, String> {
        val v = versionText(title, version)
        val same = sameArtist(artist, seed) ||
            (seed.isNotBlank() && norm(seed) in norm(title) && !Regex("cover|reprise|tribute|style", RegexOption.IGNORE_CASE).containsMatchIn(title))
        if (v.isNotEmpty() && SPED.containsMatchIn(v)) return "tempo" to "Sped Up"
        if (v.isNotEmpty() && SLOWED.containsMatchIn(v)) return "tempo" to "Slowed + Reverb"
        if (REMIX.containsMatchIn(v)) {
            val l = remixLabel(v)
            return if (same) "remix" to l else "andere" to (if (l.startsWith("Remix von")) l else "$l · $artist")
        }
        if (LIVE.containsMatchIn(v)) return if (same) "live" to v else "andere" to "Live von $artist"
        if (ACOUSTIC.containsMatchIn(v)) return if (same) "akustik" to v else "andere" to "Akustik-Version von $artist"
        if (INSTR.containsMatchIn(v)) return if (same) "instrumental" to v else "andere" to "Instrumental von $artist"
        if (v.isNotEmpty() && EDIT.containsMatchIn(v) && !ORIGINAL.containsMatchIn(v)) return if (same) "edit" to v else "andere" to "$v · $artist"
        return if (same) "original" to v.ifEmpty { "Original" } else "andere" to "Cover oder gleichnamiger Song von $artist"
    }

    private fun search(q: String, limit: Int): List<JsonObject> {
        val url = "https://api.deezer.com/search".toHttpUrl().newBuilder().addQueryParameter("q", q).addQueryParameter("limit", "$limit").build()
        return Http.client.newCall(Request.Builder().url(url).header("User-Agent", "SH-Tunebridge-Android").build()).execute().use { r ->
            if (!r.isSuccessful) emptyList()
            else (json.parseToJsonElement(r.body!!.string()).jsonObject["data"] as? JsonArray)?.map { it.jsonObject }.orEmpty()
        }
    }

    private fun JsonObject.str(k: String) = get(k)?.jsonPrimitive?.contentOrNull

    /** Direkt bei Deezer (nur nach Einwilligung). Blockiert – im Hintergrund aufrufen. */
    fun find(seed: Track): VersionResult {
        val core = coreTitle(seed.title)
        val seedArtist = seed.artists.firstOrNull().orEmpty().split(Regex("""\s*(,|&| x | feat\.? | ft\.? )\s*""", RegexOption.IGNORE_CASE)).first().trim()
        val want = norm(core)
        val queries = buildList {
            if (seedArtist.isNotEmpty()) { add("artist:\"$seedArtist\" track:\"$core\"" to 50); add("$seedArtist $core remix" to 50) }
            add("track:\"$core\"" to 100); add("$core remix" to 50)
        }
        data class Hit(val v: Version, val rank: Long)
        val seen = LinkedHashMap<String, Hit>()
        for ((q, n) in queries) for (h in runCatching { search(q, n) }.getOrDefault(emptyList())) {
            val t = h.str("title") ?: continue
            val art = h["artist"]?.jsonObject?.str("name") ?: continue
            val alb = h["album"] as? JsonObject
            if (JUNK.containsMatchIn("$t $art ${alb?.str("title").orEmpty()}")) continue
            if (norm(coreTitle(h.str("title_short") ?: t)) != want) continue
            val (kind, label) = classify(t, h.str("title_version").orEmpty(), art, seedArtist)
            val rank = h["rank"]?.jsonPrimitive?.longOrNull ?: 0
            val k = "${norm(art)}|${norm(t)}"
            if ((seen[k]?.rank ?: -1) >= rank) continue
            val track = Track(title = t, artists = listOf(art), album = alb?.str("title"),
                durationMs = h["duration"]?.jsonPrimitive?.longOrNull?.times(1000)?.takeIf { it > 0 },
                ids = h.str("id")?.let { mapOf("deezer" to it) }.orEmpty(), cover = alb?.str("cover_medium"))
            seen[k] = Hit(Version(track, kind, label), rank)
        }
        val byKind = seen.values.groupBy { it.v.kind }
        val ref = seed.durationMs ?: byKind["original"]?.sortedByDescending { it.rank }?.firstNotNullOfOrNull { it.v.track.durationMs }
        fun plausible(h: Hit): Boolean {
            if (h.v.label.startsWith("Remix") || "-Remix" in h.v.label) return true
            val d = h.v.track.durationMs
            return if (ref != null) d != null && kotlin.math.abs(d - ref) <= ref * 0.35 else want.length >= 8
        }
        val items = KINDS.flatMap { (k, _) ->
            byKind[k].orEmpty().filter { k != "andere" || plausible(it) }.sortedByDescending { it.rank }.take(MAX_PER_KIND).map { it.v }
        }.take(80)
        return VersionResult(core, KINDS, items)
    }
}
