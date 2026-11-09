package de.bs002.tunebridge.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.data.Repository
import de.bs002.tunebridge.ui.Fmt
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbType

/** PC-Seite: Welche Playlists dieses PCs kommen aufs Handy – alle oder eine Auswahl (wirkt beim nächsten Abgleich). */
@Composable
fun ListsOnPhone(link: Repository.PcLink, syncNow: () -> Unit) {
    var choose by remember { mutableStateOf(false) }
    val all = link.catalog
    val mode = if (link.lists == null) "all" else "some"
    Segmented(listOf("all", "some"), mode, { if (it == "all") "Alle" else "Auswahl" }) { m ->
        App.repo.setLists(link.pcId, if (m == "all") null else (link.lists ?: emptyList()))
        if (m == "some") choose = true else syncNow()
    }
    Spacer(Modifier.height(10.dp))
    Text(
        when {
            all.isEmpty() -> "Die Liste der PC-Playlists kommt mit dem nächsten Abgleich."
            link.lists == null -> "Alle ${all.size} Playlists des PCs sind auf dem Handy."
            else -> "${link.lists.count { n -> all.any { it.name == n } }} von ${all.size} Playlists sind auf dem Handy. " +
                "Was du am Handy anlegst oder befüllst, bleibt immer dabei."
        },
        style = TbType.small, color = Tb.text3,
    )
    if (link.lists != null && all.isNotEmpty()) {
        Spacer(Modifier.height(10.dp))
        TbButton("Playlists auswählen", { choose = true }, kind = BtnKind.Ghost)
    }
    if (choose && all.isNotEmpty()) Chooser(link, all) { choose = false; syncNow() }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun Chooser(link: Repository.PcLink, all: List<Repository.CatalogEntry>, done: () -> Unit) {
    var picked by remember { mutableStateOf(link.lists.orEmpty().toSet()) }
    var q by remember { mutableStateOf("") }
    ModalBottomSheet(onDismissRequest = { App.repo.setLists(link.pcId, picked.toList()); done() },
        sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = Tb.bg1) {
        Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 20.dp)) {
            Text("Playlists aufs Handy", style = TbType.title, color = Tb.text)
            Text("${picked.size} gewählt · ${Fmt.songs(all.filter { it.name in picked }.sumOf { it.n })}", style = TbType.small, color = Tb.text3,
                modifier = Modifier.padding(top = 2.dp, bottom = 10.dp))
            SearchField(q, { q = it }, placeholder = "Playlist suchen …")
            val shown = all.filter { q.isBlank() || it.name.contains(q.trim(), true) }
            LazyColumn(Modifier.fillMaxWidth().heightIn(max = 460.dp).padding(top = 6.dp)) {
                items(shown, key = { it.name }) { e ->
                    val on = e.name in picked
                    Row(Modifier.fillMaxWidth().clickable { picked = if (on) picked - e.name else picked + e.name }.padding(vertical = 2.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Checkbox(on, { picked = if (it) picked + e.name else picked - e.name },
                            colors = CheckboxDefaults.colors(checkedColor = Tb.accent, uncheckedColor = Tb.lineStrong, checkmarkColor = Tb.accentInk))
                        Column(Modifier.weight(1f)) {
                            Text(e.name, style = TbType.body, color = Tb.text, maxLines = 1)
                            Text(Fmt.songs(e.n), style = TbType.small, color = Tb.text3)
                        }
                    }
                }
            }
            Spacer(Modifier.height(12.dp))
            TbButton("Übernehmen & abgleichen", { App.repo.setLists(link.pcId, picked.toList()); done() }, kind = BtnKind.Primary)
        }
    }
}
