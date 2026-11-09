package de.bs002.tunebridge.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.data.Recognition
import de.bs002.tunebridge.ui.Fmt
import de.bs002.tunebridge.ui.components.EmptyState
import de.bs002.tunebridge.ui.components.SectionLabel
import de.bs002.tunebridge.ui.components.TbCard
import de.bs002.tunebridge.ui.favorite
import de.bs002.tunebridge.ui.shownGenre
import de.bs002.tunebridge.ui.theme.GenreColors
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbType
import java.util.Calendar

/** Zahlen zum Verlauf – alles nur auf dem Handy berechnet, nichts wird gesendet. */
private class Stats(recs: List<Recognition>) {
    val total = recs.size
    val artists = recs.flatMap { it.track.artists.ifEmpty { listOf(it.track.artist) } }.filter { it.isNotBlank() }
        .groupingBy { it }.eachCount().entries.sortedByDescending { it.value }.map { it.key to it.value }
    val songs = recs.groupBy { it.track.key }.values.map { it.first() to it.size }.sortedByDescending { it.second }
    val genres = recs.mapNotNull { it.shownGenre }.groupingBy { it }.eachCount().entries.sortedByDescending { it.value }.map { it.key to it.value }
    val favorites = recs.count { it.favorite }
    private val cal = Calendar.getInstance()
    private fun field(ts: Double, f: Int) = cal.apply { timeInMillis = (ts * 1000).toLong() }.get(f)
    /** Montag = 0 … Sonntag = 6 */
    val weekdays = IntArray(7).also { a -> recs.forEach { a[(field(it.ts, Calendar.DAY_OF_WEEK) + 5) % 7]++ } }
    /** 4-Stunden-Blöcke: 0–4, 4–8, … */
    val hours = IntArray(6).also { a -> recs.forEach { a[field(it.ts, Calendar.HOUR_OF_DAY) / 4]++ } }
    val days = recs.map { dayIndex(it.ts) }.toSortedSet()
    /** Längste Folge von Tagen mit mindestens einem Song. */
    val streak: Int = run {
        var best = 0; var run = 0; var prev = Long.MIN_VALUE
        for (d in days) { run = if (d == prev + 1) run + 1 else 1; best = maxOf(best, run); prev = d }
        best
    }
    val sources = recs.groupingBy { r -> Origin.entries.drop(1).firstOrNull { it.matches(r) }?.label ?: "Sonstige" }.eachCount()
        .entries.sortedByDescending { it.value }.map { it.key to it.value }

    companion object {
        fun dayIndex(ts: Double): Long {
            val c = Calendar.getInstance().apply { timeInMillis = (ts * 1000).toLong() }
            return (c.timeInMillis + c.get(Calendar.ZONE_OFFSET) + c.get(Calendar.DST_OFFSET)) / 86_400_000L
        }
    }
}

@Composable
fun StatsScreen(back: () -> Unit, openSong: (String) -> Unit) {
    val all by App.repo.history.collectAsState()
    var period by rememberSaveable { mutableStateOf(Period.Month) }
    val recs = remember(all, period) { val since = period.since(); all.filter { it.ts >= since } }
    val st = remember(recs) { Stats(recs) }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        TopBack(back)
        ScreenHeader("Rückblick", "Nur auf dem Handy berechnet")
        Column(Modifier.padding(horizontal = 20.dp)) {
            Segmented(listOf(Period.Week, Period.Month, Period.Year, Period.All), period,
                { if (it == Period.All) "Alles" else it.label }) { period = it }
            if (st.total == 0) {
                EmptyState(Ico.Chart, "Noch nichts in diesem Zeitraum", "Erkenne ein paar Songs – dann steht hier, was du so hörst.")
                return@Column
            }
            Spacer(Modifier.height(16.dp))
            Summary(st, period)
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Tile(Fmt.songs(st.total), "erkannt", Modifier.weight(1f))
                Tile("${st.artists.size}", if (st.artists.size == 1) "Künstler" else "Künstler:innen", Modifier.weight(1f))
            }
            Spacer(Modifier.height(10.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                Tile("${st.days.size}", if (st.days.size == 1) "Tag aktiv" else "Tage aktiv", Modifier.weight(1f))
                Tile("${st.streak}", if (st.streak == 1) "Tag am Stück" else "Tage am Stück", Modifier.weight(1f))
                Tile("${st.favorites}", if (st.favorites == 1) "Favorit" else "Favoriten", Modifier.weight(1f))
            }

            if (st.genres.isNotEmpty()) {
                SectionLabel("Genres", Modifier.padding(top = 22.dp))
                TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                    GenreStrip(st.genres)
                    Spacer(Modifier.height(12.dp))
                    BarList(st.genres.take(8).map { Triple(it.first, it.second, GenreColors.of(it.first)) }, st.total)
                }
            }
            SectionLabel("Meiste Künstler", Modifier.padding(top = 22.dp))
            TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                BarList(st.artists.take(8).map { Triple(it.first, it.second, Tb.accent) }, st.artists.first().second)
            }
            val repeats = st.songs.filter { it.second > 1 }
            if (repeats.isNotEmpty()) {
                SectionLabel("Öfter erkannt", Modifier.padding(top = 22.dp))
                TbCard(Modifier.fillMaxWidth(), padding = 4.dp) {
                    repeats.take(5).forEach { (rec, n) ->
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Box(Modifier.weight(1f)) { SongRow(rec, onClick = { openSong(rec.uid) }, showDay = true) }
                            Text("${n}×", style = TbType.bodyStrong, color = Tb.accent, modifier = Modifier.padding(end = 14.dp))
                        }
                    }
                }
            }
            SectionLabel("Wann du erkennst", Modifier.padding(top = 22.dp))
            TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                Columns(listOf("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"), st.weekdays)
                Spacer(Modifier.height(16.dp))
                Columns(listOf("0–4", "4–8", "8–12", "12–16", "16–20", "20–24"), st.hours)
            }
            SectionLabel("Quellen", Modifier.padding(top = 22.dp))
            TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                BarList(st.sources.map { Triple(it.first, it.second, Tb.text2) }, st.total)
            }
            Spacer(Modifier.height(32.dp))
        }
    }
}

