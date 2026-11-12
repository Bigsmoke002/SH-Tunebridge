package de.bs002.tunebridge.ui.screens

import de.bs002.tunebridge.playable

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
import de.bs002.tunebridge.data.PHONE
import de.bs002.tunebridge.data.Playlist
import de.bs002.tunebridge.ui.components.IconBtn
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
fun PlaylistsScreen(open: (String, String) -> Unit, openPc: () -> Unit, openMix: () -> Unit = {}) {
    val lists by App.repo.playlists.collectAsState()
    val pcs = App.repo.settings.collectAsState().value.pcs
    val paired = pcs.isNotEmpty()
    var q by rememberSaveable { mutableStateOf("") }
    var create by remember { mutableStateOf(false) }
    if (create) NameDialog("Neue Playlist", "", "Anlegen", close = { create = false }) { n ->
        if (App.repo.createPhonePlaylist(n)) { create = false; open(PHONE, n); null } else "Diesen Namen gibt es schon"
    }
    Column(Modifier.fillMaxSize()) {
        val phoneN = lists.count { it.pc == PHONE }
        ScreenHeader("Playlists", if (lists.isEmpty()) null else "${lists.size} · ${Fmt.songs(lists.sumOf { it.tracks.size })}" +
            if (phoneN > 0 && phoneN < lists.size) " · $phoneN auf dem Handy" else "") {
            if (paired) TbButton("Mix", openMix, kind = BtnKind.Ghost, icon = Ico.Sparkle, small = true)
            IconBtn(Ico.Plus, "Neue Playlist", { create = true })
        }
        if (lists.isEmpty()) {
            EmptyState(
                Ico.Stack, "Noch keine Playlists",
                if (paired) "Leg hier eigene Playlists an oder sortiere am PC – beim nächsten Abgleich erscheinen die PC-Playlists hier."
                else "Leg eigene Playlists auf dem Handy an. Gekoppelt mit SH-Tunebridge am PC siehst du hier auch alle PC-Playlists.",
            ) {
                Row(horizontalArrangement = androidx.compose.foundation.layout.Arrangement.spacedBy(8.dp)) {
                    TbButton("Neue Playlist", { create = true }, kind = BtnKind.Primary, icon = Ico.Plus)
                    if (!paired) TbButton("Mit PC koppeln", openPc, kind = BtnKind.Ghost, icon = Ico.Qr)
                }
            }
            return
        }
        if (lists.size > 8) SearchField(q, { q = it }, Modifier.padding(horizontal = 20.dp), "Playlist suchen …")
        val shown = remember(lists, q) { lists.filter { q.isBlank() || it.name.contains(q.trim(), true) } }
        val groups = remember(shown, pcs) {
            (listOf(Triple(PHONE, "Auf dem Handy", Ico.Phone)) + pcs.map { Triple(it.pcId, it.pcName, Ico.Monitor) })
                .map { g -> g to shown.filter { it.pc == g.first } }.filter { it.second.isNotEmpty() }
        }
        LazyColumn(contentPadding = PaddingValues(start = 10.dp, end = 10.dp, top = 8.dp, bottom = 24.dp)) {
            groups.forEach { (g, ls) ->
                if (groups.size > 1 || g.first == PHONE) item(key = "g-${g.first}") {
                    Row(Modifier.padding(start = 10.dp, top = 14.dp, bottom = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                        TbIcon(g.third, Tb.text3, 14.dp)
                        Spacer(Modifier.width(8.dp))
                        Text(g.second, style = TbType.label, color = Tb.text3)
                    }
                }
                items(ls, key = { "${it.pc}/${it.name}" }) { p -> PlaylistRow(p) { open(p.pc, p.name) } }
            }
        }
    }
}

/** Name eingeben (neue Playlist, Umbenennen). [save] gibt eine Fehlermeldung zurück oder null (= fertig). */
@Composable
fun NameDialog(title: String, initial: String, confirm: String, close: () -> Unit, save: (String) -> String?) {
    var name by remember { mutableStateOf(initial) }
    var err by remember { mutableStateOf<String?>(null) }
    androidx.compose.material3.AlertDialog(
        onDismissRequest = close, containerColor = Tb.bg2,
        title = { Text(title, style = TbType.title, color = Tb.text) },
        text = {
            Column {
                SearchField(name, { name = it; err = null }, placeholder = "Name")
                err?.let { Text(it, style = TbType.small, color = Tb.danger, modifier = Modifier.padding(top = 8.dp)) }
            }
        },
        confirmButton = {
            TbButton(confirm, {
                val n = name.trim().take(120)
                if (n.isEmpty()) err = "Bitte einen Namen eingeben" else err = save(n)
            }, kind = BtnKind.Primary)
        },
        dismissButton = { TbButton("Abbrechen", close, kind = BtnKind.Ghost) },
    )
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
fun PlaylistScreen(pc: String, name: String, back: () -> Unit, openSimilar: (Track) -> Unit = {}, openVersions: (Track) -> Unit = {}, openSet: () -> Unit = {},
                   renamed: (String) -> Unit = {}) {
    val lists by App.repo.playlists.collectAsState()
    val p = lists.firstOrNull { it.pc == pc && it.name == name }
    val pcName = App.repo.settings.collectAsState().value.pcs.let { l -> if (l.size > 1) l.firstOrNull { it.pcId == pc }?.pcName else null }
    var sheet by remember { mutableStateOf<Track?>(null) }
    var q by rememberSaveable { mutableStateOf("") }
    val phone = pc == PHONE
    var menu by remember { mutableStateOf(false) }
    var rename by remember { mutableStateOf(false) }
    var copy by remember { mutableStateOf(false) }
    val pcs = App.repo.settings.collectAsState().value.pcs
    if (rename) NameDialog("Umbenennen", name, "Speichern", close = { rename = false }) { n ->
        if (App.repo.renamePhonePlaylist(name, n)) { rename = false; renamed(n); null } else "Diesen Namen gibt es schon"
    }
    if (copy && p != null) CopyToPcDialog(p, pcs, close = { copy = false })
    Column(Modifier.fillMaxSize()) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.weight(1f)) { TopBack(back) }
            if (phone && p != null) Box(Modifier.padding(top = 8.dp, end = 12.dp)) {
                IconBtn(Ico.More, "Mehr", { menu = true })
                androidx.compose.material3.DropdownMenu(menu, { menu = false }, containerColor = Tb.bg2) {
                    androidx.compose.material3.DropdownMenuItem({ Text("Umbenennen", style = TbType.body, color = Tb.text) }, { menu = false; rename = true },
                        leadingIcon = { TbIcon(Ico.Edit, Tb.text2, 18.dp) })
                    if (pcs.isNotEmpty() && p.tracks.isNotEmpty()) androidx.compose.material3.DropdownMenuItem(
                        { Text(if (pcs.size == 1) "Auf ${pcs[0].pcName} kopieren" else "Auf einen PC kopieren", style = TbType.body, color = Tb.text) },
                        { menu = false; copy = true }, leadingIcon = { TbIcon(Ico.Monitor, Tb.text2, 18.dp) })
                    androidx.compose.material3.DropdownMenuItem({ Text("Löschen", style = TbType.body, color = Tb.danger) }, {
                        menu = false
                        App.repo.deletePhonePlaylist(name)?.let { gone -> App.snack("„$name“ gelöscht", "Rückgängig") { App.repo.restorePlaylist(gone) } }
                        back()
                    }, leadingIcon = { TbIcon(Ico.Trash, Tb.danger, 18.dp) })
                }
            }
        }
        var share by remember { mutableStateOf(false) }
        if (share && p != null) ExportSheet(name, p.tracks.map { de.bs002.tunebridge.data.Export.Item(it) }) { share = false }
        ScreenHeader(name, p?.let { Fmt.songs(it.tracks.size) + (if (phone) " · auf dem Handy" else pcName?.let { n -> " · $n" } ?: "") }) {
            if (p != null && p.tracks.size >= 3 && App.repo.link(pc) != null) de.bs002.tunebridge.ui.components.IconBtn(Ico.Sliders, "Set planen", openSet)
            if (p != null && p.tracks.isNotEmpty()) de.bs002.tunebridge.ui.components.IconBtn(de.bs002.tunebridge.ui.theme.Ico.Share, "Teilen / exportieren", { share = true })
            if (p != null && p.tracks.any { it.playable }) PlayButtons(p.tracks, name)
        }
        if (p == null || p.tracks.isEmpty()) {
            EmptyState(Ico.Stack, "Leer", if (phone) "Füge Songs über „Zur Playlist“ in einem Song hinzu – oder im Verlauf lange auf Songs drücken und mehrere auf einmal einsortieren."
                else "In dieser Playlist sind noch keine Songs.")
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
                    TbButton(if (playing == url) "Stopp" else "Reinhören", { Player.toggle(url, t) }, kind = BtnKind.Primary, icon = if (playing == url) Ico.Pause else Ico.Play)
                }
                if (t.playable && p != null) {
                    Spacer(Modifier.padding(top = 8.dp))
                    TbButton("Ab hier abspielen", { Player.play(p.tracks, p.tracks.indexOf(t), name); sheet = null }, kind = BtnKind.Ghost, icon = Ico.Next)
                }
                Spacer(Modifier.padding(top = 8.dp))
                TbButton("Ähnliche Songs", { sheet = null; openSimilar(t) }, kind = BtnKind.Ghost, icon = Ico.Sparkle)
                Spacer(Modifier.padding(top = 8.dp))
                TbButton("Remixe & Versionen", { sheet = null; openVersions(t) }, kind = BtnKind.Ghost, icon = Ico.Disc)
                SectionLabel("Anhören & öffnen")
                LinkGrid(t, emptyMap())
                SectionLabel("In dieser Playlist")
                TbButton("Aus „$name“ entfernen", { App.repo.removeFromPlaylist(pc, name, t); sheet = null }, kind = BtnKind.Danger, icon = Ico.Trash)
            }
        }
    }
}

