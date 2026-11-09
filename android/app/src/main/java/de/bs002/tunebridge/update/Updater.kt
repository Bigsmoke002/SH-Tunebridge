package de.bs002.tunebridge.update

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.provider.Settings
import androidx.core.content.FileProvider
import de.bs002.tunebridge.App
import de.bs002.tunebridge.BuildConfig
import de.bs002.tunebridge.net.Http
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.booleanOrNull
import okhttp3.Request
import java.io.File
import java.io.IOException
import java.security.MessageDigest
import java.util.concurrent.TimeUnit

/**
 * Updates ohne Play Store – genauso abgesichert wie am Desktop:
 * 1. GitHub-Releases abfragen (GitHub sieht dabei die IP-Adresse; einmal am Tag beim Öffnen, abschaltbar),
 * 2. Manifest `SH-Tunebridge-<v>-android.manifest` laden und seine SSH-Signatur mit dem Release-Schlüssel prüfen,
 * 3. APK laden, Größe und SHA-256 mit dem Manifest vergleichen,
 * 4. Android-Installer öffnen – installieren bestätigst du selbst; Android nimmt das Update zudem nur an,
 *    wenn es mit demselben App-Schlüssel signiert ist.
 */
object Updater {
    private const val NS = "sh-tunebridge-release"
    private const val DAY = 24 * 3600.0

    data class Update(val version: String, val notes: String, val file: String, val url: String, val size: Long, val sha256: String)

    sealed interface State {
        data object Idle : State
        data object Checking : State
        data object Current : State
        data class Available(val update: Update) : State
        data class Downloading(val progress: Float) : State
        data class Ready(val update: Update, val apk: File) : State
        data class Failed(val message: String) : State
    }

    private val _state = MutableStateFlow<State>(State.Idle)
    val state: StateFlow<State> = _state.asStateFlow()

    /** Nur Release-Builds aktualisieren sich selbst (die Entwicklerversion kommt per adb). */
    val supported: Boolean get() = !BuildConfig.DEBUG

    private val client by lazy { Http.client.newBuilder().readTimeout(60, TimeUnit.SECONDS).callTimeout(10, TimeUnit.MINUTES).followRedirects(true).build() }
    private val json = Json { ignoreUnknownKeys = true }

    /** Beim Öffnen: höchstens einmal am Tag, nur wenn eingeschaltet. */
    suspend fun checkDaily() {
        val s = App.repo.settings.value
        if (!supported || !s.autoUpdate || System.currentTimeMillis() / 1000.0 - s.lastUpdateCheck < DAY) return
        runCatching { check() }
    }

    suspend fun check(): Update? = withContext(Dispatchers.IO) {
        _state.value = State.Checking
        try {
            App.repo.updateSettings { it.copy(lastUpdateCheck = System.currentTimeMillis() / 1000.0) }
            val u = latest()
            _state.value = if (u == null) State.Current else State.Available(u)
            u
        } catch (e: Exception) {
            _state.value = State.Failed(e.message ?: "Update-Prüfung fehlgeschlagen")
            null
        }
    }

    private fun get(url: String, accept: String = "application/vnd.github+json"): ByteArray =
        client.newCall(Request.Builder().url(url).header("Accept", accept).header("User-Agent", "SH-Tunebridge-Android").build()).execute().use { r ->
            if (!r.isSuccessful) throw IOException("GitHub antwortet mit Fehler ${r.code}")
            r.body!!.bytes()
        }

