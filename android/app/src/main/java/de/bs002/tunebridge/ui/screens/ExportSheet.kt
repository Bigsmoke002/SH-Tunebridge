package de.bs002.tunebridge.ui.screens

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.data.Export
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType

/** Format wählen und über das Android-Teilen-Menü weitergeben. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ExportSheet(title: String, items: List<Export.Item>, close: () -> Unit) {
    val ctx = LocalContext.current
    ModalBottomSheet(onDismissRequest = close, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = Tb.bg2) {
        Column(Modifier.padding(start = 20.dp, end = 20.dp, bottom = 28.dp)) {
            Text("„$title“ teilen", style = TbType.title, color = Tb.text)
            Text("${items.size} ${if (items.size == 1) "Song" else "Songs"} · nur Titel, Künstler und Links – keine Cover, keine Musik",
                style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 2.dp, bottom = 10.dp))
            Export.Format.entries.forEach { f ->
                Row(Modifier.fillMaxWidth().clickable { close(); Export.share(ctx, title, items, f) }.padding(vertical = 12.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    TbIcon(Ico.Arrow, Tb.accent, 18.dp)
                    Spacer(Modifier.width(14.dp))
                    Column {
                        Text(f.label, style = TbType.bodyStrong, color = Tb.text)
                        Text(f.hint, style = TbType.small, color = Tb.text3)
                    }
                }
            }
            Spacer(Modifier.height(4.dp))
        }
    }
}
