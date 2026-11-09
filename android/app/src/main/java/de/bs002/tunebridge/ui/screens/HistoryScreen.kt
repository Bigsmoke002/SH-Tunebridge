package de.bs002.tunebridge.ui.screens

import de.bs002.tunebridge.playable

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
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
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.ui.Fmt
import de.bs002.tunebridge.ui.favorite
import de.bs002.tunebridge.ui.shownGenre
import de.bs002.tunebridge.data.Recognition
import androidx.compose.foundation.clickable
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.foundation.layout.Box
import de.bs002.tunebridge.ui.components.EmptyState
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType

@Composable
fun HistoryScreen(openSong: (String) -> Unit) {
    val all by App.repo.history.collectAsState()
    var q by rememberSaveable { mutableStateOf("") }
    var favOnly by rememberSaveable { mutableStateOf(false) }
    var period by rememberSaveable { mutableStateOf(Period.All) }
    var origin by rememberSaveable { mutableStateOf(Origin.All) }
    var genre by rememberSaveable { mutableStateOf<String?>(null) }
    val genres = remember(all) { all.mapNotNull { it.shownGenre }.groupingBy { it }.eachCount().entries.sortedByDescending { it.value }.map { it.key } }
    val list = remember(all, q, favOnly, period, origin, genre) {
        val needle = q.trim().lowercase()
        val since = period.since()
        all.filter { r ->
            (needle.isEmpty() || "${r.track.title} ${r.track.artist} ${r.track.album.orEmpty()} ${r.shownGenre.orEmpty()}".lowercase().contains(needle)) &&
                (!favOnly || r.favorite) && r.ts >= since && origin.matches(r) && (genre == null || r.shownGenre == genre)
        }
    }
    val filtered = favOnly || period != Period.All || origin != Origin.All || genre != null
    val groups = remember(list) { list.groupBy { Fmt.dayLabel(it.ts) } }
    val listState = rememberLazyListState()
    // Neuer Song oben (Erkennung, Teilen, Abgleich): mitnehmen, solange man ganz oben war
    LaunchedEffect(list.firstOrNull()?.uid) { if (listState.firstVisibleItemIndex <= 2) listState.animateScrollToItem(0) }

    Column(Modifier.fillMaxSize()) {
        ScreenHeader("Verlauf", if (all.isEmpty()) null else if (list.size != all.size) "${list.size} von ${Fmt.songs(all.size)}" else Fmt.songs(all.size)) {
            if (list.any { it.track.playable }) PlayButtons(list.map { it.track }, "Verlauf")
        }
        if (all.isEmpty()) {
            EmptyState(Ico.Clock, "Noch leer", "Erkannte Songs landen hier – vom Handy und, wenn gekoppelt, auch die vom PC.")
            return
        }
        SearchField(q, { q = it }, Modifier.padding(horizontal = 20.dp))
        androidx.compose.foundation.lazy.LazyRow(Modifier.fillMaxWidth().padding(top = 10.dp),
            contentPadding = androidx.compose.foundation.layout.PaddingValues(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            item { FilterChip("Favoriten", favOnly, if (favOnly) Ico.HeartFill else Ico.Heart) { favOnly = !favOnly } }
            item { MenuChip(period.label, period != Period.All, Period.entries.map { it.label }) { period = Period.entries[it] } }
            item { MenuChip(origin.label, origin != Origin.All, Origin.entries.map { it.label }) { origin = Origin.entries[it] } }
            if (genres.isNotEmpty()) item {
                MenuChip(genre ?: "Alle Genres", genre != null, listOf("Alle Genres") + genres) { genre = if (it == 0) null else genres[it - 1] }
            }
            if (filtered) item { FilterChip("Zurücksetzen", false, Ico.X) { favOnly = false; period = Period.All; origin = Origin.All; genre = null } }
        }
        LazyColumn(Modifier.fillMaxSize(), state = listState, contentPadding = androidx.compose.foundation.layout.PaddingValues(start = 10.dp, end = 10.dp, bottom = 24.dp)) {
            groups.forEach { (day, recs) ->
                item(key = "h-$day") {
                    Text(day, style = TbType.label, color = Tb.text3, modifier = Modifier.padding(start = 10.dp, top = 20.dp, bottom = 6.dp))
                }
                items(recs, key = { it.uid }) { rec ->
                    SongRow(rec, onClick = { openSong(rec.uid) }, showSource = true)
                }
            }
            if (list.isEmpty()) item { Text(if (q.isBlank()) "Nichts passt zu diesen Filtern." else "Keine Treffer für „$q“.", style = TbType.body, color = Tb.text3, modifier = Modifier.padding(20.dp)) }
        }
    }
}

@Composable
fun ScreenHeader(title: String, sub: String? = null, trailing: @Composable () -> Unit = {}) {
    Row(Modifier.fillMaxWidth().padding(start = 20.dp, end = 12.dp, top = 18.dp, bottom = 14.dp), verticalAlignment = Alignment.Bottom) {
        Column(Modifier.weight(1f)) {
            Text(title, style = TbType.display, color = Tb.text)
            if (sub != null) Text(sub, style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 2.dp))
        }
        trailing()
    }
}

