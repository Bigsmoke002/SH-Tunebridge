package de.bs002.tunebridge.ui.screens

import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.data.Repository
import de.bs002.tunebridge.sync.Nets
import de.bs002.tunebridge.sync.PcSync
import de.bs002.tunebridge.ui.Fmt
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.Hairline
import de.bs002.tunebridge.ui.components.Notice
import de.bs002.tunebridge.ui.components.SectionLabel
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.components.TbCard
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType
import kotlinx.coroutines.Job
import kotlinx.coroutines.launch

private val MODES = listOf("all" to "Alle", "some" to "Bestimmte", "one" to "Nur diese")

/** Welche Adressen des PCs das Handy benutzt: alle, bestimmte (mehrere) oder genau eine. */
@Composable
fun AddrPicker(addrs: List<String>, mode: String, use: List<String>, onChange: (String, List<String>) -> Unit) {
    val nets = remember { Nets.current() }
    Segmented(MODES.map { it.first }, mode, { k -> MODES.first { it.first == k }.second }) { m ->
        val reach = addrs.filter { Nets.reachable(it, nets) }
        onChange(m, when (m) {
            "all" -> emptyList()
            "one" -> listOf(use.firstOrNull { it in addrs } ?: reach.firstOrNull() ?: addrs.first())
            else -> use.filter { it in addrs }.ifEmpty { reach.ifEmpty { addrs } }
        })
    }
    Spacer(Modifier.height(10.dp))
    addrs.forEachIndexed { i, a ->
        if (i > 0) Hairline()
        val on = mode == "all" || a in use
        val here = Nets.reachable(a, nets)
        Row(
            Modifier.fillMaxWidth().clip(RoundedCornerShape(Tb.radiusSm)).clickable(enabled = mode != "all") {
                onChange(mode, if (mode == "one") listOf(a) else if (a in use) (use - a).ifEmpty { listOf(a) } else use + a)
            }.padding(vertical = 11.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Box(
                Modifier.size(20.dp).clip(if (mode == "one") CircleShape else RoundedCornerShape(5.dp))
                    .background(if (on) Tb.accent else Tb.bg3).border(1.dp, if (on) Tb.accent else Tb.lineStrong, if (mode == "one") CircleShape else RoundedCornerShape(5.dp))
                    .alpha(if (mode == "all") 0.6f else 1f),
                contentAlignment = Alignment.Center,
            ) { if (on) TbIcon(Ico.Check, Tb.accentInk, 13.dp) }
            Spacer(Modifier.width(12.dp))
            Column(Modifier.weight(1f)) {
                Text(a, style = TbType.bodyStrong.copy(fontFamily = FontFamily.Monospace, fontSize = 14.sp), color = Tb.text)
                Text(Nets.describe(a, nets), style = TbType.small, color = Tb.text3)
            }
            Text(if (here) "hier erreichbar" else "anderes Netz", style = TbType.small, color = if (here) Tb.accent else Tb.text3)
        }
    }
}

/** Was, wann, wohin, wie – vor dem Koppeln und in den Details eines PCs. */
@Composable
fun SyncFacts(pcName: String, addrs: List<String>) {
    val me = remember { App.repo.deviceName() }
    val rows = listOf(
        "Ans PC" to "Deine Erkennungen am Handy (Song, Zeitpunkt, Shazam-Angaben, unsicher/bestätigt), gelöschte Einträge, Änderungen an Playlists, Gerätename „$me“ und App-Version.",
        "Vom PC" to "Verlauf und Playlists von $pcName (Titel, Künstler, Album, Genre, Cover- und Hörproben-Adressen). Keine Konten, Schlüssel oder Einstellungen.",
        "Wann" to "Nach jeder Erkennung, beim Öffnen der App und bei „Jetzt abgleichen“ – aber nur, wenn das Handy gerade im Netz dieses PCs ist. „Automatisch abgleichen“ unter Mehr schaltet das Automatische ab.",
        "Wohin" to addrs.joinToString("\n") { "$it  ·  ${Nets.describe(it)}" },
        "Wie" to "Direkt im eigenen Netz, Ende-zu-Ende verschlüsselt (AES-256-GCM). Kein Server dazwischen, nichts geht ins Internet.",
    )
    TbCard(Modifier.fillMaxWidth(), padding = 0.dp) {
        rows.forEachIndexed { i, (k, v) ->
            if (i > 0) Hairline()
            Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                Text(k.uppercase(), style = TbType.label, color = Tb.text3)
                Spacer(Modifier.height(4.dp))
                Text(v, style = TbType.body, color = Tb.text2)
            }
        }
    }
}

