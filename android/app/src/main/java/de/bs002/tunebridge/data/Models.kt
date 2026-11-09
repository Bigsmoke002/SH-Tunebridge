package de.bs002.tunebridge.data

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonObject

/** Gleiches Format wie `Track` der Desktop-App (models.py) – so geht nichts verloren, wenn PC und Handy abgleichen. */
@Serializable
data class Track(
    val title: String,
    val artists: List<String> = emptyList(),
    val album: String? = null,
    @SerialName("duration_ms") val durationMs: Long? = null,
    val isrc: String? = null,
    val ids: Map<String, String> = emptyMap(),
    val tags: Map<String, Double> = emptyMap(),
    val genre: String? = null,
    val subgenre: String? = null,
    val niche: String? = null,
    val cover: String? = null,
    @SerialName("preview_url") val previewUrl: String? = null,
) {
    val artist: String get() = artists.joinToString(", ")

    /** Wie `store.track_key` am Desktop: ISRC, sonst „künstler|titel“ normalisiert. */
    val key: String get() = isrc ?: "${norm(artist)}|${norm(title)}"

    companion object {
        fun norm(s: String): String = s.lowercase()
            .replace(Regex("""\s*[(\[].*?[)\]]"""), "")
            .replace(Regex("""[^\p{L}\p{N}]+"""), " ").trim()
    }
}

/** Ein Eintrag im Verlauf. ts in Sekunden (wie am Desktop). */
@Serializable
data class Recognition(
    val id: Long = 0,
    val uid: String,
    val ts: Double,
    val host: String,
    val source: String,
    val engine: String,
    val track: Track,
    val extra: JsonObject = JsonObject(emptyMap()),
)

/** Playlist eines gekoppelten PCs ([pc] = dessen Kennung; der PC selbst schickt sie ohne). */
@Serializable
data class Playlist(val name: String, val tracks: List<Track>, val updated: Double = 0.0, val pc: String = "")
