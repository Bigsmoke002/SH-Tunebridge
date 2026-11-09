package de.bs002.tunebridge.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.sync.ShazamRoot
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.components.TbCard
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType
import kotlinx.coroutines.launch

/** Mehr › Shazam-App: eigenen Shazam-Verlauf per Root übernehmen – vorher einmal ausdrücklich warnen. */
@Composable
fun ShazamRootCard(toast: (String) -> Unit) {
    val ctx = LocalContext.current
    val s by App.repo.settings.collectAsState()
    val scope = rememberCoroutineScope()
    var warn by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf<String?>(null) }
    val su = remember { ShazamRoot.hasSu() }

    fun run() {
        if (busy != null) return
        busy = "Frage Root-Zugriff an …"
        scope.launch {
            runCatching { ShazamRoot.import(ctx) { busy = it } }
                .onSuccess { r ->
                    toast(if (r.added == 0) "Nichts Neues – ${r.found} Shazams waren schon da" else "${r.added} Shazams übernommen" +
                        (if (r.already > 0) ", ${r.already} schon da" else ""))
                    if (r.added > 0) App.listener.autoSync()
                }
                .onFailure { toast(it.message ?: "Auslesen hat nicht geklappt") }
            busy = null
        }
    }

    TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(40.dp).clip(CircleShape).background(Tb.bg3), contentAlignment = Alignment.Center) { TbIcon(Ico.Shield, Tb.danger, 20.dp) }
            Spacer(Modifier.width(14.dp))
            Column(Modifier.weight(1f)) {
                Text("Verlauf aus der Shazam-App", style = TbType.bodyStrong, color = Tb.text)
                Text("Nur mit Root – nur für erfahrene Nutzer, auf eigene Gefahr.", style = TbType.small, color = Tb.danger,
                    modifier = Modifier.padding(top = 2.dp))
                Text(
                    if (su) "Übernimmt deine eigenen Shazams (Titel, Künstler, Zeitpunkt) in den Verlauf."
                    else "Hier wurde kein Root gefunden. Ohne Root: Songs aus Shazam teilen oder am PC die Shazam-Datenkopie laden.",
                    style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 2.dp),
                )
            }
        }
        if (su) {
            Spacer(Modifier.height(12.dp))
            TbButton(busy ?: "Shazam-Verlauf auslesen", {
                if (s.rootAck < ShazamRoot.WARNING_VERSION) warn = true else run()
            }, kind = BtnKind.Ghost, icon = Ico.Shield, enabled = busy == null)
        }
    }

    if (warn) RootWarning(onCancel = { warn = false }) {
        App.repo.updateSettings { it.copy(rootAck = ShazamRoot.WARNING_VERSION) }
        warn = false
        run()
    }
}

@Composable
private fun RootWarning(onCancel: () -> Unit, onAccept: () -> Unit) {
    var sure by remember { mutableStateOf(false) }
    AlertDialog(
        onDismissRequest = onCancel, containerColor = Tb.bg2,
        icon = { TbIcon(Ico.Shield, Tb.danger, 28.dp) },
        title = { Text("Achtung: Root – nur für erfahrene Nutzer", style = TbType.title, color = Tb.danger) },
        text = {
            Column(Modifier.heightIn(max = 520.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text("Diese Funktion braucht Root-Rechte. Sie liest die Datenbank der Shazam-App direkt aus deren geschütztem Speicher – " +
                    "das geht nur, weil Root den Schutz von Android aushebelt.", style = TbType.body, color = Tb.text2)
                Text("Root ist riskant: Ein falsch eingerichtetes Root, ein fehlerhafter Root-Manager oder unsachgemäßer Gebrauch können zu " +
                    "Datenverlust, Sicherheitslücken, Verlust der Garantie oder einem Handy führen, das nicht mehr startet. " +
                    "Nutze das nur, wenn du wirklich weißt, was Root bedeutet und was du tust.", style = TbType.bodyStrong, color = Tb.danger)
                Text("Gelesen werden nur Song-Nummer, Titel, Künstler und Zeitpunkt deiner eigenen Shazams. Nicht gelesen: Standort, " +
                    "Audio-Signatur, Konto- und Anmeldedaten. Die Kopie wird sofort gelöscht, an der Shazam-App wird nichts verändert. " +
                    "Fehlen Angaben, fragt die App sie bei Shazam nach (wie beim Teilen eines Songs).", style = TbType.body, color = Tb.text2)
                Text("Shazam/Apple bieten dafür keine Schnittstelle; nach einem Shazam-Update kann es nicht mehr funktionieren. " +
                    "Nur für deine eigenen Daten verwenden.", style = TbType.body, color = Tb.text2)
                Text("Nutzung auf eigene Gefahr und eigene Verantwortung. Der Entwickler übernimmt – soweit gesetzlich zulässig – keine " +
                    "Haftung für Schäden, Datenverlust oder Folgen unsachgemäßen Gebrauchs. Unberührt bleibt die gesetzliche Haftung " +
                    "für Vorsatz, grobe Fahrlässigkeit und Schäden an Leben, Körper oder Gesundheit.", style = TbType.body, color = Tb.danger)
                val shape = RoundedCornerShape(6.dp)
                Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).clickable { sure = !sure }.padding(vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically) {
                    Box(Modifier.size(22.dp).clip(shape).background(if (sure) Tb.danger else Tb.bg3).border(1.dp, if (sure) Tb.danger else Tb.danger.copy(alpha = 0.6f), shape),
                        contentAlignment = Alignment.Center) { if (sure) TbIcon(Ico.Check, Tb.bg0, 16.dp) }
                    Spacer(Modifier.width(12.dp))
                    Text("Ich weiß, was Root ist, habe es selbst eingerichtet und nutze diese Funktion auf eigene Verantwortung.",
                        style = TbType.body, color = Tb.text)
                }
            }
        },
        confirmButton = { TbButton("Verstanden – auslesen", onAccept, kind = BtnKind.Danger, enabled = sure) },
        dismissButton = { TbButton("Abbrechen", onCancel, kind = BtnKind.Ghost) },
    )
}