/** Zustimmung: Darf die App die eigenen Netzwerkkarten des Handys auslesen? Ohne sie kein Abgleich mit PCs. */
@Composable
fun NetConsent(onLater: (() -> Unit)? = null) {
    TbCard(Modifier.fillMaxWidth(), padding = 0.dp) {
        Column(Modifier.padding(16.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(Modifier.size(40.dp).clip(CircleShape).background(Tb.bg3), contentAlignment = Alignment.Center) { TbIcon(Ico.Key, Tb.accent, 20.dp) }
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    Text("Netzwerke des Handys erkennen?", style = TbType.bodyStrong, color = Tb.text)
                    Text("Für den Abgleich mit PCs braucht die App deine Zustimmung.", style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 2.dp))
                }
            }
        }
        listOf(
            "Was" to "Die eigenen Netzwerkkarten des Handys: IP-Adresse und Netz (z. B. 192.168.178.0/24), WLAN oder VPN.",
            "Wozu" to "Damit das Handy einen PC nur anspricht, wenn es gerade in dessen Netz ist – in fremden WLANs wird nichts gesendet.",
            "Nicht" to "Keine WLAN-Namen, kein Standort, keine anderen Geräte im Netz, keine zusätzliche Berechtigung. Nichts davon wird gespeichert oder verschickt.",
            "Widerruf" to "Jederzeit unter Mehr › Datenschutz. Danach gleicht das Handy nicht mehr mit PCs ab.",
        ).forEach { (k, v) ->
            Hairline()
            Column(Modifier.padding(horizontal = 16.dp, vertical = 12.dp)) {
                Text(k.uppercase(), style = TbType.label, color = Tb.text3)
                Spacer(Modifier.height(4.dp))
                Text(v, style = TbType.body, color = Tb.text2)
            }
        }
        Hairline()
        Row(Modifier.padding(16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TbButton("Erlauben", { App.repo.updateSettings { it.copy(netConsent = true) } }, kind = BtnKind.Primary, icon = Ico.Check)
            if (onLater != null) TbButton("Nicht jetzt", onLater, kind = BtnKind.Ghost)
        }
    }
}

