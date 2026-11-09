package de.bs002.tunebridge.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
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
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.Player
import de.bs002.tunebridge.data.Playlist
import de.bs002.tunebridge.data.Track
import de.bs002.tunebridge.ui.Fmt
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.Cover
import de.bs002.tunebridge.ui.components.EmptyState
import de.bs002.tunebridge.ui.components.GenreChip
import de.bs002.tunebridge.ui.components.SectionLabel
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.components.TrackLine
import de.bs002.tunebridge.ui.theme.GenreColors
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType

@Composable
fun PlaylistsScreen(open: (String, String) -> Unit, openPc: () -> Unit) {
    val lists by App.repo.playlists.collectAsState()
    val pcs = App.repo.settings.collectAsState().value.pcs
    val paired = pcs.isNotEmpty()
    var q by rememberSaveable { mutableStateOf("") }
    Column(Modifier.fillMaxSize()) {
        ScreenHeader("Playlists", if (lists.isEmpty()) null
            else "${lists.size} ${if (pcs.size > 1) "von ${pcs.size} PCs" else "vom PC"} · ${Fmt.songs(lists.sumOf { it.tracks.size })}")
        if (lists.isEmpty()) {
            EmptyState(
                Ico.Stack, if (paired) "Noch keine Playlists" else "Deine Playlists wohnen am PC",
                if (paired) "Sortiere am PC Songs in Playlists – beim nächsten Abgleich erscheinen sie hier."
                else "Kopple das Handy mit SH-Tunebridge am PC. Dann siehst du hier alle Playlists und kannst unterwegs Songs einsortieren.",
            ) { if (!paired) TbButton("Mit PC koppeln", openPc, kind = BtnKind.Primary, icon = Ico.Qr) }
            return
        }
        if (lists.size > 8) SearchField(q, { q = it }, Modifier.padding(horizontal = 20.dp), "Playlist suchen …")
        val shown = remember(lists, q) { lists.filter { q.isBlank() || it.name.contains(q.trim(), true) } }
        val groups = remember(shown, pcs) { pcs.map { pc -> pc to shown.filter { it.pc == pc.pcId } }.filter { it.second.isNotEmpty() } }
        LazyColumn(contentPadding = PaddingValues(start = 10.dp, end = 10.dp, top = 8.dp, bottom = 24.dp)) {
            groups.forEach { (pc, ls) ->
                if (groups.size > 1) item(key = "pc-${pc.pcId}") {
                    Row(Modifier.padding(start = 10.dp, top = 14.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                        TbIcon(Ico.Monitor, Tb.text3, 14.dp)
                        Spacer(Modifier.width(8.dp))
                        Text(pc.pcName, style = TbType.label, color = Tb.text3)
                    }
                }
                items(ls, key = { "${it.pc}/${it.name}" }) { p -> PlaylistRow(p) { open(p.pc, p.name) } }
            }
        }
    }
}

@Composable
private fun PlaylistRow(p: Playlist, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().clip(RoundedCornerShape(Tb.radiusSm)).clickable(onClick = onClick).padding(horizontal = 10.dp, vertical = 9.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Mosaic(p.tracks.mapNotNull { it.cover }.distinct().take(4), p.name)
        Spacer(Modifier.width(14.dp))
        Column(Modifier.weight(1f)) {
            Text(p.name, style = TbType.bodyStrong, color = Tb.text, maxLines = 1)
            Text(Fmt.songs(p.tracks.size), style = TbType.small, color = Tb.text3)
        }
        TbIcon(Ico.Chevron, Tb.text3, 16.dp)
    }
}

/** 2×2 aus den ersten Covern – wie die Playlist-Kacheln am Desktop. */
@Composable
private fun Mosaic(covers: List<String>, name: String) {
    val size = 52.dp
    Box(Modifier.size(size).clip(RoundedCornerShape(Tb.radiusSm)).background(GenreColors.of(name).copy(alpha = 0.14f)), contentAlignment = Alignment.Center) {
        if (covers.size >= 4 && App.repo.settings.value.covers) {
            Column {
                Row { Cover(covers[0], size / 2, 0.dp); Cover(covers[1], size / 2, 0.dp) }
                Row { Cover(covers[2], size / 2, 0.dp); Cover(covers[3], size / 2, 0.dp) }
            }
        } else if (covers.isNotEmpty() && App.repo.settings.value.covers) Cover(covers[0], size, 0.dp)
        else TbIcon(Ico.Stack, GenreColors.of(name), 22.dp)
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlaylistScreen(pc: String, name: String, back: () -> Unit) {
    val lists by App.repo.playlists.collectAsState()
    val p = lists.firstOrNull { it.pc == pc && it.name == name }
    val pcName = App.repo.settings.collectAsState().value.pcs.let { l -> if (l.size > 1) l.firstOrNull { it.pcId == pc }?.pcName else null }
    var sheet by remember { mutableStateOf<Track?>(null) }
    var q by rememberSaveable { mutableStateOf("") }
    Column(Modifier.fillMaxSize()) {
        TopBack(back)
        ScreenHeader(name, p?.let { Fmt.songs(it.tracks.size) + (pcName?.let { n -> " · $n" } ?: "") })
        if (p == null || p.tracks.isEmpty()) {
            EmptyState(Ico.Stack, "Leer", "In dieser Playlist sind noch keine Songs.")
            return
        }
        if (p.tracks.size > 12) SearchField(q, { q = it }, Modifier.padding(horizontal = 20.dp))
        val shown = remember(p, q) { p.tracks.filter { q.isBlank() || "${it.title} ${it.artist}".contains(q.trim(), true) } }
        LazyColumn(contentPadding = PaddingValues(start = 10.dp, end = 10.dp, top = 6.dp, bottom = 24.dp)) {
            items(shown, key = { it.key }) { t ->
                Row(
                    Modifier.fillMaxWidth().clip(RoundedCornerShape(Tb.radiusSm)).clickable { sheet = t }.padding(horizontal = 10.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Cover(t.cover, 44.dp)
                    Spacer(Modifier.width(12.dp))
                    TrackLine(t.title, t.artist, Modifier.weight(1f))
                    if (t.genre != null) Box(Modifier.size(7.dp).clip(RoundedCornerShape(50)).background(GenreColors.of(t.genre)))
                }
            }
        }
    }
    sheet?.let { t ->
        val playing by Player.playing.collectAsState()
        ModalBottomSheet(onDismissRequest = { sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = Tb.bg1) {
            Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Cover(t.cover, 64.dp)
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        TrackLine(t.title, t.artist)
                        Spacer(Modifier.padding(top = 6.dp))
                        GenreChip(t.genre, t.subgenre)
                    }
                }
                t.previewUrl?.let { url ->
                    Spacer(Modifier.padding(top = 14.dp))
                    TbButton(if (playing == url) "Stopp" else "Reinhören", { Player.toggle(url) }, kind = BtnKind.Primary, icon = if (playing == url) Ico.Pause else Ico.Play)
                }
                SectionLabel("Anhören & öffnen")
                LinkGrid(t, emptyMap())
                SectionLabel("In dieser Playlist")
                TbButton("Aus „$name“ entfernen", { App.repo.removeFromPlaylist(pc, name, t); sheet = null }, kind = BtnKind.Danger, icon = Ico.Trash)
            }
        }
    }
}
