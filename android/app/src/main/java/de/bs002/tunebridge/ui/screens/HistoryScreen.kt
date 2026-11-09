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
import de.bs002.tunebridge.ui.components.EmptyState
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType

@Composable
fun HistoryScreen(openSong: (String) -> Unit) {
    val all by App.repo.history.collectAsState()
    var q by rememberSaveable { mutableStateOf("") }
    val list = remember(all, q) {
        val needle = q.trim().lowercase()
        if (needle.isEmpty()) all else all.filter { "${it.track.title} ${it.track.artist}".lowercase().contains(needle) }
    }
    val groups = remember(list) { list.groupBy { Fmt.dayLabel(it.ts) } }
    val listState = rememberLazyListState()
    // Neuer Song oben (Erkennung, Teilen, Abgleich): mitnehmen, solange man ganz oben war
    LaunchedEffect(list.firstOrNull()?.uid) { if (listState.firstVisibleItemIndex <= 2) listState.animateScrollToItem(0) }

    Column(Modifier.fillMaxSize()) {
        ScreenHeader("Verlauf", if (all.isEmpty()) null else Fmt.songs(all.size)) {
            if (list.any { it.track.playable }) PlayButtons(list.map { it.track }, "Verlauf")
        }
        if (all.isEmpty()) {
            EmptyState(Ico.Clock, "Noch leer", "Erkannte Songs landen hier – vom Handy und, wenn gekoppelt, auch die vom PC.")
            return
        }
        SearchField(q, { q = it }, Modifier.padding(horizontal = 20.dp))
        LazyColumn(Modifier.fillMaxSize(), state = listState, contentPadding = androidx.compose.foundation.layout.PaddingValues(start = 10.dp, end = 10.dp, bottom = 24.dp)) {
            groups.forEach { (day, recs) ->
                item(key = "h-$day") {
                    Text(day, style = TbType.label, color = Tb.text3, modifier = Modifier.padding(start = 10.dp, top = 20.dp, bottom = 6.dp))
                }
                items(recs, key = { it.uid }) { rec ->
                    SongRow(rec, onClick = { openSong(rec.uid) }, showSource = true)
                }
            }
            if (list.isEmpty()) item { Text("Keine Treffer für „$q“.", style = TbType.body, color = Tb.text3, modifier = Modifier.padding(20.dp)) }
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
