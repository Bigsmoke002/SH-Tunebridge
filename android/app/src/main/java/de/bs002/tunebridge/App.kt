package de.bs002.tunebridge

import android.app.Application
import coil.ImageLoader
import coil.ImageLoaderFactory
import coil.disk.DiskCache
import de.bs002.tunebridge.data.Db
import de.bs002.tunebridge.data.Repository
import de.bs002.tunebridge.net.Http
import de.bs002.tunebridge.sync.PcSync

class App : Application(), ImageLoaderFactory {
    override fun onCreate() {
        super.onCreate()
        repo = Repository(Db(this), this)
        sync = PcSync(repo)
        listener = Listener(this, repo, sync)
        Player.init(this)
        shortcuts()
    }

    /** Lange auf das App-Symbol drücken: „Erkennen“ und „Handy-Ton erkennen“. */
    private fun shortcuts() = runCatching {
        val sm = getSystemService(android.content.pm.ShortcutManager::class.java) ?: return@runCatching
        val icon = android.graphics.drawable.Icon.createWithResource(this, R.drawable.ic_stat_wave)
        sm.dynamicShortcuts = listOf(
            android.content.pm.ShortcutInfo.Builder(this, "listen").setShortLabel("Erkennen").setLongLabel("Song erkennen (Mikrofon)")
                .setIcon(icon).setIntent(MainActivity.listenIntent(this, false)).build(),
            android.content.pm.ShortcutInfo.Builder(this, "listen-system").setShortLabel("Handy-Ton").setLongLabel("Handy-Ton erkennen")
                .setIcon(icon).setIntent(MainActivity.listenIntent(this, true)).build(),
        )
    }

    /** Cover nur im Speicher und in einem kleinen App-Cache – kein eigener HTTP-Client, keine Cookies. */
    override fun newImageLoader(): ImageLoader = ImageLoader.Builder(this)
        .okHttpClient(Http.client)
        .diskCache { DiskCache.Builder().directory(cacheDir.resolve("cover")).maxSizeBytes(40L shl 20).build() }
        .respectCacheHeaders(false)
        .build()

    companion object {
        lateinit var repo: Repository
            private set
        lateinit var sync: PcSync
            private set
        lateinit var listener: Listener
            private set

        /** Song, zu dem die Seite „Ähnliche Songs“ gerade Vorschläge zeigt. */
        val similarSeed = kotlinx.coroutines.flow.MutableStateFlow<de.bs002.tunebridge.data.Track?>(null)
        val versionsSeed = kotlinx.coroutines.flow.MutableStateFlow<de.bs002.tunebridge.data.Track?>(null)

        /** Erkennen von außen angestoßen (Schnellkachel, Widget, App-Kurzbefehl): false = Mikrofon, true = Handy-Ton. */
        val listenRequest = kotlinx.coroutines.flow.MutableStateFlow<Boolean?>(null)

        /** Kurze Meldung unten, optional mit Aktion (z. B. „Rückgängig“). */
        class Snack(val message: String, val action: String? = null, val run: (() -> Unit)? = null)
        val snacks = kotlinx.coroutines.flow.MutableSharedFlow<Snack>(extraBufferCapacity = 4)
        fun snack(message: String, action: String? = null, run: (() -> Unit)? = null) { snacks.tryEmit(Snack(message, action, run)) }

        /** Fassung der Datenschutz-Hinweise; bei Änderung erneut zustimmen lassen. */
        const val CONSENT_VERSION = 2          // 2: Update-Prüfung erklärt
    }
}
