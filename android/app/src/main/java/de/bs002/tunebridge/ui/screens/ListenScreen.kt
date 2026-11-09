package de.bs002.tunebridge.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.animation.AnimatedContent
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInVertically
import androidx.compose.animation.togetherWith
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import android.app.Activity
import android.media.projection.MediaProjectionManager
import android.os.Build
import androidx.compose.material3.AlertDialog
import de.bs002.tunebridge.audio.CaptureService
import androidx.compose.material3.Text
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
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import de.bs002.tunebridge.App
import de.bs002.tunebridge.Listener
import de.bs002.tunebridge.R
import de.bs002.tunebridge.data.Recognition
import de.bs002.tunebridge.ui.Fmt
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.Cover
import de.bs002.tunebridge.ui.components.GenreChip
import de.bs002.tunebridge.ui.components.Notice
import de.bs002.tunebridge.ui.components.Orb
import de.bs002.tunebridge.ui.components.OrbMode
import de.bs002.tunebridge.ui.components.SectionLabel
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.components.TbCard
import de.bs002.tunebridge.ui.components.TrackLine
import de.bs002.tunebridge.ui.shownGenre
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType
import kotlinx.coroutines.delay

@Composable
fun ListenScreen(openSong: (String) -> Unit, openPc: () -> Unit) {
    val ctx = LocalContext.current
    val listener = App.listener
    val state by listener.state.collectAsState()
    val settings by App.repo.settings.collectAsState()
    val history by App.repo.history.collectAsState()
    var askMic by remember { mutableStateOf(false) }
    var askSystem by remember { mutableStateOf(false) }
    var askPhoneMusic by remember { mutableStateOf<Int?>(null) }
    val projection by CaptureService.projection.collectAsState()

    // Handy-Ton: System-Dialog „Aufnahme starten“ – danach übernimmt der Vordergrund-Dienst und erkennt gleich
    val capture = rememberLauncherForActivityResult(ActivityResultContracts.StartActivityForResult()) { r ->
        val data = r.data
        if (r.resultCode == Activity.RESULT_OK && data != null) CaptureService.begin(ctx, r.resultCode, data, listen = true)
    }
    val notify = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { }
    var again by remember { mutableStateOf(0) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { ok ->
        if (ok) again++
    }
    fun go(seconds: Int? = null, micAnyway: Boolean = false) {
        if (listener.busy) { listener.cancel(); return }
        val system = App.repo.settings.value.system
        // Musik läuft auf diesem Handy: Das Mikrofon hört den eigenen Lautsprecher schlecht (Android filtert ihn) –
        // Handy-Ton hört digital mit und klappt viel zuverlässiger.
        if (!system && !micAnyway && ctx.getSystemService(android.media.AudioManager::class.java)?.isMusicActive == true) {
            askPhoneMusic = seconds ?: settings.seconds; return
        }
        if (system && !App.repo.settings.value.systemAck) { askSystem = true; return }
        if (!system && !App.repo.settings.value.micAck) { askMic = true; return }
        val granted = ContextCompat.checkSelfPermission(ctx, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED
        if (!granted) { permission.launch(Manifest.permission.RECORD_AUDIO); return }
        if (!system) { listener.start(seconds ?: settings.seconds); return }
        if (CaptureService.projection.value != null) { listener.start(seconds ?: settings.seconds, system = true); return }
        if (Build.VERSION.SDK_INT >= 33 &&
            ContextCompat.checkSelfPermission(ctx, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
            notify.launch(Manifest.permission.POST_NOTIFICATIONS)
        }
        val mpm = ctx.getSystemService(MediaProjectionManager::class.java)
        capture.launch(mpm.createScreenCaptureIntent())
    }
    LaunchedEffect(again) { if (again > 0) go() }
    // Schnellkachel, Widget, Kurzbefehl
    val request by App.listenRequest.collectAsState()
    LaunchedEffect(request) {
        val sys = request ?: return@LaunchedEffect
        App.listenRequest.value = null
        if (App.repo.settings.value.system != sys) App.repo.updateSettings { it.copy(system = sys) }
        if (!listener.busy) go()
    }

    if (askMic) MicNotice(
        onOk = { App.repo.updateSettings { it.copy(micAck = true) }; askMic = false; go() },
        onCancel = { askMic = false },
    )
    askPhoneMusic?.let { secs ->
        AlertDialog(
            onDismissRequest = { askPhoneMusic = null }, containerColor = Tb.bg2,
            title = { Text("Musik läuft auf diesem Handy", style = TbType.title, color = Tb.text) },
            text = {
                Text("Über das Mikrofon klappt das oft nicht – Android filtert den eigenen Lautsprecher heraus. " +
                    "„Handy-Ton“ hört direkt mit, was das Handy abspielt, und erkennt viel zuverlässiger.",
                    style = TbType.body, color = Tb.text2)
            },
            confirmButton = {
                TbButton("Handy-Ton nehmen", {
                    askPhoneMusic = null
                    App.repo.updateSettings { it.copy(system = true) }
                    go(secs)
                }, kind = BtnKind.Primary)
            },
            dismissButton = { TbButton("Trotzdem Mikrofon", { askPhoneMusic = null; go(secs, micAnyway = true) }, kind = BtnKind.Ghost) },
        )
    }
    if (askSystem) SystemNotice(
        onOk = { App.repo.updateSettings { it.copy(systemAck = true) }; askSystem = false; go() },
        onCancel = { askSystem = false },
    )

    Column(
        Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(horizontal = 20.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Row(Modifier.fillMaxWidth().padding(top = 14.dp), verticalAlignment = Alignment.CenterVertically) {
            Image(painterResource(R.drawable.logo), null, Modifier.size(26.dp))
            Spacer(Modifier.width(10.dp))
            Text("SH-Tunebridge", style = TbType.heading, color = Tb.text, modifier = Modifier.weight(1f))
            PcBadge(settings.pcs, openPc)
        }
        Spacer(Modifier.height(36.dp))

        val (mode, progress, bands) = when (val s = state) {
            is Listener.State.Recording -> Triple(OrbMode.Live, s.progress, s.bands)
            is Listener.State.Analysing -> Triple(OrbMode.Thinking, 1f, FloatArray(0))
            else -> Triple(OrbMode.Idle, 0f, FloatArray(0))
        }
        Box(Modifier.fillMaxWidth().padding(bottom = 22.dp)) {
            Segmented(listOf(false, true), settings.system, { if (it) "Handy-Ton" else "Mikrofon" }) { v ->
                if (!listener.busy) App.repo.updateSettings { it.copy(system = v) }
            }
        }
        Orb(mode, progress, bands, onClick = { go() })
        Spacer(Modifier.height(22.dp))
        StatusText(state, settings.system)
        if (settings.system && projection != null && !listener.busy) {
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(7.dp).clip(CircleShape).background(Tb.accent))
                Spacer(Modifier.width(7.dp))
                Text("Handy-Ton freigegeben", style = TbType.small, color = Tb.text3)
                Spacer(Modifier.width(10.dp))
                TbButton("Beenden", { CaptureService.stop(ctx) }, kind = BtnKind.Ghost, small = true)
            }
        }
        Spacer(Modifier.height(14.dp))
        Actions(state, onRetry = { go() }, onLonger = { go(20) }, openSong = openSong)

        val recent = history.take(5).filter { (state as? Listener.State.Found)?.rec?.uid != it.uid }
        if (recent.isNotEmpty()) {
            SectionLabel("Zuletzt erkannt", Modifier.padding(top = 12.dp))
            TbCard(Modifier.fillMaxWidth(), padding = 4.dp) {
                recent.forEach { SongRow(it, onClick = { openSong(it.uid) }) }
            }
        }
        Spacer(Modifier.height(24.dp))
    }
}

@Composable
private fun StatusText(state: Listener.State, system: Boolean) {
    val sys = system || App.listener.lastSystem
    val (title, sub) = when (state) {
        Listener.State.Idle -> "Zum Erkennen tippen" to
            if (system) "Erkennt, was gerade auf dem Handy spielt – Kopfhörer egal" else "Handy Richtung Musik halten – 10 Sekunden reichen"
        is Listener.State.Recording -> "Höre zu …" to "Tippen bricht ab"
        Listener.State.Analysing -> "Erkenne …" to "Fingerabdruck geht an Shazam – kein Ton"
        is Listener.State.Found -> (if (state.unsure) "Erkannt – aber unsicher" else "Erkannt") to Fmt.ago(state.rec.ts)
        is Listener.State.NotFound -> "Nichts erkannt" to "Ton kam an (${state.levelDb.toInt()} dB) – an einer anderen Stelle nochmal probieren"
        is Listener.State.Silent -> "Kein Ton angekommen" to
            if (sys && App.listener.lastSystem) "Spielt gerade etwas? Manche Apps (z. B. mit Kopierschutz) sperren das Mithören – dann das Mikrofon nehmen."
            else "Pegel ${state.levelDb.toInt()} dB – näher an die Musik oder lauter machen"
        is Listener.State.Limited -> "Shazam macht eine Pause" to state.message
        is Listener.State.Failed -> "Hat nicht geklappt" to state.message
    }
    AnimatedContent(title to sub, transitionSpec = { fadeIn() togetherWith fadeOut() }, label = "status") { (t, s) ->
        Column(Modifier.fillMaxWidth().heightIn(min = 44.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Text(t, style = TbType.heading, color = Tb.text, textAlign = TextAlign.Center)
            Spacer(Modifier.height(3.dp))
            Text(s, style = TbType.small, color = Tb.text3, textAlign = TextAlign.Center)
        }
    }
}

@Composable
private fun Actions(state: Listener.State, onRetry: () -> Unit, onLonger: () -> Unit, openSong: (String) -> Unit) {
    AnimatedContent(state::class, transitionSpec = { (fadeIn() + slideInVertically { it / 6 }) togetherWith fadeOut() }, label = "aktionen") { _ ->
        when (state) {
            is Listener.State.Found -> FoundCard(state.rec, state.unsure, openSong)
            is Listener.State.NotFound -> Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TbButton("Nochmal", onRetry, icon = Ico.Repeat)
                TbButton("Länger zuhören (20 s)", onLonger, kind = BtnKind.Ghost)
            }
            is Listener.State.Limited -> Countdown(state.waitSeconds)
            is Listener.State.Failed, is Listener.State.Silent -> TbButton("Nochmal versuchen", onRetry, icon = Ico.Repeat)
            else -> Spacer(Modifier.height(1.dp))
        }
    }
}

@Composable
private fun Countdown(seconds: Int) {
    var left by remember(seconds) { mutableIntStateOf(seconds) }
    LaunchedEffect(seconds) { while (left > 0) { delay(1000); left-- }; App.listener.reset() }
    Text(if (left > 0) "wieder frei in $left s" else "wieder frei", style = TbType.small, color = Tb.warn)
}

@Composable
private fun FoundCard(rec: Recognition, unsure: Boolean, openSong: (String) -> Unit) {
    Column(Modifier.fillMaxWidth()) {
        if (unsure) {
            Notice("Nur mit Tempo-Abweichung gefunden – das passiert bei Slowed-/Sped-up-Versionen oder ähnlichen Songs. Stimmt der Treffer?") {
                Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TbButton("Stimmt", {
                        App.repo.updateExtra(rec.uid, kotlinx.serialization.json.JsonObject(rec.extra - "unsure" + ("confirmed" to kotlinx.serialization.json.JsonPrimitive(true))))
                        App.listener.reset()
                    }, kind = BtnKind.Primary, icon = Ico.Check, small = true)
                    TbButton("Falsch", { App.repo.delete(rec.uid); App.listener.reset() }, kind = BtnKind.Ghost, small = true)
                }
            }
            Spacer(Modifier.height(10.dp))
        }
        TbCard(Modifier.fillMaxWidth(), padding = 12.dp, onClick = { openSong(rec.uid) }) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Cover(rec.track.cover, 64.dp)
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    TrackLine(rec.track.title, rec.track.artist)
                    Spacer(Modifier.height(8.dp))
                    GenreChip(rec.shownGenre)
                }
                TbIcon(Ico.Chevron, Tb.text3, 18.dp)
            }
        }
    }
}

