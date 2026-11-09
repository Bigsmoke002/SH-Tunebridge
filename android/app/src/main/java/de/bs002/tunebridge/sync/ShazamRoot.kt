package de.bs002.tunebridge.sync

import android.content.Context
import android.database.sqlite.SQLiteDatabase
import android.util.Log
import de.bs002.tunebridge.App
import de.bs002.tunebridge.net.Shazam
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import java.io.File

/**
 * Eigenen Shazam-Verlauf aus der Shazam-App übernehmen – NUR mit Root (nur für erfahrene Nutzer).
 *
 * Shazam/Apple bieten dafür keine Schnittstelle. Mit Root kopiert die App die Datenbank der Shazam-App
 * (`library.db`) kurz in ihren eigenen Cache, liest daraus ausschließlich Song-Nummer, Titel, Künstler und
 * Zeitpunkt und löscht die Kopie sofort wieder. Nicht gelesen werden u. a. Standort (lat/lon/Ort), die
 * Audio-Signatur, Konto- oder Anmeldedaten. An der Shazam-App wird nichts verändert.
 */
object ShazamRoot {
    const val WARNING_VERSION = 1
    private const val PKG = "com.shazam.android"
    private val DIRS = listOf("/data/user/0/$PKG/databases", "/data/data/$PKG/databases")

    class RootError(msg: String) : Exception(msg)

    data class Item(val requestId: String, val key: String, val ts: Long, val title: String?, val artists: List<String>)

    data class Result(val found: Int, val added: Int, val already: Int, val looked: Int)

    /** Gibt es überhaupt ein su? (Nur Dateien prüfen – fragt noch keinen Root-Zugriff an.) */
    fun hasSu(): Boolean =
        (System.getenv("PATH").orEmpty().split(':') + listOf("/system/bin", "/system/xbin", "/sbin", "/debug_ramdisk", "/system_ext/bin"))
            .any { File(it, "su").exists() }

    fun shazamInstalled(ctx: Context): Boolean =
        runCatching { ctx.packageManager.getPackageInfo(PKG, 0); true }.getOrDefault(false)

    /** Datei der Shazam-App per `su` in [dst] kopieren. false = Datei fehlt; RootError = kein Root. */
    private fun suCopy(src: String, dst: File): Boolean {
        // Seit Android 11 sieht ein su im Bereich dieser App die Daten anderer Apps nicht (App-Daten-Isolierung).
        // Darum im globalen Bereich lesen: Magisk/KernelSU „--mount-master“, sonst nsenter; zuletzt einfach su.
        val cat = "cat '$src'"
        val ways = listOf(
            listOf("su", "--mount-master", "-c", cat),
            listOf("su", "-c", "nsenter -t 1 -m -- $cat"),
            listOf("su", "-c", cat),
        )
        for (cmd in ways) {
            val ok = runCatching {
                val p = ProcessBuilder(cmd).redirectError(File("/dev/null")).start()
                p.outputStream.close()
                dst.outputStream().use { out -> p.inputStream.use { it.copyTo(out) } }
                p.waitFor() == 0 && dst.length() > 0L
            }.getOrDefault(false)
            if (ok) return true
            Log.i("TbShz", "Kopieren über „${cmd.dropLast(1).joinToString(" ")}“ ging nicht: $src")
            dst.delete()
        }
        return false
    }

    private fun checkRoot() {
        val ok = runCatching {
            val p = ProcessBuilder("su", "-c", "id -u").redirectErrorStream(true).start()
            p.outputStream.close()
            val out = p.inputStream.bufferedReader().readText().trim()
            p.waitFor() == 0 && out.endsWith("0")
        }.getOrDefault(false)
        if (!ok) throw RootError("Kein Root-Zugriff – abgelehnt im Root-Manager oder das Handy ist nicht gerootet.")
    }

    /** Liest die eigenen Shazams. Die Kopie im Cache wird in jedem Fall gelöscht. */
    suspend fun read(ctx: Context): List<Item> = withContext(Dispatchers.IO) {
        if (!shazamInstalled(ctx)) throw RootError("Die Shazam-App ist auf diesem Handy nicht installiert.")
        checkRoot()
        val dir = File(ctx.cacheDir, "shz").apply { deleteRecursively(); mkdirs() }
        try {
            val db = File(dir, "library.db")
            val base = DIRS.firstOrNull { suCopy("$it/library.db", db) }
                ?: throw RootError("Shazam-Datenbank nicht gefunden – evtl. hat ein Shazam-Update sie verändert.")
            suCopy("$base/library.db-wal", File(dir, "library.db-wal"))     // neueste Einträge (falls vorhanden)
            SQLiteDatabase.openDatabase(db.path, null, SQLiteDatabase.OPEN_READWRITE).use { d ->
                val artistsSql = runCatching {
                    d.rawQuery("SELECT 1 FROM apple_artist_track JOIN artist ON artist.artist_id = apple_artist_track.artist_adam_id LIMIT 1", null).close()
                    "(SELECT group_concat(artist.artist_name, '\u001f') FROM apple_artist_track JOIN artist " +
                        "ON artist.artist_id = apple_artist_track.artist_adam_id WHERE apple_artist_track.track_key = tag.track_key)"
                }.getOrDefault("NULL")
                // Ausschließlich diese Spalten – kein Standort, keine Signatur.
                val sql = "SELECT tag.request_id, tag.track_key, tag.timestamp, track.track_title, $artistsSql " +
                    "FROM tag LEFT JOIN track ON track.track_key = tag.track_key " +
                    "WHERE tag.track_key IS NOT NULL AND tag.track_key != '' ORDER BY tag.timestamp"
                val out = ArrayList<Item>()
                runCatching { d.rawQuery(sql, null) }
                    .getOrElse { throw RootError("Unbekannter Aufbau der Shazam-Datenbank – evtl. nach einem Shazam-Update. Bitte melden.") }
                    .use { c ->
                        while (c.moveToNext()) {
                            out += Item(
                                requestId = c.getString(0), key = c.getString(1), ts = c.getLong(2),
                                title = c.getString(3)?.takeIf { it.isNotBlank() },
                                artists = c.getString(4)?.split('\u001f')?.map { it.trim() }?.filter { it.isNotEmpty() }.orEmpty(),
                            )
                        }
                    }
                out
            }
        } finally {
            dir.deleteRecursively()
        }
    }

    /** Auslesen und in den eigenen Verlauf übernehmen. Fehlende Künstler fragt die App bei Shazam nach (wie beim Teilen). */
    suspend fun import(ctx: Context, progress: (String) -> Unit = {}): Result {
        progress("Lese Shazam-Verlauf …")
        val items = read(ctx)
        val known = App.repo.knownUids("android-shz-")
        val fresh = items.filter { "android-shz-${it.requestId}" !in known }
        val tracks = HashMap<String, Shazam.Hit?>()
        var looked = 0
        val need = fresh.filter { it.artists.isEmpty() || it.title == null }.map { it.key }.distinct().take(300)
        for ((i, key) in need.withIndex()) {
            progress("Ergänze Angaben bei Shazam … ${i + 1}/${need.size}")
            tracks[key] = runCatching { Shazam.track(key) }.getOrNull()
            looked++
            delay(250)
        }
        val added = App.repo.importShazamApp(fresh, tracks)
        return Result(found = items.size, added = added, already = items.size - fresh.size, looked = looked)
    }
}