    private fun latest(): Update? {
        val rels = json.parseToJsonElement(String(get("https://api.github.com/repos/${BuildConfig.UPDATE_REPO}/releases?per_page=15"))).jsonArray
        val mine = parse(BuildConfig.VERSION_NAME.substringBefore('-'))
        val best = rels.map { it.jsonObject }
            .filter { it["draft"]?.jsonPrimitive?.booleanOrNull != true && it["prerelease"]?.jsonPrimitive?.booleanOrNull != true }
            .mapNotNull { r -> parse(r["tag_name"]!!.jsonPrimitive.content.removePrefix("v"))?.let { it to r } }
            .filter { (v, _) -> mine == null || compare(v, mine) > 0 }
            .sortedWith { a, b -> compare(b.first, a.first) }
        for ((_, r) in best) {
            val tag = r["tag_name"]!!.jsonPrimitive.content
            val assets = r["assets"]?.jsonArray.orEmpty().associate {
                it.jsonObject["name"]!!.jsonPrimitive.content to it.jsonObject["browser_download_url"]!!.jsonPrimitive.content
            }
            val base = "SH-Tunebridge-${tag.removePrefix("v")}-android"
            val man = assets["$base.manifest"] ?: continue            // dieses Release hat (noch) keine Android-App
            val sig = assets["$base.manifest.sig"] ?: continue
            val manifest = get(man, "application/octet-stream")
            try {
                SshSig.verify(manifest, String(get(sig, "application/octet-stream")), BuildConfig.RELEASE_KEYS.split(','), NS)
            } catch (e: SshSig.SigError) {
                throw IOException("Signatur ungültig – Update wird NICHT installiert (${e.message})")
            }
            val text = String(manifest)
            val head = text.substringBefore("\n\n")
            val f = head.lines().drop(1).filter { '=' in it }.associate { it.substringBefore('=') to it.substringAfter('=') }
            if (!head.startsWith("SH-Tunebridge-Release 1") || !f.keys.containsAll(listOf("version", "file", "size", "sha256")))
                throw IOException("Manifest unvollständig – Update abgebrochen")
            if ("v${f["version"]}" != tag) throw IOException("Version im Manifest passt nicht zum Release")
            val file = f["file"]!!
            if ('/' in file || '\\' in file || !file.endsWith(".apk")) throw IOException("Ungültiger Dateiname im Manifest")
            val url = assets[file] ?: continue
            return Update(f["version"]!!, text.substringAfter("\n\n", "").trim(), file, url, f["size"]!!.toLong(), f["sha256"]!!.lowercase())
        }
        return null
    }

    /** APK laden und prüfen (Größe + SHA-256 aus dem signierten Manifest). */
    suspend fun download(ctx: Context, u: Update): File? = withContext(Dispatchers.IO) {
        val dir = File(ctx.cacheDir, "updates").apply { deleteRecursively(); mkdirs() }
        val out = File(dir, u.file)
        try {
            _state.value = State.Downloading(0f)
            client.newCall(Request.Builder().url(u.url).header("User-Agent", "SH-Tunebridge-Android").build()).execute().use { r ->
                if (!r.isSuccessful) throw IOException("Download fehlgeschlagen (${r.code})")
                val md = MessageDigest.getInstance("SHA-256")
                var n = 0L
                r.body!!.byteStream().use { input ->
                    out.outputStream().use { o ->
                        val buf = ByteArray(64 * 1024)
                        while (true) {
                            val k = input.read(buf)
                            if (k < 0) break
                            o.write(buf, 0, k); md.update(buf, 0, k); n += k
                            if (n > u.size) throw IOException("Datei größer als angekündigt – abgebrochen")
                            _state.value = State.Downloading((n.toFloat() / u.size).coerceIn(0f, 1f))
                        }
                    }
                }
                val hex = md.digest().joinToString("") { "%02x".format(it) }
                if (n != u.size || hex != u.sha256) throw IOException("Prüfsumme stimmt nicht – Update verworfen")
            }
            _state.value = State.Ready(u, out)
            out
        } catch (e: Exception) {
            dir.deleteRecursively()
            _state.value = State.Failed(e.message ?: "Download fehlgeschlagen")
            null
        }
    }

    /** Darf die App Installationen anbieten? (Android: „Unbekannte Apps installieren“ für SH-Tunebridge) */
    fun canInstall(ctx: Context): Boolean = ctx.packageManager.canRequestPackageInstalls()

    fun openInstallSettings(ctx: Context) {
        ctx.startActivity(Intent(Settings.ACTION_MANAGE_UNKNOWN_APP_SOURCES, Uri.parse("package:${ctx.packageName}"))
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    /** Android-Installer öffnen – du bestätigst dort selbst. */
    fun install(ctx: Context, apk: File) {
        val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.updates", apk)
        ctx.startActivity(Intent(Intent.ACTION_VIEW).setDataAndType(uri, "application/vnd.android.package-archive")
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION or Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    fun dismiss() { _state.value = State.Idle }

    private fun parse(v: String): List<Int>? =
        Regex("""^(\d+)\.(\d+)\.(\d+)$""").find(v)?.groupValues?.drop(1)?.map { it.toInt() }

    private fun compare(a: List<Int>, b: List<Int>): Int {
        for (i in 0 until 3) if (a[i] != b[i]) return a[i].compareTo(b[i])
        return 0
    }

}
