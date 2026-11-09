package de.bs002.tunebridge.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.Player
import de.bs002.tunebridge.ui.screens.LinkGrid
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbType
import kotlinx.coroutines.delay

/** Leiste über der Navigation, solange eine Hörprobe läuft: Vor/Zurück, Pause, „Öffnen“ in der Musik-App. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MiniPlayer(modifier: Modifier = Modifier) {
    val s by Player.state.collectAsState()
    val t = s.current ?: return
    var open by remember { mutableStateOf(false) }
    var progress by remember { mutableFloatStateOf(0f) }
    LaunchedEffect(s.index, s.playing) {
        while (true) { progress = Player.progress(); delay(400) }
    }
    Column(Modifier.fillMaxWidth().background(Tb.bg2).then(modifier)) {
        LinearProgressIndicator(progress = { progress }, modifier = Modifier.fillMaxWidth().height(2.dp), color = Tb.accent, trackColor = Tb.bg3)
        Row(Modifier.fillMaxWidth().padding(start = 12.dp, end = 4.dp, top = 6.dp, bottom = 6.dp), verticalAlignment = Alignment.CenterVertically) {
            Row(Modifier.weight(1f).clickable { open = true }, verticalAlignment = Alignment.CenterVertically) {
                Cover(t.cover, 40.dp)
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(t.title, style = TbType.bodyStrong, color = Tb.text, maxLines = 1)
                    val sub = listOfNotNull(t.artist.ifBlank { null }, if (s.queue.size > 1) "${s.index + 1}/${s.queue.size}" else null, "Hörprobe")
                    Text(sub.joinToString(" · "), style = TbType.small, color = Tb.text3, maxLines = 1)
                }
            }
            if (s.queue.size > 1) IconBtn(Ico.Prev, "Zurück", { Player.prev() }, tint = if (s.hasPrev) Tb.text2 else Tb.text3)
            if (s.loading) CircularProgressIndicator(Modifier.padding(10.dp).size(20.dp), color = Tb.accent, strokeWidth = 2.dp)
            else IconBtn(if (s.playing) Ico.Pause else Ico.Play, if (s.playing) "Pause" else "Abspielen", { Player.playPause() }, tint = Tb.text)
            if (s.queue.size > 1) IconBtn(Ico.Next, "Weiter", { Player.next() }, tint = if (s.hasNext) Tb.text2 else Tb.text3)
            IconBtn(Ico.X, "Schließen", { Player.stop() }, tint = Tb.text3)
        }
    }
    if (open) ModalBottomSheet(onDismissRequest = { open = false }, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = Tb.bg1) {
        Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
            Text(t.title, style = TbType.heading, color = Tb.text)
            Text(t.artist, style = TbType.body, color = Tb.text2)
            Text("Hier läuft eine 30-Sekunden-Hörprobe. Den ganzen Song hörst du in deiner Musik-App:",
                style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 10.dp, bottom = 12.dp))
            LinkGrid(t, emptyMap())
        }
    }
}
