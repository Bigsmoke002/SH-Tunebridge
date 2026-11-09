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
import androidx.compose.foundation.lazy.itemsIndexed
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
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.Player
import de.bs002.tunebridge.data.Track
import de.bs002.tunebridge.net.Similar
import de.bs002.tunebridge.playable
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

private sealed interface Load {
    data object Busy : Load
    data class Done(val from: String, val items: List<Pair<Track, Double>>) : Load
    data object NeedConsent : Load
    data class Failed(val message: String) : Load
}

/** Ähnliche Songs zu [App.similarSeed]: vom PC, wenn erreichbar – sonst (nach Einwilligung) direkt bei Deezer. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun SimilarScreen(back: () -> Unit) {
    val seed by App.similarSeed.collectAsState()
    val settings by App.repo.settings.collectAsState()
    var load by remember { mutableStateOf<Load>(Load.Busy) }
    var retry by remember { mutableIntStateOf(0) }
    var sheet by remember { mutableStateOf<Track?>(null) }
    var pick by remember { mutableStateOf<Track?>(null) }
    val t = seed ?: run {
        Column(Modifier.fillMaxSize()) { TopBack(back); EmptyState(Ico.Search, "Kein Song gewählt", "Öffne einen Song und tippe auf „Ähnliche Songs“.") }
        return
    }

    LaunchedEffect(t, retry, settings.similarDirect) {
        load = Load.Busy
        load = try {
            val pc = runCatching { App.sync.similar(t) }.getOrNull()
            when {
                pc != null -> Load.Done("vom PC", pc)
                settings.similarDirect -> Load.Done("von Deezer", withContext(Dispatchers.IO) { Similar.find(t) })
                else -> Load.NeedConsent
            }
        } catch (e: Exception) {
            Load.Failed(e.message ?: "Hat nicht geklappt")
        }
    }

    Column(Modifier.fillMaxSize()) {
        TopBack(back)
        val done = load as? Load.Done
        ScreenHeader("Ähnlich wie", "${t.title} · ${t.artist}" + (done?.let { " · ${it.from}" } ?: "")) {
            if (done != null && done.items.any { it.first.playable }) PlayButtons(done.items.map { it.first }, "Ähnlich wie ${t.title}")
        }
        when (val l = load) {
            Load.Busy -> Box(Modifier.fillMaxWidth().padding(40.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Tb.accent) }
            Load.NeedConsent -> Column(Modifier.padding(horizontal = 20.dp)) {
                Notice("Kein PC erreichbar. Unterwegs kann die App die Vorschläge direkt bei Deezer holen: Dafür gehen Titel und " +
                    "Künstler (bzw. Deezer-Nummer/ISRC) dieses Songs an Deezer, Deezer sieht deine IP-Adresse. Ausschaltbar unter Mehr › Datenschutz.",
                    icon = Ico.Info, color = Tb.accent) {
                    Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TbButton("Erlauben & laden", { App.repo.updateSettings { it.copy(similarDirect = true) } }, kind = BtnKind.Primary, small = true)
                        TbButton("Später am PC", back, kind = BtnKind.Ghost, small = true)
                    }
                }
            }
            is Load.Failed -> EmptyState(Ico.Info, "Hat nicht geklappt", l.message) { TbButton("Nochmal", { retry++ }, icon = Ico.Repeat) }
            is Load.Done -> if (l.items.isEmpty()) EmptyState(Ico.Search, "Nichts gefunden", "Zu diesem Song gibt es gerade keine Vorschläge.")
            else LazyColumn(contentPadding = PaddingValues(start = 10.dp, end = 10.dp, top = 6.dp, bottom = 24.dp)) {
                itemsIndexed(l.items, key = { i, it -> "$i-${it.first.key}" }) { i, (s, m) ->
                    Row(
                        Modifier.fillMaxWidth().clip(RoundedCornerShape(Tb.radiusSm)).clickable { sheet = s }.padding(horizontal = 10.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Cover(s.cover, 44.dp)
                        Spacer(Modifier.width(12.dp))
                        TrackLine(s.title, s.artist, Modifier.weight(1f))
                        Text("${(m * 100).toInt()} %", style = TbType.small, color = Tb.text3)
                    }
                }
            }
        }
    }
    sheet?.let { s ->
        val done = load as? Load.Done
        ModalBottomSheet(onDismissRequest = { sheet = null }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = Tb.bg1) {
            Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Cover(s.cover, 64.dp)
                    Spacer(Modifier.width(14.dp))
                    TrackLine(s.title, s.artist, Modifier.weight(1f))
                }
                Row(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (s.playable && done != null) TbButton("Ab hier abspielen", {
                        val list = done.items.map { it.first }
                        Player.play(list, list.indexOf(s), "Ähnlich wie ${t.title}"); sheet = null
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