/** Ein Satz zum Zeitraum – wie ein kleiner Jahres-/Monatsrückblick. */
@Composable
private fun Summary(st: Stats, period: Period) {
    val span = when (period) { Period.Week -> "Diese Woche"; Period.Month -> "In den letzten 30 Tagen"; Period.Year -> "In den letzten 12 Monaten"; else -> "Insgesamt" }
    val text = buildString {
        append("$span hast du ${Fmt.songs(st.total)} erkannt")
        st.genres.firstOrNull()?.let { append(", am meisten ${it.first}") }
        st.artists.firstOrNull()?.takeIf { it.second > 1 }?.let { append(" – ganz vorne: ${it.first} (${it.second}×)") }
        append(".")
        val busiest = st.weekdays.indices.maxByOrNull { st.weekdays[it] }
        if (busiest != null && st.total >= 5) append(" Dein Erkenn-Tag: ${listOf("Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag")[busiest]}.")
    }
    TbCard(Modifier.fillMaxWidth(), padding = 16.dp) {
        Text(text, style = TbType.body, color = Tb.text)
    }
}

@Composable
private fun Tile(value: String, label: String, modifier: Modifier) {
    TbCard(modifier, padding = 12.dp) {
        Text(value, style = TbType.title, color = Tb.text, maxLines = 1)
        Text(label, style = TbType.small, color = Tb.text3, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
private fun GenreStrip(genres: List<Pair<String, Int>>) {
    val sum = genres.sumOf { it.second }.coerceAtLeast(1)
    Row(Modifier.fillMaxWidth().height(10.dp).clip(RoundedCornerShape(5.dp))) {
        genres.forEach { (g, n) -> Box(Modifier.weight(n.toFloat() / sum).fillMaxHeight().background(GenreColors.of(g))) }
    }
}

@Composable
private fun BarList(rows: List<Triple<String, Int, Color>>, max: Int) {
    Column(verticalArrangement = Arrangement.spacedBy(9.dp)) {
        rows.forEach { (name, n, color) ->
            Column {
                Row {
                    Text(name, style = TbType.small, color = Tb.text2, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.weight(1f))
                    Text("$n", style = TbType.small, color = Tb.text3)
                }
                Spacer(Modifier.height(4.dp))
                Box(Modifier.fillMaxWidth().height(6.dp).clip(RoundedCornerShape(3.dp)).background(Tb.bg3)) {
                    Box(Modifier.fillMaxWidth((n.toFloat() / max.coerceAtLeast(1)).coerceIn(0.02f, 1f)).fillMaxHeight()
                        .clip(RoundedCornerShape(3.dp)).background(color))
                }
            }
        }
    }
}

@Composable
private fun Columns(labels: List<String>, values: IntArray) {
    val max = values.maxOrNull()?.coerceAtLeast(1) ?: 1
    Row(Modifier.fillMaxWidth().height(96.dp), horizontalArrangement = Arrangement.spacedBy(6.dp), verticalAlignment = Alignment.Bottom) {
        labels.forEachIndexed { i, l ->
            Column(Modifier.weight(1f), horizontalAlignment = Alignment.CenterHorizontally) {
                if (values[i] > 0) Text("${values[i]}", style = TbType.small, color = Tb.text3)
                Box(Modifier.fillMaxWidth().height((60f * values[i] / max).coerceAtLeast(2f).dp).clip(RoundedCornerShape(4.dp))
                    .background(if (values[i] == max && values[i] > 0) Tb.accent else Tb.bg3))
                Spacer(Modifier.height(4.dp))
                Text(l, style = TbType.small, color = Tb.text3, maxLines = 1)
            }
        }
    }
}

