package de.bs002.tunebridge.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.Player
import de.bs002.tunebridge.data.Track
import de.bs002.tunebridge.net.Version
import de.bs002.tunebridge.net.VersionResult
import de.bs002.tunebridge.net.Versions
import de.bs002.tunebridge.playable
import de.bs002.tunebridge.ui.Fmt
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.Cover
import de.bs002.tunebridge.ui.components.EmptyState
import de.bs002.tunebridge.ui.components.Notice
import de.bs002.tunebridge.ui.components.SectionLabel
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.components.TrackLine
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbType
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

private sealed interface VLoad {
    data object Busy : VLoad
    data class Done(val from: String, val res: VersionResult) : VLoad
    data object NeedConsent : VLoad
    data class Failed(val message: String) : VLoad
}

/** Remixe, Covers & andere Versionen zu [App.versionsSeed]: vom PC, sonst (nach Einwilligung) direkt bei Deezer. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun VersionsScreen(back: () -> Unit) {
    val seed by App.versionsSeed.collectAsState()
    val settings by App.repo.settings.collectAsState()
    var load by remember { mutableStateOf<VLoad>(VLoad.Busy) }
    var retry by remember { mutableIntStateOf(0) }
    var filter by remember { mutableStateOf<String?>(null) }
    var sheet by remember { mutableStateOf<Version?>(null) }
    var pick by remember { mutableStateOf<Track?>(null) }
    val t = seed ?: run {
        Column(Modifier.fillMaxSize()) { TopBack(back); EmptyState(Ico.Search, "Kein Song gewählt", "Öffne einen Song und tippe auf „Remixe & Versionen“.") }
        return
    }

    LaunchedEffect(t, retry, settings.similarDirect) {
        load = VLoad.Busy
        load = try {
            val pc = runCatching { App.sync.versions(t) }.getOrNull()
            when {
                pc != null -> VLoad.Done("vom PC", pc)
                settings.similarDirect -> VLoad.Done("von Deezer", withContext(Dispatchers.IO) { Versions.find(t) })
                else -> VLoad.NeedConsent
            }
        } catch (e: Exception) {
            VLoad.Failed(e.message ?: "Hat nicht geklappt")
        }
        (load as? VLoad.Done)?.res?.items?.let { items -> filter = if (items.any { it.kind == "remix" }) "remix" else null }
    }

    Column(Modifier.fillMaxSize()) {
        TopBack(back)
        val done = load as? VLoad.Done
        val shown = done?.res?.items?.filter { filter == null || it.kind == filter }.orEmpty()
        ScreenHeader("Remixe & Versionen", "${t.title} · ${t.artist}" + (done?.let { " · ${it.from}" } ?: "")) {
            if (shown.any { it.track.playable }) PlayButtons(shown.map { it.track }, "Versionen von ${t.title}")
        }
        when (val l = load) {
            VLoad.Busy -> Box(Modifier.fillMaxWidth().padding(40.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Tb.accent) }
            VLoad.NeedConsent -> Column(Modifier.padding(horizontal = 20.dp)) {
                Notice("Kein PC erreichbar. Unterwegs kann die App direkt bei Deezer nach Remixen und Versionen suchen: Dafür gehen Titel " +
                    "und Künstler dieses Songs an Deezer, Deezer sieht deine IP-Adresse. Ausschaltbar unter Mehr › Datenschutz.",
                    icon = Ico.Info, color = Tb.accent) {
                    Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TbButton("Erlauben & suchen", { App.repo.updateSettings { it.copy(similarDirect = true) } }, kind = BtnKind.Primary, small = true)
                        TbButton("Später am PC", back, kind = BtnKind.Ghost, small = true)
                    }
                }
            }
            is VLoad.Failed -> EmptyState(Ico.Info, "Hat nicht geklappt", l.message) { TbButton("Nochmal", { retry++ }, icon = Ico.Repeat) }
            is VLoad.Done -> if (l.res.items.isEmpty()) EmptyState(Ico.Search, "Nichts gefunden", "Zu „${l.res.core}“ gibt es gerade keine anderen Versionen.")
            else {
                val counts = l.res.items.groupingBy { it.kind }.eachCount()
                LazyRow(Modifier.fillMaxWidth().padding(top = 4.dp, bottom = 6.dp), contentPadding = PaddingValues(horizontal = 20.dp),
                    horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    item { FilterChip("Alle ${l.res.items.size}", filter == null) { filter = null } }
                    items(l.res.kinds.filter { (counts[it.first] ?: 0) > 0 }, key = { it.first }) { (id, name) ->
                        FilterChip("$name ${counts[id]}", filter == id) { filter = id }
                    }
                }
                if (filter == "andere" || (filter == null && (counts["andere"] ?: 0) > 0)) Text(
                    "Andere Künstler: Covers und Versionen mit gleichem Titel – bei sehr häufigen Titeln kann auch ein anderer Song dabei sein.",
                    style = TbType.small, color = Tb.text3, modifier = Modifier.padding(horizontal = 20.dp, vertical = 4.dp))
                LazyColumn(contentPadding = PaddingValues(start = 10.dp, end = 10.dp, top = 4.dp, bottom = 24.dp)) {
                    var last: String? = null
                    shown.forEachIndexed { i, v ->
                        if (filter == null && v.kind != last) {
                            val name = l.res.kinds.firstOrNull { it.first == v.kind }?.second ?: v.kind
                            item(key = "h-${v.kind}") { SectionLabel(name) }
                        }
                        last = v.kind
                        item(key = "$i-${v.track.key}") {
                            Row(
                                Modifier.fillMaxWidth().clip(RoundedCornerShape(Tb.radiusSm)).clickable { sheet = v }.padding(horizontal = 10.dp, vertical = 8.dp),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Cover(v.track.cover, 44.dp)
                                Spacer(Modifier.width(12.dp))
                                Column(Modifier.weight(1f)) {
                                    TrackLine(v.track.title, v.track.artist)
                                    Text(v.label, style = TbType.small, color = Tb.accent, maxLines = 1, overflow = TextOverflow.Ellipsis)
                                }
                                v.track.durationMs?.let { Text(Fmt.duration(it), style = TbType.small, color = Tb.text3) }
                            }
                        }
                    }
                }
            }
        }
    }
    sheet?.let { v ->
        val s = v.track
        ModalBottomSheet(onDismissRequest = { sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = Tb.bg1) {
            Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Cover(s.cover, 64.dp)
                    Spacer(Modifier.width(14.dp))
                    Column(Modifier.weight(1f)) {
                        TrackLine(s.title, s.artist)
                        Text(v.label, style = TbType.small, color = Tb.accent)
                    }
                }
                Row(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    val done = load as? VLoad.Done
                    if (s.playable && done != null) TbButton("Reinhören", {
                        val list = done.res.items.filter { filter == null || it.kind == filter }.map { it.track }
                        Player.play(list, list.indexOf(s).coerceAtLeast(0), "Versionen von ${t.title}"); sheet = null
                    }, kind = BtnKind.Primary, icon = Ico.Play)
                    TbButton("Zur Playlist", { pick = s; sheet = null }, icon = Ico.Plus)
                }
                SectionLabel("Anhören & öffnen")
                LinkGrid(s, emptyMap())
            }
        }
    }
    pick?.let { PlaylistPicker(it) { pick = null } }
}
