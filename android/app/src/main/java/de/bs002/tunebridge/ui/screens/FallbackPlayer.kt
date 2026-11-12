package de.bs002.tunebridge.ui.screens

import android.annotation.SuppressLint
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.lifecycle.compose.LocalLifecycleOwner
import de.bs002.tunebridge.App
import de.bs002.tunebridge.Player
import de.bs002.tunebridge.data.Track
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.Notice
import de.bs002.tunebridge.ui.components.SectionLabel
import de.bs002.tunebridge.ui.components.SettingRow
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbType

/**
 * Ersatz-Hörprobe: offizieller YouTube- bzw. Spotify-Player, eingebettet und sichtbar – nur wenn Deezer/Apple keine
 * Hörprobe haben und nur nach Einwilligung je Anbieter. YouTube-Richtlinien: kein Ton ohne Bild, nichts im
 * Hintergrund – der Player läuft in einem eigenen Vollbild-Fenster, pausiert, sobald die App in den Hintergrund geht,
 * und wird beim Schließen beendet.
 */
private val YT = Regex("""(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/)|music\.youtube\.com/watch\?v=)([\w-]{11})""")
private val SP = Regex("""open\.spotify\.com/(?:intl-[a-z]+/)?track/([A-Za-z0-9]{22})""")

private fun knownIds(t: Track, links: Map<String, String>): Map<String, String> {
    val out = HashMap<String, String>()
    t.ids["youtube"]?.takeIf { it.matches(Regex("""[\w-]{11}""")) }?.let { out["youtube"] = it }
    t.ids["spotify"]?.takeIf { it.matches(Regex("""[A-Za-z0-9]{22}""")) }?.let { out["spotify"] = it }
    links.values.forEach { u ->
        YT.find(u)?.let { out.putIfAbsent("youtube", it.groupValues[1]) }
        SP.find(u)?.let { out.putIfAbsent("spotify", it.groupValues[1]) }
    }
    return out
}

private sealed interface FLoad {
    data object Busy : FLoad
    data class Found(val kind: String, val id: String, val via: String) : FLoad
    data class None(val why: String) : FLoad
}

@Composable
fun FallbackPlayer(t: Track, links: Map<String, String>, autoplay: Boolean) {
    val s by App.repo.settings.collectAsState()
    var ask by remember { mutableStateOf(false) }
    SectionLabel("Ersatz-Hörprobe")
    if (!s.fallbackYoutube && !s.fallbackSpotify) {
        Notice("Keine Hörprobe bei Deezer oder Apple. Als Ersatz kann die App den offiziellen YouTube- oder Spotify-Player " +
            "einbetten – sichtbar, direkt beim Anbieter. Das musst du einmal erlauben.", icon = Ico.Info, color = Tb.accent) {
            Row(Modifier.padding(top = 10.dp)) { TbButton("Ersatz-Player einrichten …", { ask = true }, kind = BtnKind.Primary, small = true) }
        }
        if (ask) FallbackConsentDialog { ask = false }
        return
    }
    val kinds = listOfNotNull("youtube".takeIf { s.fallbackYoutube }, "spotify".takeIf { s.fallbackSpotify })
    var load by remember(t.key, kinds) { mutableStateOf<FLoad>(FLoad.Busy) }
    LaunchedEffect(t.key, kinds) {
        val known = knownIds(t, links).filterKeys { it in kinds }
        load = known["youtube"]?.let { FLoad.Found("youtube", it, "bekannter Link") }
            ?: known["spotify"]?.let { FLoad.Found("spotify", it, "bekannter Link") }
            ?: runCatching { App.sync.fallback(t, kinds, known) }.fold(
                { r ->
                    when {
                        r == null -> FLoad.None("Kein Link zu YouTube/Spotify bekannt – den passenden Player sucht der gekoppelte PC, sobald er erreichbar ist.")
                        r["youtube"] != null -> FLoad.Found("youtube", r["youtube"]!!, "vom PC")
                        r["spotify"] != null -> FLoad.Found("spotify", r["spotify"]!!, "vom PC")
                        else -> FLoad.None("Auch bei ${kinds.joinToString(" und ") { if (it == "youtube") "YouTube" else "Spotify" }} kein passender Player gefunden.")
                    }
                },
                { FLoad.None(it.message ?: "Suche fehlgeschlagen") })
    }
    when (val l = load) {
        FLoad.Busy -> Text("Suche den offiziellen Player …", style = TbType.small, color = Tb.text3)
        is FLoad.None -> Text(l.why, style = TbType.small, color = Tb.text3)
        is FLoad.Found -> {
            // Eigenes Fenster statt eingebettet: in der scrollbaren Seite kam nur der Ton, nicht das Videobild
            var open by remember(t.key, l.id) { mutableStateOf(autoplay) }
            val name = if (l.kind == "youtube") "YouTube" else "Spotify"
            Row(Modifier.padding(top = 2.dp)) {
                TbButton("Im $name-Player abspielen", { open = true }, kind = BtnKind.Primary, small = true, icon = Ico.Play)
            }
            Text("Offizieller $name-Player (${l.via}) – gespielt wird direkt beim Anbieter, nur solange der Player offen ist.",
                style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 6.dp))
            if (open) PlayerWindow(l.kind, l.id) { open = false }
        }
    }
}

private fun isEmbed(u: android.net.Uri): Boolean = when (u.host) {
    "www.youtube-nocookie.com", "www.youtube.com" -> u.path.orEmpty().startsWith("/embed/")
    "open.spotify.com" -> u.path.orEmpty().startsWith("/embed/")
    else -> false
}

