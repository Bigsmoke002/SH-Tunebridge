package de.bs002.tunebridge.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.LinearProgressIndicator
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.BuildConfig
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.Hairline
import de.bs002.tunebridge.ui.components.SettingRow
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbType
import de.bs002.tunebridge.update.Updater
import kotlinx.coroutines.launch

/** Mehr › Über: Version, Update suchen/laden/installieren, automatische Prüfung. */
@Composable
fun UpdateSection() {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val st by Updater.state.collectAsState()
    val s by App.repo.settings.collectAsState()
    Text("SH-Tunebridge ${BuildConfig.VERSION_NAME}", style = TbType.bodyStrong, color = Tb.text)
    if (!Updater.supported) {
        Text("Entwicklerversion – Updates kommen per adb.", style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 2.dp))
        return
    }
    Spacer(Modifier.height(10.dp))
    when (val x = st) {
        is Updater.State.Available -> UpdateOffer(x.update) { Updater.start(ctx, x.update) }
        is Updater.State.Downloading -> DownloadProgress(x)
        is Updater.State.Ready -> InstallButton(x)
        else -> {
            Text(
                when (x) {
                    Updater.State.Checking -> "Suche nach Updates …"
                    Updater.State.Current -> "Du hast die neueste Version."
                    is Updater.State.Failed -> x.message
                    else -> if (s.lastUpdateCheck > 0) "Zuletzt gesucht ${de.bs002.tunebridge.ui.Fmt.ago(s.lastUpdateCheck)}" else "Noch nicht nach Updates gesucht."
                },
                style = TbType.small, color = if (x is Updater.State.Failed) Tb.danger else Tb.text3,
            )
            Spacer(Modifier.height(10.dp))
            TbButton("Nach Updates suchen", { scope.launch { Updater.check() } }, kind = BtnKind.Ghost, icon = Ico.Sync,
                enabled = x != Updater.State.Checking)
        }
    }
    Spacer(Modifier.height(8.dp))
    Hairline()
    SettingRow("Automatisch nach Updates suchen", "Einmal am Tag beim Öffnen fragt die App bei GitHub nach – GitHub sieht dabei deine IP-Adresse. " +
        "Jede Version ist mit dem Release-Schlüssel signiert und wird vor dem Installieren geprüft.", s.autoUpdate) { v ->
        App.repo.updateSettings { it.copy(autoUpdate = v) }
    }
}

private fun mb(b: Long) = "%.1f".format(java.util.Locale.GERMANY, b / 1_048_576.0)

/** Balken + „12,3 von 40,1 MB · 31 %“. */
@Composable
fun DownloadProgress(x: Updater.State.Downloading, compact: Boolean = false) {
    val pct = (x.progress * 100).toInt()
    Row(Modifier.fillMaxWidth()) {
        Text(if (x.version.isNotEmpty()) "Update ${x.version} wird geladen …" else "Update wird geladen …",
            style = if (compact) TbType.small else TbType.body, color = Tb.text2, modifier = Modifier.weight(1f))
        Text("$pct %", style = TbType.small, color = Tb.accent)
    }
    Spacer(Modifier.height(6.dp))
    LinearProgressIndicator(progress = { x.progress }, modifier = Modifier.fillMaxWidth(), color = Tb.accent, trackColor = Tb.bg3)
    if (!compact && x.total > 0) Text("${mb(x.done)} von ${mb(x.total)} MB – danach wird die Prüfsumme kontrolliert. Du kannst die App dabei weiter benutzen.",
        style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 6.dp))
}