@Composable
fun SongRow(rec: Recognition, onClick: () -> Unit, showDay: Boolean = false, showSource: Boolean = false) {
    val genre = rec.shownGenre
    val fromPc = showSource && !rec.host.startsWith("Handy")
    Row(
        Modifier.fillMaxWidth().clip(androidx.compose.foundation.shape.RoundedCornerShape(Tb.radiusSm)).clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Cover(rec.track.cover, 48.dp)
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            TrackLine(rec.track.title, rec.track.artist)
            if (genre != null || fromPc) Row(Modifier.padding(top = 3.dp), verticalAlignment = Alignment.CenterVertically) {
                if (genre != null) {
                    Box(Modifier.size(6.dp).clip(CircleShape).background(de.bs002.tunebridge.ui.theme.GenreColors.of(genre)))
                    Spacer(Modifier.width(6.dp))
                    Text(genre, style = TbType.small, color = Tb.text3, maxLines = 1,
                        overflow = androidx.compose.ui.text.style.TextOverflow.Ellipsis, modifier = Modifier.weight(1f, fill = false))
                }
                if (fromPc) {
                    if (genre != null) Text("  ·  ", style = TbType.small, color = Tb.text3)
                    TbIcon(Ico.Monitor, Tb.text3, 12.dp)
                    Spacer(Modifier.width(4.dp))
                    Text("PC", style = TbType.small, color = Tb.text3)
                }
            }
        }
        Spacer(Modifier.width(10.dp))
        Text(if (showDay) Fmt.ago(rec.ts) else Fmt.clock(rec.ts), style = TbType.small, color = Tb.text3,
            modifier = Modifier.align(Alignment.Top).padding(top = 3.dp))
    }
}

