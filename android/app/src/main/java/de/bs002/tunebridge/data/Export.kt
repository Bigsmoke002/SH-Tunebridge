package de.bs002.tunebridge.data

import android.content.Context
import android.content.Intent
import androidx.core.content.FileProvider
import java.io.File
import java.net.URLEncoder
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Verlauf oder Playlist als Datei teilen (Android-Teilen-Menü) – nur Song-Angaben und Links, keine Cover, keine
 * Hörproben. Die Datei liegt kurz im App-Cache (export/) und wird beim nächsten Export ersetzt.
 */
object Export {
    enum class Format(val label: String, val ext: String, val mime: String, val hint: String) {
        Text("Text", "txt", "text/plain", "Liste „Künstler – Titel“ mit Link – für Chats und Notizen"),
        Csv("CSV", "csv", "text/csv", "Tabelle für Excel/LibreOffice oder Import in andere Musik-Apps"),
        M3u("M3U", "m3u8", "audio/x-mpegurl", "Playlist-Datei mit Links (z. B. für Player, die Web-Links öffnen)"),
    }

    class Item(val track: Track, val ts: Double? = null, val source: String? = null, val links: Map<String, String> = emptyMap(), val genre: String? = track.genre)

    /** Bester Link: direkte Dienst-Adresse, sonst die Deezer-Suche. */
    fun link(i: Item): String {
        val t = i.track
        t.ids["spotify"]?.let { return "https://open.spotify.com/track/$it" }
        t.ids["deezer"]?.let { return "https://www.deezer.com/track/$it" }
        i.links["spotify"]?.takeIf { it.startsWith("https://") }?.let { return it }
        i.links["shazam"]?.takeIf { it.startsWith("https://") }?.let { return it }
        t.ids["youtube"]?.let { return "https://music.youtube.com/watch?v=$it" }
        return "https://www.deezer.com/search/" + URLEncoder.encode("${t.artists.firstOrNull().orEmpty()} ${t.title}".trim(), "UTF-8").replace("+", "%20")
    }

    fun render(title: String, items: List<Item>, f: Format): String = when (f) {
        Format.Text -> buildString {
            append(title).append(" (").append(items.size).append(if (items.size == 1) " Song" else " Songs").append(")\n\n")
            items.forEachIndexed { n, i -> append(n + 1).append(". ").append(name(i.track)).append('\n').append("   ").append(link(i)).append('\n') }
            append("\n– geteilt mit SH-Tunebridge")
        }
        Format.Csv -> buildString {
            val day = SimpleDateFormat("yyyy-MM-dd HH:mm", Locale.GERMANY)
            append(row("Titel", "Künstler", "Album", "ISRC", "Genre", "Erkannt", "Quelle", "Link")).append("\r\n")
            items.forEach { i ->
                val t = i.track
                append(row(t.title, t.artist, t.album.orEmpty(), t.isrc.orEmpty(), i.genre.orEmpty(),
                    i.ts?.let { day.format(Date((it * 1000).toLong())) }.orEmpty(), sourceName(i.source), link(i))).append("\r\n")
            }
        }
        Format.M3u -> buildString {
            append("#EXTM3U\n#PLAYLIST:").append(title.replace('\n', ' ')).append('\n')
            items.forEach { i ->
                val secs = i.track.durationMs?.let { it / 1000 } ?: -1
                append("#EXTINF:").append(secs).append(',').append(name(i.track).replace('\n', ' ')).append('\n').append(link(i)).append('\n')
            }
        }
    }

    private fun sourceName(s: String?) = when (s) {
        null -> ""
        "handy-mikrofon" -> "Handy (Mikrofon)"
        "handy-ton" -> "Handy (Handy-Ton)"
        "geteilt" -> "Aus Shazam geteilt"
        "shazam-app" -> "Shazam-App"
        else -> "PC"
    }

    private fun name(t: Track) = if (t.artist.isBlank()) t.title else "${t.artist} – ${t.title}"

    /** CSV nach RFC 4180, Semikolon (deutsches Excel); Formel-Zeichen am Anfang entschärfen (CSV-Injection). */
    private fun row(vararg cells: String) = cells.joinToString(";") { c ->
        val v = if (c.isNotEmpty() && c[0] in "=+-@\t\r") "'$c" else c
        "\"" + v.replace("\"", "\"\"") + "\""
    }

    fun share(ctx: Context, title: String, items: List<Item>, f: Format) {
        val dir = File(ctx.cacheDir, "export").apply { deleteRecursively(); mkdirs() }
        val safe = title.replace(Regex("""[^\p{L}\p{N} ._-]+"""), "").trim().ifBlank { "SH-Tunebridge" }.take(60)
        val file = File(dir, "$safe.${f.ext}")
        // BOM, damit Excel die Umlaute in der CSV richtig liest
        file.writeText((if (f == Format.Csv) "﻿" else "") + render(title, items, f))
        val uri = FileProvider.getUriForFile(ctx, "${ctx.packageName}.updates", file)
        val send = Intent(Intent.ACTION_SEND).setType(f.mime).putExtra(Intent.EXTRA_STREAM, uri).putExtra(Intent.EXTRA_SUBJECT, title)
            .addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        if (f == Format.Text) send.putExtra(Intent.EXTRA_TEXT, render(title, items, f))
        ctx.startActivity(Intent.createChooser(send, "$title teilen").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }

    /** Einzelnen Song als Text teilen. */
    fun shareSong(ctx: Context, i: Item) {
        val text = "${name(i.track)}\n${link(i)}"
        ctx.startActivity(Intent.createChooser(Intent(Intent.ACTION_SEND).setType("text/plain").putExtra(Intent.EXTRA_TEXT, text), "Song teilen")
            .addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
    }
}