/** Schritt 2 beim Koppeln: alles zeigen, ausdrücklich bestätigen, dann auf „Zulassen“ am PC warten. */
@Composable
fun PairConfirm(invite: PcSync.Invite, back: () -> Unit, done: (String) -> Unit) {
    val scope = rememberCoroutineScope()
    val consent = App.repo.settings.collectAsState().value.netConsent
    if (!consent) {
        Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
            TopBack(back)
            ScreenHeader("Mit ${invite.pcName} koppeln?")
            Column(Modifier.padding(horizontal = 20.dp)) {
                Text("Bevor die App zeigen kann, über welche Adressen sie den PC erreicht, braucht sie deine Zustimmung.",
                    style = TbType.body, color = Tb.text2)
                Spacer(Modifier.height(14.dp))
                NetConsent(onLater = back)
                Spacer(Modifier.height(32.dp))
            }
        }
        return
    }
    val reach = remember(invite) { invite.addrs.filter { Nets.reachable(it) } }
    var mode by remember { mutableStateOf("all") }
    var use by remember { mutableStateOf(reach.ifEmpty { invite.addrs }) }
    var waiting by remember { mutableStateOf<String?>(null) }        // Prüfzahl, solange auf den PC gewartet wird
    var error by remember { mutableStateOf<String?>(null) }
    var job by remember { mutableStateOf<Job?>(null) }
    val already = App.repo.settings.collectAsState().value.pcs.firstOrNull { it.pcId == invite.pcId }
    DisposableEffect(Unit) { onDispose { job?.cancel() } }

    fun request() {
        val id = PcSync.newDeviceId()
        waiting = PcSync.confirmCode(invite.code, id)
        error = null
        job = scope.launch {
            runCatching { App.sync.pair(invite, id, mode, if (mode == "all") emptyList() else use) }
                .onSuccess { link ->
                    runCatching { App.sync.sync(link.pcId) }
                    done("Gekoppelt mit ${link.pcName}")
                }
                .onFailure { if (it !is kotlinx.coroutines.CancellationException) { error = it.message ?: "Koppeln hat nicht geklappt"; waiting = null } }
        }
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        TopBack({ job?.cancel(); back() })
        ScreenHeader("Mit ${invite.pcName} koppeln?")
        Column(Modifier.padding(horizontal = 20.dp)) {
            val check = waiting
            if (check != null) {
                TbCard(Modifier.fillMaxWidth(), padding = 20.dp) {
                    Text("PRÜFZAHL", style = TbType.label, color = Tb.text3)
                    Text("${check.take(2)} ${check.drop(2)}", fontFamily = FontFamily.Monospace, fontWeight = FontWeight.SemiBold,
                        fontSize = 44.sp, letterSpacing = 4.sp, color = Tb.text, modifier = Modifier.padding(vertical = 6.dp))
                    Text("Am PC erscheint jetzt „${App.repo.deviceName()} möchte sich koppeln“. Dort muss dieselbe Zahl stehen – dann am PC „Zulassen“ klicken.",
                        style = TbType.body, color = Tb.text2)
                    Spacer(Modifier.height(16.dp))
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Pulse()
                        Spacer(Modifier.width(10.dp))
                        Text("Warte auf den PC …", style = TbType.small, color = Tb.text3, modifier = Modifier.weight(1f))
                        TbButton("Abbrechen", { job?.cancel(); waiting = null }, kind = BtnKind.Ghost, small = true)
                    }
                }
                Spacer(Modifier.height(24.dp))
                return@Column
            }
            Text("Bitte prüfen, bevor du koppelst. Erst wenn du hier und danach am PC zustimmst, wird gekoppelt.",
                style = TbType.body, color = Tb.text2)
            if (already != null) {
                Spacer(Modifier.height(12.dp))
                Notice("Mit diesem PC ist das Handy schon gekoppelt. Neu koppeln ersetzt die bisherige Kopplung.", icon = Ico.Info, color = Tb.accent)
            }
            error?.let { Spacer(Modifier.height(12.dp)); Notice(it, color = Tb.danger) }
            if (reach.isEmpty()) {
                Spacer(Modifier.height(12.dp))
                Notice("Keine der Adressen liegt im Netz, in dem das Handy gerade ist. Ist das Handy im selben WLAN wie der PC?")
            }
            SectionLabel("Adressen des PCs")
            TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                AddrPicker(invite.addrs, mode, use) { m, u -> mode = m; use = u }
            }
            SectionLabel("Was passiert")
            SyncFacts(invite.pcName, if (mode == "all") invite.addrs else use)
            Spacer(Modifier.height(20.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TbButton("Koppeln anfragen", { request() }, kind = BtnKind.Primary, icon = Ico.Check)
                TbButton("Abbrechen", back, kind = BtnKind.Ghost)
            }
            Spacer(Modifier.height(32.dp))
        }
    }
}

@Composable
private fun Pulse() {
    val t = rememberInfiniteTransition(label = "warten")
    val a by t.animateFloat(0.3f, 1f, infiniteRepeatable(tween(700), RepeatMode.Reverse), label = "puls")
    Box(Modifier.size(10.dp).alpha(a).clip(CircleShape).background(Tb.accent))
}