@Composable
private fun PcBadge(pcs: List<de.bs002.tunebridge.data.Repository.PcLink>, onClick: () -> Unit) {
    val near = pcs.filter { App.sync.reachable(it).isNotEmpty() }
    val last = pcs.maxOfOrNull { it.lastSync } ?: 0.0
    val err = near.isNotEmpty() && near.all { it.lastSyncError != null }
    val color = when { pcs.isEmpty() || near.isEmpty() -> Tb.text3; err -> Tb.warn; else -> Tb.accent }
    Row(
        Modifier.clip(CircleShape).background(Tb.bg2).clickable(onClick = onClick).padding(horizontal = 11.dp, vertical = 6.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(7.dp).clip(CircleShape).background(color))
        Spacer(Modifier.width(7.dp))
        Text(
            when {
                pcs.isEmpty() -> "PC koppeln"
                !de.bs002.tunebridge.sync.Nets.allowed() -> "Abgleich aus"
                near.isEmpty() -> if (pcs.size == 1) "${pcs[0].pcName} · nicht im Netz" else "${pcs.size} PCs · nicht im Netz"
                err -> "PC offline"
                pcs.size == 1 && last > 0 -> "PC · ${Fmt.ago(last)}"
                pcs.size > 1 -> "${near.size}/${pcs.size} PCs${if (last > 0) " · ${Fmt.ago(last)}" else ""}"
                else -> "PC"
            },
            style = TbType.small, color = Tb.text2, maxLines = 1,
        )
    }
}