@Composable
fun SearchField(value: String, onChange: (String) -> Unit, modifier: Modifier = Modifier, placeholder: String = "Suchen …") {
    val shape = RoundedCornerShape(Tb.radiusSm)
    Row(
        modifier.fillMaxWidth().clip(shape).background(Tb.bg3).border(1.dp, Tb.line, shape).padding(horizontal = 12.dp, vertical = 11.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        TbIcon(Ico.Search, Tb.text3, 17.dp)
        Spacer(Modifier.width(10.dp))
        BasicTextField(
            value, onChange, singleLine = true, textStyle = TbType.body.copy(color = Tb.text), cursorBrush = SolidColor(Tb.accent),
            modifier = Modifier.weight(1f),
            decorationBox = { inner -> if (value.isEmpty()) Text(placeholder, style = TbType.body, color = Tb.text3); inner() },
        )
    }
}

/** „Abspielen“ und „Zufällig“ für eine Liste – spielt die Hörproben nacheinander (Mini-Player unten). */
@Composable
fun PlayButtons(tracks: List<de.bs002.tunebridge.data.Track>, title: String) {
    Row(horizontalArrangement = Arrangement.spacedBy(2.dp), verticalAlignment = Alignment.CenterVertically) {
        de.bs002.tunebridge.ui.components.IconBtn(Ico.Shuffle, "Zufällig abspielen", { de.bs002.tunebridge.Player.play(tracks.shuffled(), 0, title) })
        de.bs002.tunebridge.ui.components.IconBtn(Ico.Play, "Abspielen", { de.bs002.tunebridge.Player.play(tracks, 0, title) }, tint = Tb.accent)
    }
}

/** Zeitraum-Filter im Verlauf. */
enum class Period(val label: String, private val days: Int) {
    All("Jederzeit", 0), Today("Heute", -1), Week("7 Tage", 7), Month("30 Tage", 30), Year("12 Monate", 365);

    fun since(): Double = when {
        days == 0 -> 0.0
        days < 0 -> java.util.Calendar.getInstance().apply {
            set(java.util.Calendar.HOUR_OF_DAY, 0); set(java.util.Calendar.MINUTE, 0); set(java.util.Calendar.SECOND, 0)
        }.timeInMillis / 1000.0
        else -> System.currentTimeMillis() / 1000.0 - days * 86400.0
    }
}

/** Woher der Eintrag stammt. */
enum class Origin(val label: String) {
    All("Alle Quellen"), Mic("Mikrofon"), System("Handy-Ton"), Pc("Vom PC"), Other("Geteilt & Import");

    fun matches(r: Recognition): Boolean = when (this) {
        All -> true
        Mic -> r.source == "handy-mikrofon"
        System -> r.source == "handy-ton"
        Pc -> !r.host.startsWith("Handy")
        Other -> r.host.startsWith("Handy") && r.source != "handy-mikrofon" && r.source != "handy-ton"
    }
}

@Composable
fun FilterChip(text: String, active: Boolean, icon: Ico? = null, onClick: () -> Unit) {
    Row(
        Modifier.clip(CircleShape).background(if (active) Tb.accent.copy(alpha = 0.16f) else Tb.bg3)
            .border(1.dp, if (active) Tb.accent.copy(alpha = 0.5f) else Tb.line, CircleShape)
            .clickable(onClick = onClick).padding(horizontal = 12.dp, vertical = 7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) { TbIcon(icon, if (active) Tb.accent else Tb.text3, 14.dp); Spacer(Modifier.width(6.dp)) }
        Text(text, style = TbType.small, color = if (active) Tb.accent else Tb.text2, maxLines = 1)
    }
}

@Composable
fun MenuChip(text: String, active: Boolean, options: List<String>, pick: (Int) -> Unit) {
    var open by remember { mutableStateOf(false) }
    Box {
        FilterChip("$text  ▾", active) { open = true }
        DropdownMenu(open, { open = false }, containerColor = Tb.bg2) {
            options.forEachIndexed { i, o ->
                DropdownMenuItem({ Text(o, style = TbType.body, color = Tb.text) }, { open = false; pick(i) })
            }
        }
    }
}