/** Statusleiste über dem Mini-Player: Update lädt (mit Balken) bzw. ist bereit – auf jeder Seite sichtbar. */
@Composable
fun UpdateBanner(openMore: () -> Unit) {
    val ctx = LocalContext.current
    val st by Updater.state.collectAsState()
    val x = st
    if (x !is Updater.State.Downloading && x !is Updater.State.Ready) return
    Column(
        Modifier.fillMaxWidth().background(Tb.bg2).clickable(onClick = openMore).padding(horizontal = 16.dp, vertical = 10.dp),
    ) {
        when (x) {
            is Updater.State.Downloading -> DownloadProgress(x, compact = true)
            is Updater.State.Ready -> Row(verticalAlignment = Alignment.CenterVertically) {
                Text("Update ${x.update.version} geladen und geprüft", style = TbType.small, color = Tb.text, modifier = Modifier.weight(1f))
                TbButton("Installieren", {
                    if (Updater.canInstall(ctx)) Updater.install(ctx, x.apk) else openMore()
                }, kind = BtnKind.Primary, small = true, icon = Ico.Check)
            }
            else -> Unit
        }
    }
    Hairline()
}

@Composable
private fun UpdateOffer(u: Updater.Update, load: () -> Unit) {
    Text("Version ${u.version} ist da", style = TbType.bodyStrong, color = Tb.accent)
    if (u.notes.isNotBlank()) Text(u.notes.take(600), style = TbType.small, color = Tb.text2, modifier = Modifier.padding(top = 4.dp))
    Text("Signatur geprüft · ${"%.1f".format(u.size / 1_048_576.0)} MB", style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 4.dp))
    Spacer(Modifier.height(10.dp))
    TbButton("Laden & installieren", load, kind = BtnKind.Primary, icon = Ico.Arrow)
}

@Composable
private fun InstallButton(r: Updater.State.Ready) {
    val ctx = LocalContext.current
    Text("Version ${r.update.version} geladen und geprüft (SHA-256 passt).", style = TbType.small, color = Tb.text2)
    Spacer(Modifier.height(10.dp))
    if (!Updater.canInstall(ctx)) {
        Text("Android fragt einmal, ob SH-Tunebridge Apps installieren darf („Unbekannte Apps installieren“). Danach hier nochmal tippen.",
            style = TbType.small, color = Tb.warn)
        Spacer(Modifier.height(8.dp))
        TbButton("Erlaubnis öffnen", { Updater.openInstallSettings(ctx) }, kind = BtnKind.Ghost)
        Spacer(Modifier.height(6.dp))
    }
    TbButton("Jetzt installieren", { Updater.install(ctx, r.apk) }, kind = BtnKind.Primary, icon = Ico.Check, enabled = Updater.canInstall(ctx))
}

/** Hinweis beim Öffnen, wenn die tägliche Prüfung etwas gefunden hat. */
@Composable
fun UpdatePrompt(openMore: () -> Unit) {
    val ctx = LocalContext.current
    val st by Updater.state.collectAsState()
    var shown by remember { mutableStateOf<String?>(null) }
    val u = (st as? Updater.State.Available)?.update ?: return
    if (shown == u.version) return
    AlertDialog(
        onDismissRequest = { shown = u.version }, containerColor = Tb.bg2,
        title = { Text("Update auf ${u.version}", style = TbType.title, color = Tb.text) },
        text = {
            Column(Modifier.heightIn(max = 360.dp).verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Eine neue, signierte Version ist da. Beim Laden siehst du den Fortschritt unten in der App und in der Benachrichtigung; " +
                    "installieren bestätigst du danach selbst.", style = TbType.body, color = Tb.text2)
                if (u.notes.isNotBlank()) Text(u.notes.take(800), style = TbType.small, color = Tb.text3)
            }
        },
        confirmButton = { TbButton("Jetzt laden", { shown = u.version; Updater.start(ctx, u) }, kind = BtnKind.Primary, icon = Ico.Arrow) },
        dismissButton = {
            Row(horizontalArrangement = Arrangement.spacedBy(4.dp)) {
                TbButton("Details", { shown = u.version; openMore() }, kind = BtnKind.Ghost)
                TbButton("Später", { shown = u.version }, kind = BtnKind.Ghost)
            }
        },
    )
}
