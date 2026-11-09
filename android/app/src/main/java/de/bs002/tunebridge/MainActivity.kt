package de.bs002.tunebridge

import android.content.Intent
import android.graphics.Color
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.SystemBarStyle
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.core.splashscreen.SplashScreen.Companion.installSplashScreen
import androidx.lifecycle.lifecycleScope
import de.bs002.tunebridge.net.Shazam
import de.bs002.tunebridge.ui.AppRoot
import de.bs002.tunebridge.ui.theme.TbTheme
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.receiveAsFlow
import kotlinx.coroutines.launch
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import kotlinx.serialization.json.putJsonArray
import kotlinx.serialization.json.putJsonObject

class MainActivity : ComponentActivity() {
    private val messages = Channel<String>(Channel.BUFFERED)

    override fun onCreate(savedInstanceState: Bundle?) {
        installSplashScreen()
        enableEdgeToEdge(SystemBarStyle.dark(Color.TRANSPARENT), SystemBarStyle.dark(Color.TRANSPARENT))
        super.onCreate(savedInstanceState)
        setContent { TbTheme { AppRoot(messages.receiveAsFlow()) } }
        handle(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handle(intent)
    }

    override fun onStart() {
        super.onStart()
        App.listener.autoSync()   // beim Öffnen still abgleichen, falls der PC erreichbar ist
        lifecycleScope.launch { de.bs002.tunebridge.update.Updater.checkDaily() }   // nur wenn eingeschaltet, 1× am Tag
    }

    /** „Teilen“ aus der Shazam-App (oder einem Browser) mit einem Shazam-Link -> Song in den Verlauf.
     *  Schnellkachel / Widget / Kurzbefehl -> gleich erkennen (Hinweise und Berechtigungen wie beim Tippen). */
    private fun handle(intent: Intent?) {
        if (intent?.action == ACTION_LISTEN) {
            App.listenRequest.value = intent.getBooleanExtra(EXTRA_SYSTEM, false)
            intent.action = null                       // nicht nochmal beim Drehen o. Ä.
            return
        }
        if (intent?.action != Intent.ACTION_SEND) return
        val text = intent.getStringExtra(Intent.EXTRA_TEXT).orEmpty()
        intent.action = null
        val key = Regex("""shazam\.com/(?:[a-z-]+/)?(?:song|track)/(\d+)""").find(text)?.groupValues?.get(1)
        if (key == null) {
            messages.trySend("Kein Shazam-Link gefunden – teile einen Song direkt aus der Shazam-App")
            return
        }
        lifecycleScope.launch {
            runCatching { Shazam.track(key) }
                .onSuccess { hit ->
                    if (hit == null) { messages.send("Shazam kennt diesen Song nicht (mehr)"); return@onSuccess }
                    val extra = buildJsonObject {
                        putJsonArray("engines") { add(JsonPrimitive("shazam")) }
                        putJsonObject("links") { hit.links.forEach { (k, v) -> put(k, v) } }
                        hit.label?.let { put("label", it) }
                        hit.year?.let { put("year", it) }
                        put("shazam_key", key)
                        if (hit.genres.isNotEmpty()) put("shazam_genre", hit.genres.first())
                        put("device", "handy")
                        put("shared", true)
                    }
                    App.repo.add(hit.track, "geteilt", extra)
                    messages.send("„${hit.track.title}“ aus Shazam übernommen")
                    App.listener.autoSync()
                }
                .onFailure { messages.send("Konnte den Song nicht laden – Internet prüfen") }
        }
    }

    companion object {
        const val ACTION_LISTEN = "de.bs002.tunebridge.LISTEN"
        const val EXTRA_SYSTEM = "system"

        fun listenIntent(ctx: android.content.Context, system: Boolean): Intent =
            Intent(ctx, MainActivity::class.java).setAction(ACTION_LISTEN).putExtra(EXTRA_SYSTEM, system)
                .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP)
    }
}