/**
 * Offizieller Player in einem eigenen Vollbild-Fenster (schwarz, Player mittig, „Schließen“ bzw. Zurück).
 * Geöffnet nur durch Antippen – deshalb startet er gleich. Pausiert, sobald die App in den Hintergrund geht.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
private fun PlayerWindow(kind: String, id: String, close: () -> Unit) {
    val ctx = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val onClose by androidx.compose.runtime.rememberUpdatedState(close)
    DisposableEffect(kind, id) {
        Player.stop()                                       // nie zwei Töne gleichzeitig
        // YouTube verlangt beim Einbetten eine Herkunft (sonst Fehler 152/153) – die geht als Referer mit
        val origin = "https://shtunebridge.bs002.de"
        val src = if (kind == "youtube") "https://www.youtube-nocookie.com/embed/$id?rel=0&playsinline=1&autoplay=1&origin=$origin"
            else "https://open.spotify.com/embed/track/$id?utm_source=generator&theme=0"
        val dm = ctx.resources.displayMetrics
        val web = WebView(ctx).apply {
            settings.javaScriptEnabled = true               // der offizielle Player braucht JavaScript
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = false
            setBackgroundColor(android.graphics.Color.BLACK)
            webChromeClient = WebChromeClient()
            webViewClient = object : WebViewClient() {
                // Der Player selbst bleibt hier; andere Links (z. B. „Ansehen auf YouTube“) im Browser bzw. in der App öffnen
                override fun shouldOverrideUrlLoading(view: WebView, req: WebResourceRequest): Boolean {
                    if (!req.isForMainFrame || isEmbed(req.url)) return false
                    runCatching { ctx.startActivity(android.content.Intent(android.content.Intent.ACTION_VIEW, req.url)) }
                    return true
                }
            }
            loadUrl(src, mapOf("Referer" to "$origin/"))
        }
        val h = if (kind == "youtube") dm.widthPixels * 9 / 16 else (352 * dm.density).toInt()
        val root = android.widget.FrameLayout(ctx).apply {
            setBackgroundColor(android.graphics.Color.BLACK)
            addView(web, android.widget.FrameLayout.LayoutParams(-1, h, android.view.Gravity.CENTER))
            addView(android.widget.TextView(ctx).apply {
                text = "Schließen"
                setTextColor(android.graphics.Color.WHITE)
                textSize = 16f
                val p = (16 * dm.density).toInt()
                setPadding(p, p * 3, p, p)
                setOnClickListener { onClose() }
            }, android.widget.FrameLayout.LayoutParams(-2, -2, android.view.Gravity.TOP or android.view.Gravity.END))
        }
        val dlg = android.app.Dialog(ctx, android.R.style.Theme_Black_NoTitleBar_Fullscreen).apply {
            setContentView(root)
            setOnDismissListener { onClose() }
            show()
        }
        val obs = LifecycleEventObserver { _, e ->
            when (e) {
                Lifecycle.Event.ON_PAUSE -> web.onPause()   // App im Hintergrund: Player hält an
                Lifecycle.Event.ON_RESUME -> web.onResume()
                else -> Unit
            }
        }
        owner.lifecycle.addObserver(obs)
        onDispose {
            owner.lifecycle.removeObserver(obs)
            dlg.setOnDismissListener(null); dlg.dismiss()
            web.stopLoading(); web.loadUrl("about:blank"); web.destroy()
        }
    }
}

/** Einwilligung je Anbieter – derselbe Text wie am PC. */
@Composable
fun FallbackConsentDialog(close: () -> Unit) {
    val s by App.repo.settings.collectAsState()
    var yt by remember { mutableStateOf(s.fallbackYoutube) }
    var sp by remember { mutableStateOf(s.fallbackSpotify) }
    AlertDialog(
        onDismissRequest = close, containerColor = Tb.bg2,
        title = { Text("Ersatz-Hörprobe", style = TbType.title, color = Tb.text) },
        text = {
            Column(Modifier.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text("Gibt es bei Deezer und Apple keine Hörprobe, zeigt die Song-Seite den offiziellen Player des Anbieters – " +
                    "nur sichtbar und nur dort (kein Ton im Hintergrund, nichts wird heruntergeladen).", style = TbType.small, color = Tb.text2)
                SettingRow("YouTube (Google, USA)", "Beim Laden gehen IP-Adresse und Geräteinfos an Google, Daten können in die USA gehen; " +
                    "YouTube kann Cookies setzen. Das Video kommt aus bekannten Links oder vom gekoppelten PC (der sucht mit seinem YouTube-Zugang, " +
                    "dafür gehen Titel und Künstler an Google). Es gelten die YouTube-Nutzungsbedingungen (youtube.com/t/terms) und die " +
                    "Datenschutzerklärung von Google (policies.google.com/privacy).", yt) { yt = it }
                SettingRow("Spotify (Schweden)", "Der Player spielt ohne Anmeldung eine Vorschau; Spotify sieht IP-Adresse und Geräteinfos " +
                    "und kann Cookies setzen. Nur wenn ein Spotify-Link des Songs bekannt ist.", sp) { sp = it }
                Spacer(Modifier.height(2.dp))
                Text("Jederzeit änderbar unter Mehr › Datenschutz.", style = TbType.small, color = Tb.text3)
            }
        },
        confirmButton = { TbButton("Speichern", { App.repo.updateSettings { it.copy(fallbackYoutube = yt, fallbackSpotify = sp) }; close() }, kind = BtnKind.Primary) },
        dismissButton = { TbButton("Abbrechen", close, kind = BtnKind.Ghost) },
    )
}
