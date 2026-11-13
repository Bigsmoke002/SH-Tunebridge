package de.bs002.tunebridge.ui.screens

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
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.BuildConfig
import de.bs002.tunebridge.ui.Fmt
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.Hairline
import de.bs002.tunebridge.ui.components.Notice
import de.bs002.tunebridge.ui.components.SectionLabel
import de.bs002.tunebridge.ui.components.SettingRow
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.components.TbCard
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType
import kotlinx.coroutines.launch

@Composable
fun SettingsScreen(openPair: () -> Unit, openPc: (String) -> Unit, openPrivacy: () -> Unit, toast: (String) -> Unit) {
    val s by App.repo.settings.collectAsState()
    val scope = rememberCoroutineScope()
    var syncing by remember { mutableStateOf(false) }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        ScreenHeader("Mehr")
        Column(Modifier.padding(horizontal = 20.dp)) {
            SectionLabel(if (s.pcs.size > 1) "PCs" else "PC", Modifier.padding(top = 0.dp))
            TbCard(Modifier.fillMaxWidth(), padding = if (s.pcs.isEmpty()) 16.dp else 6.dp) {
                if (s.pcs.isEmpty()) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(Modifier.size(40.dp).clip(CircleShape).background(Tb.bg3), contentAlignment = Alignment.Center) { TbIcon(Ico.Monitor, Tb.text3, 20.dp) }
                        Spacer(Modifier.width(14.dp))
                        Column(Modifier.weight(1f)) {
                            Text("Kein PC gekoppelt", style = TbType.bodyStrong, color = Tb.text)
                            Text("Verlauf und Playlists mit SH-Tunebridge am PC abgleichen – direkt im eigenen Netz, verschlüsselt. Auch mit mehreren PCs.",
                                style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 2.dp))
                        }
                    }
                    Spacer(Modifier.height(14.dp))
                    TbButton("Mit PC koppeln", openPair, kind = BtnKind.Primary, icon = Ico.Qr)
                } else {
                    if (!s.netConsent) Notice("Netzwerk-Erkennung ist aus – das Handy gleicht nicht ab. Auf einen PC tippen, um sie zu erlauben.", modifier = Modifier.padding(8.dp))
                    s.pcs.forEachIndexed { i, pc ->
                        if (i > 0) Hairline(Modifier.padding(horizontal = 10.dp))
                        val reach = App.sync.reachable(pc).isNotEmpty()
                        Row(
                            Modifier.fillMaxWidth().clip(RoundedCornerShape(Tb.radiusSm)).clickable { openPc(pc.pcId) }.padding(10.dp),
                            verticalAlignment = Alignment.CenterVertically,
                        ) {
                            Box(Modifier.size(40.dp).clip(CircleShape).background(if (reach) Tb.accentSoft else Tb.bg3), contentAlignment = Alignment.Center) {
                                TbIcon(Ico.Monitor, if (reach) Tb.accent else Tb.text3, 20.dp)
                            }
                            Spacer(Modifier.width(14.dp))
                            Column(Modifier.weight(1f)) {
                                Text(pc.pcName, style = TbType.bodyStrong, color = Tb.text)
                                Text(pcStatus(pc), style = TbType.small, color = if (reach && pc.lastSyncError != null) Tb.warn else Tb.text3,
                                    maxLines = 2, modifier = Modifier.padding(top = 2.dp))
                            }
                            TbIcon(Ico.Chevron, Tb.text3, 16.dp)
                        }
                    }
                    Spacer(Modifier.height(6.dp))
                    Row(Modifier.padding(horizontal = 10.dp, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TbButton(if (syncing) "Gleiche ab …" else "Jetzt abgleichen", {
                            if (syncing) return@TbButton
                            syncing = true
                            scope.launch {
                                val res = runCatching { App.sync.syncAll(manual = true) }.getOrDefault(emptyList())
                                val done = res.filter { !it.skipped }
                                toast(when {
                                    res.isEmpty() -> "Kein PC gekoppelt"
                                    done.isEmpty() -> "Kein gekoppelter PC im aktuellen Netz (unterwegs: beim PC „Unterwegs abgleichen“ einschalten)"
                                    done.size == 1 -> syncText(done.first())
                                    else -> "Mit ${done.size} PCs abgeglichen"
                                })
                                syncing = false
                            }
                        }, kind = BtnKind.Primary, icon = Ico.Sync, enabled = !syncing)
                        TbButton("Weiteren PC koppeln", openPair, kind = BtnKind.Ghost, icon = Ico.Plus)
                    }
                    SettingRow("Automatisch abgleichen", "Nach jeder Erkennung und beim Öffnen – nur mit PCs, in deren Netz das Handy gerade ist", s.autoSync) { v ->
                        App.repo.updateSettings { it.copy(autoSync = v) }
                    }
                }
            }

            SectionLabel("Shazam-App")
            ShazamRootCard(toast)

            SectionLabel("Erkennen")
            TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                Text("Aufnahmedauer", style = TbType.bodyStrong, color = Tb.text)
                Text("Shazam wertet 10 Sekunden aus. Längere Aufnahmen nehmen die Mitte – hilfreich, wenn am Anfang geredet wird.",
                    style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 2.dp, bottom = 12.dp))
                Segmented(listOf(10, 15, 20), s.seconds, { "$it s" }) { v -> App.repo.updateSettings { it.copy(seconds = v) } }
                Spacer(Modifier.height(10.dp))
                Hairline()
                SettingRow("Offline merken", "Ohne Internet nur den Fingerabdruck (Zahlenwerte, kein Ton) speichern und später bei Shazam " +
                    "nachfragen – höchstens 50, höchstens 30 Tage. Aus: ohne Internet kein Erkennen.", s.offlineQueue) { v ->
                    App.repo.updateSettings { it.copy(offlineQueue = v) }
                }
                Hairline()
                SettingRow("Angeschlossenes Mikrofon nehmen", "USB-Soundkarte oder Headset als Mikrofon. Aus: immer das Mikrofon des Handys – " +
                    "sonst nähme Android den (oft stummen) Eingang der Soundkarte.", s.externalMic) { v ->
                    App.repo.updateSettings { it.copy(externalMic = v) }
                }
            }

            SectionLabel("Sicherung")
            BackupCard()

            SectionLabel("Datenschutz")
            TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                SettingRow("Cover-Bilder anzeigen", "Lädt Albumcover von Apples Bildserver (sieht deine IP-Adresse). Aus: neutrale Platzhalter.", s.covers) { v ->
                    App.repo.updateSettings { it.copy(covers = v) }
                }
                Hairline()
                SettingRow("Netzwerke erkennen", "Liest IP-Adresse und Netz des Handys (WLAN/VPN), damit nur PCs im selben Netz angesprochen werden. Nur auf dem Handy, keine Berechtigung nötig. Aus: kein Abgleich mit PCs.", s.netConsent) { v ->
                    App.repo.updateSettings { it.copy(netConsent = v) }
                }
                Hairline()
                SettingRow("Ähnliche Songs, Versionen & Entdecken ohne PC", "Ist kein PC erreichbar, holt die App ähnliche Songs, Remixe & Versionen bzw. „Entdecken“ direkt bei Deezer – mit Titel und Künstler des Songs bzw. deinem Suchbegriff; Deezer sieht deine IP-Adresse. Aus: nur vom PC.", s.similarDirect) { v ->
                    App.repo.updateSettings { it.copy(similarDirect = v) }
                }
                Hairline()
                var fbAsk by remember { mutableStateOf(false) }
                NavRow("Ersatz-Hörprobe (YouTube/Spotify): ${listOfNotNull("YouTube".takeIf { s.fallbackYoutube }, "Spotify".takeIf { s.fallbackSpotify }).joinToString(", ").ifEmpty { "aus" }}") { fbAsk = true }
                if (fbAsk) FallbackConsentDialog { fbAsk = false }
                Hairline()
                NavRow("Was die App sendet und speichert", openPrivacy)
            }

            SectionLabel("Über")
            TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
                UpdateSection()
                Hairline()
                Text("Logo und Name © Bigsmoke002. Schrift Inter (SIL OFL 1.1), QR-Erkennung ZXing (Apache 2.0), " +
                    "Fingerabdruck-Format wie shazamio-core (MIT), Signaturprüfung Bouncy Castle (MIT).", style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 10.dp))
            }
            Spacer(Modifier.height(32.dp))
        }
    }
}