/** Ein gekoppelter PC: Status, Adressen, was passiert, entkoppeln. */
@Composable
fun PcScreen(pcId: String, back: () -> Unit, toast: (String) -> Unit) {
    val s by App.repo.settings.collectAsState()
    val link = s.pcs.firstOrNull { it.pcId == pcId }
    val scope = rememberCoroutineScope()
    var syncing by remember { mutableStateOf(false) }
    var askUnpair by remember { mutableStateOf(false) }
    if (link == null) {
        Column(Modifier.fillMaxSize()) { TopBack(back); Text("Nicht mehr gekoppelt.", style = TbType.body, color = Tb.text3, modifier = Modifier.padding(20.dp)) }
        return
    }
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        TopBack(back)
        ScreenHeader(link.pcName, "Gekoppelt ${if (link.added > 0) Fmt.ago(link.added) else ""}".trim())
        Column(Modifier.padding(horizontal = 20.dp)) {
            if (!s.netConsent) { NetConsent(); Spacer(Modifier.height(14.dp)) }
            TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                Text(pcStatus(link), style = TbType.body, color = if (link.lastSyncError != null) Tb.warn else Tb.text2)
                Spacer(Modifier.height(12.dp))
                TbButton(if (syncing) "Gleiche ab …" else "Jetzt abgleichen", {
                    if (syncing) return@TbButton
                    syncing = true
                    scope.launch {
                        runCatching { App.sync.sync(link.pcId) }.onSuccess { toast(syncText(it)) }.onFailure { toast(it.message ?: "Abgleich fehlgeschlagen") }
                        syncing = false
                    }
                }, kind = BtnKind.Primary, icon = Ico.Sync, enabled = !syncing)
            }
            SectionLabel("Playlists auf dem Handy")
            TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                ListsOnPhone(link) {
                    if (!syncing && App.sync.reachable(link).isNotEmpty()) {
                        syncing = true
                        scope.launch {
                            runCatching { App.sync.sync(link.pcId) }.onSuccess { toast(syncText(it)) }.onFailure { toast(it.message ?: "Abgleich fehlgeschlagen") }
                            syncing = false
                        }
                    }
                }
            }
            SectionLabel("Adressen, die das Handy benutzt")
            TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                AddrPicker(link.addrs, link.addrMode, link.useAddrs) { m, u -> App.sync.setAddrs(link.pcId, m, u) }
            }
            SectionLabel("Was passiert")
            SyncFacts(link.pcName, link.targets)
            Spacer(Modifier.height(20.dp))
            TbButton("Entkoppeln", { askUnpair = true }, kind = BtnKind.Danger, icon = Ico.Trash)
            Spacer(Modifier.height(32.dp))
        }
    }
    if (askUnpair) AlertDialog(
        onDismissRequest = { askUnpair = false }, containerColor = Tb.bg2,
        title = { Text("${link.pcName} entkoppeln?", style = TbType.title, color = Tb.text) },
        text = {
            Text("Das Handy gleicht dann nicht mehr mit diesem PC ab. Dein Verlauf bleibt auf dem Handy, die Playlists dieses PCs werden vom Handy entfernt. " +
                "Am PC kannst du das Handy unter Einstellungen › Handy ebenfalls entfernen.", style = TbType.body, color = Tb.text2)
        },
        confirmButton = { TbButton("Entkoppeln", { askUnpair = false; App.sync.unpair(link.pcId); toast("${link.pcName} entkoppelt"); back() }, kind = BtnKind.Danger) },
        dismissButton = { TbButton("Abbrechen", { askUnpair = false }, kind = BtnKind.Ghost) },
    )
}

fun pcStatus(link: Repository.PcLink): String {
    val reach = App.sync.reachable(link)
    return when {
        !Nets.allowed() -> "Netzwerk-Erkennung ist aus – erst erlauben, dann gleicht das Handy mit diesem PC ab."
        reach.isEmpty() -> "Nicht im Netz dieses PCs – Abgleich pausiert, bis das Handy wieder dort ist."
        link.lastSyncError != null -> link.lastSyncError
        link.lastSync > 0 -> "Zuletzt abgeglichen ${Fmt.ago(link.lastSync)} über ${link.lastAddr ?: reach.first()}"
        else -> "Gekoppelt – noch nicht abgeglichen"
    }
}

fun syncText(r: PcSync.Result): String =
    if (r.sent == 0 && r.received == 0) "${r.pcName}: alles aktuell · ${r.playlists} Playlists"
    else "${r.pcName}: ${r.sent} an den PC geschickt, ${r.received} neu vom PC"
