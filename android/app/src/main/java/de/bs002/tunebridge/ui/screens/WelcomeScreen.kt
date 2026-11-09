package de.bs002.tunebridge.ui.screens

import androidx.compose.foundation.Image
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Checkbox
import androidx.compose.material3.CheckboxDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.R
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.SettingRow
import de.bs002.tunebridge.ui.components.Hairline
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.components.TbCard
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType

/** Erster Start: kurz und ehrlich sagen, was passiert – und erst danach loslegen. */
@Composable
fun WelcomeScreen(openPrivacy: () -> Unit) {
    var read by remember { mutableStateOf(false) }
    var covers by remember { mutableStateOf(false) }
    var updates by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 24.dp)) {
        Spacer(Modifier.height(48.dp))
        Image(painterResource(R.drawable.logo), null, Modifier.size(64.dp))
        Spacer(Modifier.height(20.dp))
        Text("Willkommen bei\nSH-Tunebridge", style = TbType.display, color = Tb.text)
        Spacer(Modifier.height(10.dp))
        Text("Songs erkennen, sammeln und mit deinem PC abgleichen. Vorher kurz, was dabei passiert:",
            style = TbType.body, color = Tb.text2)
        Spacer(Modifier.height(22.dp))
        Point(Ico.Mic, "Hört nur, wenn du tippst", "10 Sekunden, nur im Arbeitsspeicher. Aufnahmen werden nie gespeichert.")
        Point(Ico.Wave, "Shazam bekommt einen Fingerabdruck", "Zahlenwerte aus der Aufnahme – kein Ton. Shazam gehört zu Apple und sieht dabei deine IP-Adresse.")
        Point(Ico.Shield, "Alles andere bleibt bei dir", "Verlauf und Playlists liegen auf dem Handy und, wenn du koppelst, auf deinem PC. Kein Konto, keine Werbung, kein Tracking.")
        Point(Ico.Monitor, "PC im WLAN", "Abgleich direkt und verschlüsselt, ohne Server dazwischen. Ob die App dafür die Netzwerke des Handys erkennen darf, fragt sie erst beim Koppeln.")
        Spacer(Modifier.height(8.dp))
        TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
            SettingRow("Cover-Bilder anzeigen", "Kommen von Apples Bildserver. Lässt sich jederzeit unter „Mehr“ ändern.", covers) { covers = it }
            if (de.bs002.tunebridge.update.Updater.supported) {
                Hairline()
                SettingRow("Automatisch nach Updates suchen", "Einmal am Tag fragt die App bei GitHub nach einer neuen, signierten Version – GitHub sieht dabei deine IP-Adresse. Installieren bestätigst du immer selbst.", updates) { updates = it }
            }
        }
        Spacer(Modifier.height(14.dp))
        Row(Modifier.fillMaxWidth().clickable { read = !read }, verticalAlignment = Alignment.CenterVertically) {
            Checkbox(read, { read = it }, colors = CheckboxDefaults.colors(checkedColor = Tb.accent, uncheckedColor = Tb.lineStrong, checkmarkColor = Tb.accentInk))
            Text("Ich habe das gelesen und bin einverstanden.", style = TbType.body, color = Tb.text2)
        }
        Text("Alle Details", style = TbType.small, color = Tb.accent, modifier = Modifier.padding(start = 48.dp).clickable(onClick = openPrivacy))
        Spacer(Modifier.height(20.dp))
        TbButton("Los geht's", {
            App.repo.updateSettings { it.copy(consent = App.CONSENT_VERSION, covers = covers, autoUpdate = updates) }
        }, kind = BtnKind.Primary, enabled = read, modifier = Modifier.fillMaxWidth())
        Spacer(Modifier.height(36.dp))
    }
}

@Composable
private fun Point(icon: Ico, title: String, text: String) {
    Row(Modifier.padding(vertical = 10.dp)) {
        TbIcon(icon, Tb.accent, 20.dp, Modifier.padding(top = 1.dp))
        Spacer(Modifier.width(14.dp))
        Column {
            Text(title, style = TbType.bodyStrong, color = Tb.text)
            Text(text, style = TbType.small, color = Tb.text2, modifier = Modifier.padding(top = 2.dp))
        }
    }
}