/** Handy-Playlist in eine PC-Playlist kopieren (gleicher Name; geht beim nächsten Abgleich an den PC). */
@Composable
private fun CopyToPcDialog(p: Playlist, pcs: List<de.bs002.tunebridge.data.Repository.PcLink>, close: () -> Unit) {
    var target by remember { mutableStateOf(pcs.first().pcId) }
    androidx.compose.material3.AlertDialog(
        onDismissRequest = close, containerColor = Tb.bg2,
        title = { Text("Auf den PC kopieren?", style = TbType.title, color = Tb.text) },
        text = {
            Column {
                Text("${Fmt.songs(p.tracks.size)} kommen in die PC-Playlist „${p.name}“ (wird angelegt, falls es sie nicht gibt; Doppelte bleiben draußen). " +
                    "Am PC erscheinen sie beim nächsten Abgleich. Die Handy-Playlist bleibt.", style = TbType.body, color = Tb.text2)
                if (pcs.size > 1) {
                    Spacer(Modifier.padding(top = 12.dp))
                    Segmented(pcs.map { it.pcId }, target, { id -> pcs.first { it.pcId == id }.pcName }) { target = it }
                }
            }
        },
        confirmButton = {
            TbButton("Kopieren", {
                val n = App.repo.addAllToPlaylist(target, p.name, p.tracks)
                App.snack(if (n == 0) "Alle Songs sind schon in der PC-Playlist" else "${Fmt.songs(n)} für den PC vorgemerkt")
                App.listener.autoSync()
                close()
            }, kind = BtnKind.Primary)
        },
        dismissButton = { TbButton("Abbrechen", close, kind = BtnKind.Ghost) },
    )
}