@Composable
fun <T> Segmented(options: List<T>, selected: T, label: (T) -> String, onSelect: (T) -> Unit) {
    val shape = RoundedCornerShape(Tb.radiusSm)
    Row(Modifier.fillMaxWidth().clip(shape).background(Tb.bg3).border(1.dp, Tb.line, shape).padding(3.dp)) {
        options.forEach { o ->
            val on = o == selected
            Box(
                Modifier.weight(1f).clip(RoundedCornerShape(5.dp)).background(if (on) Tb.bg4 else Tb.bg3).clickable { onSelect(o) }.padding(vertical = 8.dp),
                contentAlignment = Alignment.Center,
            ) { Text(label(o), style = TbType.button, color = if (on) Tb.text else Tb.text3) }
        }
    }
}

@Composable
private fun NavRow(title: String, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clickable(onClick = onClick).padding(vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(title, style = TbType.bodyStrong, color = Tb.text, modifier = Modifier.weight(1f))
        TbIcon(Ico.Chevron, Tb.text3, 16.dp)
    }
}

/** Datenschutz-Übersicht – deckt sich mit DATENSCHUTZ.md › Android-App. */
@Composable
fun PrivacyScreen(back: () -> Unit) {
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        TopBack(back)
        ScreenHeader("Datenschutz")
        Column(Modifier.padding(horizontal = 20.dp)) {
            listOf(
                Triple(Ico.Mic, "Mikrofon", "Nur nach Tippen auf den Kreis, standardmäßig 10 Sekunden. Der Ton bleibt im Arbeitsspeicher und wird sofort verworfen – nie gespeichert, nie gesendet. Ohne Internet merkt sich die App (abschaltbar) nur den Fingerabdruck, bis Shazam erreichbar ist. Dauer-Erkennen hört nur nach deinem Start in Abständen zu, mit sichtbarer Benachrichtigung, höchstens 4 Stunden."),
                Triple(Ico.Wave, "Shazam (Apple)", "Bekommt einen Fingerabdruck der Aufnahme (Zahlenwerte, kein Ton), Zeitzone und Spracheinstellung – und technisch bedingt deine IP-Adresse. Ohne Konto, ohne Werbe-ID."),
                Triple(Ico.Disc, "Cover & Hörproben", "Cover nur, wenn eingeschaltet; Hörproben erst nach Tippen auf „Reinhören“ oder „Abspielen“. Beides kommt von Apple bzw. Deezer, die dabei deine IP-Adresse sehen. Gesteuert wird der Player auch über Benachrichtigung, Sperrbildschirm und Kopfhörer-Tasten – das bleibt auf dem Handy. Ist eine Deezer-Adresse abgelaufen, fragt die App bei Deezer mit Song-Nummer, ISRC oder Künstler + Titel nach der aktuellen."),
                Triple(Ico.Shield, "Shazam-App (nur Root)", "Nur wenn du es unter Mehr › Shazam-App startest und die Warnung bestätigst: Die App liest aus der Datenbank der Shazam-App nur Song-Nummer, Titel, Künstler und Zeitpunkt deiner Shazams – keinen Standort, keine Signatur, keine Kontodaten – und löscht die Kopie sofort."),
                Triple(Ico.Sparkle, "Ähnliche Songs", "Vom gekoppelten PC (verschlüsselt, wie der Abgleich). Ist keiner erreichbar und hast du es erlaubt, direkt bei Deezer: Titel, Künstler bzw. Deezer-Nummer/ISRC des Songs – Deezer sieht deine IP-Adresse."),
                Triple(Ico.Play, "Ersatz-Hörprobe (Standard: aus)", "Nur wenn du es je Anbieter erlaubst und Deezer/Apple keine Hörprobe haben: offizieller YouTube- bzw. Spotify-Player, sichtbar eingebettet. Beim Laden sehen Google bzw. Spotify IP-Adresse und Geräteinfos und können Cookies setzen. Die Video-Kennung kommt aus bekannten Links oder verschlüsselt vom PC (der sucht bei YouTube mit Titel und Künstler)."),
                Triple(Ico.Disc, "Remixe & Versionen", "Genauso: vom PC (verschlüsselt; Titel, Künstler, Länge) oder – mit derselben Erlaubnis – direkt bei Deezer mit Titel und Künstler."),
                Triple(Ico.Compass, "Entdecken", "Suche, Künstler-, Albumseiten und Charts: vom PC (verschlüsselt; nur Suchbegriff bzw. Kennung – der PC fragt die dort eingeschalteten Quellen Deezer, Apple, MusicBrainz, Last.fm, Discogs) oder – mit derselben Erlaubnis – nur Deezer direkt. Ergebnisse nur im Arbeitsspeicher (1 Stunde), Suchbegriffe werden nicht gespeichert."),
                Triple(Ico.Sync, "Updates (GitHub)", "Nur wenn „Automatisch nach Updates suchen“ an ist (höchstens einmal am Tag) oder du selbst suchst: GitHub sieht deine IP-Adresse. Installiert wird nur eine signierte, geprüfte Version – und erst, wenn du im Android-Installer bestätigst."),
                Triple(Ico.Monitor, "Dein PC", "Abgleich direkt im eigenen Netz, ohne Server dazwischen – nur mit PCs, denen du hier und am PC zugestimmt hast, und nur über die Adressen, die du je PC auswählst. Gesendet wird nur, wenn das Handy gerade im Netz dieses PCs ist. Dafür liest die App – erst nach deiner Zustimmung – die eigenen Netzwerkkarten (IP-Adresse, Netz), ohne Standort-Berechtigung; widerrufbar unter Mehr › Datenschutz. Jede Nachricht ist mit AES-256-GCM verschlüsselt; der Schlüssel entsteht beim Koppeln und verlässt Handy und PC nie. Mix erstellen und Set-Planer rechnen ebenfalls dort: Das Handy schickt nur Suchbegriff, Künstler/Genre oder Playlist-Namen."),
                Triple(Ico.Sync, "Unterwegs abgleichen", "Nur wenn du es je PC einschaltest (und am PC ebenfalls): Ist das Handy nicht im Netz des PCs, legt es den Abgleich auf shtunebridge.bs002.de ab und holt dort die Antwort des PCs. Inhalt wie im Heimnetz, Ende-zu-Ende verschlüsselt mit dem Schlüssel aus der Kopplung. Der Server sieht nur zufällige Kennungen, unlesbare Blöcke, das Datum; IP-Adresse und Zeitpunkt protokolliert die Server-Technik wie bei jeder Verbindung (höchstens 12 Monate). Ausschalten oder Entkoppeln löscht die Ablagen sofort, sonst nach einem Jahr ohne Nutzung."),
                Triple(Ico.Download, "Sicherung", "Nur auf Tippen: eine Datei mit deinem Verlauf und den Handy-Playlists an den Ort, den du wählst – ohne gekoppelte PCs, Schlüssel oder Einstellungen, nicht verschlüsselt. Playlists „Auf dem Handy“ bleiben sonst nur in der App."),
                Triple(Ico.Share, "Teilen & Export", "Nur nach Tippen auf Teilen: Datei mit Titel, Künstler, Album, ISRC, Genre, Zeitpunkt und Link an die App, die du wählst – keine Cover, keine Musik."),
                Triple(Ico.Shield, "Auf dem Handy", "Verlauf, Playlists und Einstellungen liegen nur in der App (nicht in Android-Sicherungen). App löschen = alles weg."),
                Triple(Ico.X, "Was es nicht gibt", "Kein Konto, keine Werbung, keine Analyse- oder Absturz-Dienste, keine Google-Play-Dienste."),
            ).forEach { (icon, title, text) ->
                Row(Modifier.padding(vertical = 12.dp)) {
                    TbIcon(icon, Tb.accent, 20.dp, Modifier.padding(top = 1.dp))
                    Spacer(Modifier.width(14.dp))
                    Column {
                        Text(title, style = TbType.bodyStrong, color = Tb.text)
                        Text(text, style = TbType.body, color = Tb.text2, modifier = Modifier.padding(top = 3.dp))
                    }
                }
            }
            Spacer(Modifier.height(32.dp))
        }
    }
}