@Composable
private fun SystemNotice(onOk: () -> Unit, onCancel: () -> Unit) {
    AlertDialog(
        onDismissRequest = onCancel,
        containerColor = Tb.bg2,
        icon = { TbIcon(Ico.Wave, Tb.accent, 26.dp) },
        title = { Text("Handy-Ton erkennen", style = TbType.title, color = Tb.text) },
        text = {
            Column(Modifier.heightIn(max = 480.dp).verticalScroll(rememberScrollState())) {
                Text("SH-Tunebridge hört dann direkt, was auf dem Handy abgespielt wird (z. B. Videos, Streams, Musik-Apps) – " +
                    "ohne Mikrofon, auch mit Kopfhörern.", style = TbType.body, color = Tb.text2)
                Spacer(Modifier.height(10.dp))
                Text("Android fragt dafür im System-Dialog nach („Bildschirm teilen“). Wähle dort „Gesamten Bildschirm teilen“, damit jede App " +
                    "gehört werden kann – bei „Eine App teilen“ nur diese eine. Genutzt wird nur der Ton, kein Bild. Solange die Freigabe besteht, siehst du eine Benachrichtigung; „Beenden“ dort oder hier nimmt sie zurück, " +
                    "nach 15 Minuten ohne Erkennen endet sie von selbst.", style = TbType.body, color = Tb.text2)
                Spacer(Modifier.height(10.dp))
                Text("Gehört wird nur nach dem Tippen (standardmäßig 10 Sekunden), nur im Arbeitsspeicher, nie gespeichert. " +
                    "An Shazam geht wie immer nur ein Fingerabdruck – kein Ton.", style = TbType.body, color = Tb.text2)
                Spacer(Modifier.height(10.dp))
                Text("Telefonate und Sprachanrufe gibt Android nie heraus. Apps können das Mithören sperren (z. B. wegen Kopierschutz) – " +
                    "das wird nicht umgangen; nimm dann das Mikrofon.", style = TbType.body, color = Tb.text2)
                Spacer(Modifier.height(10.dp))
                Text("Bitte nur zum Erkennen von Musik nutzen und keine Gespräche anderer mithören (§ 201 StGB).",
                    style = TbType.body, color = Tb.danger)
            }
        },
        confirmButton = { TbButton("Verstanden", onOk, kind = BtnKind.Primary) },
        dismissButton = { TbButton("Abbrechen", onCancel, kind = BtnKind.Ghost) },
    )
}

@Composable
private fun MicNotice(onOk: () -> Unit, onCancel: () -> Unit) {
    AlertDialog(
        onDismissRequest = onCancel,
        containerColor = Tb.bg2,
        icon = { TbIcon(Ico.Mic, Tb.accent, 26.dp) },
        title = { Text("Bevor das Mikrofon an geht", style = TbType.title, color = Tb.text) },
        text = {
            Column {
                Text("SH-Tunebridge hört nur, solange du auf den Kreis getippt hast – standardmäßig 10 Sekunden. " +
                    "Die Aufnahme bleibt im Arbeitsspeicher und wird sofort verworfen; an Shazam geht nur ein Fingerabdruck, aus dem sich kein Ton zurückgewinnen lässt.",
                    style = TbType.body, color = Tb.text2)
                Spacer(Modifier.height(12.dp))
                Text("Bitte nimm keine Gespräche anderer auf: Das nicht öffentlich gesprochene Wort ist gesetzlich geschützt (§ 201 StGB).",
                    style = TbType.body, color = Tb.text2)
            }
        },
        confirmButton = { TbButton("Verstanden", onOk, kind = BtnKind.Primary) },
        dismissButton = { TbButton("Abbrechen", onCancel, kind = BtnKind.Ghost) },
    )
}
