package de.bs002.tunebridge.ui

import de.bs002.tunebridge.data.Recognition
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import kotlinx.serialization.json.contentOrNull
import java.time.Instant
import java.time.LocalDate
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Locale

object Fmt {
    private val de = Locale.GERMANY
    private val time = DateTimeFormatter.ofPattern("HH:mm", de)
    private val day = DateTimeFormatter.ofPattern("EEEE, d. MMMM", de)
    private val dayYear = DateTimeFormatter.ofPattern("d. MMMM yyyy", de)

    fun ago(ts: Double): String {
        val s = (System.currentTimeMillis() / 1000.0 - ts).toLong()
        return when {
            s < 45 -> "gerade eben"
            s < 3600 -> "vor ${(s + 30) / 60} min"
            s < 6 * 3600 -> "vor ${(s + 1800) / 3600} h"
            else -> dayLabel(ts) + ", " + clock(ts)
        }
    }

    fun clock(ts: Double): String = time.format(Instant.ofEpochMilli((ts * 1000).toLong()).atZone(ZoneId.systemDefault()))

    fun dayLabel(ts: Double): String {
        val d = Instant.ofEpochMilli((ts * 1000).toLong()).atZone(ZoneId.systemDefault()).toLocalDate()
        val today = LocalDate.now()
        return when {
            d == today -> "Heute"
            d == today.minusDays(1) -> "Gestern"
            d.year == today.year -> day.format(d)
            else -> dayYear.format(d)
        }
    }

    fun songs(n: Int) = if (n == 1) "1 Song" else "${"%,d".format(de, n)} Songs"
}

fun JsonObject.str(key: String): String? = (this[key] as? JsonPrimitive)?.contentOrNull?.takeIf { it.isNotBlank() }
fun JsonObject.flag(key: String): Boolean = (this[key] as? JsonPrimitive)?.booleanOrNull == true
fun JsonObject.links(): Map<String, String> =
    (this["links"] as? JsonObject)?.mapNotNull { (k, v) -> (v as? JsonPrimitive)?.contentOrNull?.let { k to it } }?.toMap().orEmpty()

/** Genre zum Anzeigen: das vom PC angereicherte, sonst Shazams grobe Angabe. */
val Recognition.shownGenre: String? get() = track.genre ?: extra.str("shazam_genre")
val Recognition.favorite: Boolean get() = (extra["favorite"] as? kotlinx.serialization.json.JsonPrimitive)?.content == "true"