/** Verlauf und Handy-Playlists als Datei sichern bzw. zurückholen (z. B. beim Handywechsel). */
@Composable
private fun BackupCard() {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val scope = rememberCoroutineScope()
    var busy by remember { mutableStateOf(false) }
    var restoreFrom by remember { mutableStateOf<android.net.Uri?>(null) }
    val save = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.CreateDocument("application/json")) { uri ->
        if (uri == null) return@rememberLauncherForActivityResult
        busy = true
        scope.launch {
            runCatching {
                kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                    val b = App.repo.backup(de.bs002.tunebridge.BuildConfig.VERSION_NAME)
                    ctx.contentResolver.openOutputStream(uri, "wt")!!.use { it.write(App.repo.json.encodeToString(de.bs002.tunebridge.data.Repository.Backup.serializer(), b).toByteArray()) }
                    b
                }
            }.onSuccess { b -> App.snack("Gesichert: ${Fmt.songs(b.recognitions.size)}, ${b.playlists.size} Handy-Playlists") }
                .onFailure { App.snack("Sichern fehlgeschlagen: ${it.message ?: "unbekannter Fehler"}") }
            busy = false
        }
    }
    val open = androidx.activity.compose.rememberLauncherForActivityResult(
        androidx.activity.result.contract.ActivityResultContracts.OpenDocument()) { uri -> restoreFrom = uri }
    TbCard(Modifier.fillMaxWidth(), padding = 14.dp) {
        Text("Verlauf und Playlists sichern", style = TbType.bodyStrong, color = Tb.text)
        Text("Speichert deinen ganzen Verlauf (mit Favoriten) und die Playlists auf dem Handy als Datei, wohin du willst – z. B. für ein neues Handy. " +
            "Gekoppelte PCs, Schlüssel und Einstellungen kommen nicht hinein. Die Datei ist nicht verschlüsselt – gut aufbewahren.",
            style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 2.dp, bottom = 12.dp))
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            TbButton(if (busy) "Bitte warten …" else "Sichern", {
                if (!busy) save.launch("sh-tunebridge-sicherung-${java.time.LocalDate.now()}.json")
            }, kind = BtnKind.Primary, icon = Ico.Download, enabled = !busy)
            TbButton("Wiederherstellen", { if (!busy) open.launch(arrayOf("application/json", "application/octet-stream", "text/plain")) },
                kind = BtnKind.Ghost, icon = Ico.Upload, enabled = !busy)
        }
    }
    restoreFrom?.let { uri ->
        androidx.compose.material3.AlertDialog(
            onDismissRequest = { restoreFrom = null }, containerColor = Tb.bg2,
            title = { Text("Sicherung zurückholen?", style = TbType.title, color = Tb.text) },
            text = {
                Text("Songs und Playlists aus der Datei kommen dazu; was schon da ist, bleibt unverändert. Gekoppelte PCs bekommen die neuen Songs beim nächsten Abgleich.",
                    style = TbType.body, color = Tb.text2)
            },
            confirmButton = {
                TbButton("Zurückholen", {
                    restoreFrom = null
                    busy = true
                    scope.launch {
                        runCatching {
                            kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                                val text = ctx.contentResolver.openInputStream(uri)!!.use { inp ->
                                    val bytes = inp.readBytes()
                                    require(bytes.size < 64 shl 20) { "Die Datei ist zu groß für eine Sicherung" }
                                    String(bytes)
                                }
                                val b = runCatching { App.repo.json.decodeFromString(de.bs002.tunebridge.data.Repository.Backup.serializer(), text) }
                                    .getOrElse { throw IllegalArgumentException("Die Datei ist keine gültige Sicherung") }
                                App.repo.restoreBackup(b)
                            }
                        }.onSuccess { (n, songs) ->
                            App.snack(if (n == 0 && songs == 0) "Nichts Neues – alles war schon da" else "Zurückgeholt: ${Fmt.songs(n)} im Verlauf, $songs in Playlists")
                            if (n > 0) App.listener.autoSync()
                        }.onFailure { App.snack(it.message ?: "Zurückholen fehlgeschlagen") }
                        busy = false
                    }
                }, kind = BtnKind.Primary)
            },
            dismissButton = { TbButton("Abbrechen", { restoreFrom = null }, kind = BtnKind.Ghost) },
        )
    }
}
