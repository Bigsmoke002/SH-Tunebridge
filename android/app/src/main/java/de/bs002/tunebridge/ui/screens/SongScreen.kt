package de.bs002.tunebridge.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.Player
import de.bs002.tunebridge.data.Track
import de.bs002.tunebridge.ui.Fmt
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.Cover
import de.bs002.tunebridge.ui.components.GenreChip
import de.bs002.tunebridge.ui.components.IconBtn
import de.bs002.tunebridge.ui.favorite
import de.bs002.tunebridge.ui.components.Notice
import de.bs002.tunebridge.ui.components.Pill
import de.bs002.tunebridge.ui.components.SectionLabel
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.flag
import de.bs002.tunebridge.ui.links
import de.bs002.tunebridge.ui.shownGenre
import de.bs002.tunebridge.ui.str
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import java.net.URLEncoder

/** Wie links.py am Desktop: direkte Links, wo bekannt, sonst die Suche beim Dienst. */
private val PLATFORMS = listOf(
    Triple("spotify", "Spotify", "https://open.spotify.com/search/%s"),
    Triple("applemusic", "Apple Music", "https://music.apple.com/de/search?term=%s"),
    Triple("youtubemusic", "YouTube Music", "https://music.youtube.com/search?q=%s"),
    Triple("youtube", "YouTube", "https://www.youtube.com/results?search_query=%s"),
    Triple("deezer", "Deezer", "https://www.deezer.com/search/%s"),
    Triple("soundcloud", "SoundCloud", "https://soundcloud.com/search/sounds?q=%s"),
    Triple("tidal", "TIDAL", "https://listen.tidal.com/search?q=%s"),
    Triple("bandcamp", "Bandcamp", "https://bandcamp.com/search?q=%s&item_type=t"),
)
private val STYLE = mapOf(
    "spotify" to ("S" to 0xFF1ED760), "applemusic" to ("A" to 0xFFFA6A86), "youtubemusic" to ("YM" to 0xFFFF5A50),
    "youtube" to ("YT" to 0xFFFF5A50), "deezer" to ("D" to 0xFFA238FF), "soundcloud" to ("SC" to 0xFFFF8A3D),
    "tidal" to ("T" to 0xFFD6DBE2), "bandcamp" to ("BC" to 0xFF5FA8C9), "shazam" to ("Sh" to 0xFF0A8CFF),
)

@Composable
fun SongScreen(uid: String, back: () -> Unit, openSimilar: (Track) -> Unit = {}, openVersions: (Track) -> Unit = {}) {
    val history by App.repo.history.collectAsState()
    val rec = history.firstOrNull { it.uid == uid }
    if (rec == null) {
        Column(Modifier.fillMaxSize()) { TopBack(back); Text("Nicht mehr im Verlauf.", style = TbType.body, color = Tb.text3, modifier = Modifier.padding(20.dp)) }
        return
    }
    val playing by Player.playing.collectAsState()
    var pick by remember { mutableStateOf(false) }
    val t = rec.track
    val x = rec.extra

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.weight(1f)) { TopBack(back) }
            val ctx = LocalContext.current
            IconBtn(Ico.Share, "Song teilen", { de.bs002.tunebridge.data.Export.shareSong(ctx, de.bs002.tunebridge.data.Export.Item(t, rec.ts, rec.source, x.links())) },
                modifier = Modifier.padding(top = 8.dp))
            val fav = rec.favorite
            IconBtn(if (fav) Ico.HeartFill else Ico.Heart, if (fav) "Aus Favoriten entfernen" else "Zu Favoriten",
                { App.repo.setFavorite(rec, !fav) }, tint = if (fav) Tb.danger else Tb.text2, modifier = Modifier.padding(top = 8.dp, end = 12.dp))
        }
        Column(Modifier.padding(horizontal = 20.dp)) {
            if (x.flag("unsure")) {
                Notice("Unsicherer Treffer: nur mit Tempo-Abweichung gefunden. Stimmt das?") {
                    Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        TbButton("Stimmt", { App.repo.updateExtra(uid, JsonObject(x - "unsure" + ("confirmed" to JsonPrimitive(true)))) },
                            kind = BtnKind.Primary, icon = Ico.Check, small = true)
                        TbButton("Falsch", { deleteWithUndo(uid); back() }, kind = BtnKind.Ghost, small = true)
                    }
                }
                Spacer(Modifier.height(16.dp))
            }
            Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) { Cover(t.cover, 232.dp, 12.dp) }
            Spacer(Modifier.height(22.dp))
            Text(t.title, style = TbType.display, color = Tb.text)
            Text(t.artist, style = TbType.heading.copy(fontWeight = TbType.body.fontWeight), color = Tb.text2, modifier = Modifier.padding(top = 2.dp))
            val meta = listOfNotNull(t.album, x.str("label"), x.str("year")).joinToString("  ·  ")
            if (meta.isNotEmpty()) Text(meta, style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 8.dp))
            Spacer(Modifier.height(14.dp))
            Chips(rec.shownGenre, t.subgenre, t.niche, x.str("bpm"), rec.track.genre == null && x.str("shazam_genre") != null)
            Spacer(Modifier.height(18.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                t.previewUrl?.let { url ->
                    TbButton(if (playing == url) "Stopp" else "Reinhören", { Player.toggle(url, t) }, kind = BtnKind.Primary,
                        icon = if (playing == url) Ico.Pause else Ico.Play)
                }
                TbButton("Zur Playlist", { pick = true }, icon = Ico.Plus)
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TbButton("Ähnliche Songs", { openSimilar(t) }, kind = BtnKind.Ghost, icon = Ico.Sparkle)
                TbButton("Remixe & Versionen", { openVersions(t) }, kind = BtnKind.Ghost, icon = Ico.Disc)
            }
            Text(
                "${when {
                    !rec.host.startsWith("Handy") -> "Am PC (${rec.host}) erkannt"
                    rec.source == "geteilt" -> "Aus Shazam geteilt"
                    rec.source == "shazam-app" -> "Aus der Shazam-App übernommen"
                    rec.source == "handy-ton" -> "Vom Handy-Ton erkannt"
                    else -> "Mit dem Handy erkannt"
                }} · ${Fmt.ago(rec.ts)}",
                style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 14.dp),
            )

            SectionLabel("Anhören & öffnen")
            LinkGrid(t, x.links())

            SectionLabel("Stimmt etwas nicht?")
            TbButton("Falsch erkannt – aus dem Verlauf entfernen", { deleteWithUndo(uid); back() }, kind = BtnKind.Danger, icon = Ico.Trash)
            Spacer(Modifier.height(32.dp))
        }
    }
    if (pick) PlaylistPicker(t) { pick = false }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun Chips(genre: String?, sub: String?, niche: String?, bpm: String?, roughOnly: Boolean) {
    FlowRow(horizontalArrangement = Arrangement.spacedBy(6.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
        GenreChip(genre)
        if (sub != null) GenreChip(genre, sub)
        if (niche != null) GenreChip(genre, niche)
        if (bpm != null) Pill("$bpm BPM")
        if (roughOnly) Pill("grob laut Shazam – genauer nach dem PC-Abgleich", Tb.warn, Tb.warn.copy(alpha = 0.08f))
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun LinkGrid(t: Track, direct: Map<String, String>) {
    val ctx = LocalContext.current
    val q = URLEncoder.encode("${t.artists.firstOrNull().orEmpty()} ${t.title}".trim(), "UTF-8")
    val alias = mapOf("apple" to "applemusic", "itunes" to "applemusic")
    // Bekannte Dienst-Nummern (vom PC-Abgleich) als direkte Links; eigene Links haben Vorrang
    val fromIds = buildMap {
        t.ids["spotify"]?.let { put("spotify", "https://open.spotify.com/track/$it") }
        t.ids["deezer"]?.let { put("deezer", "https://www.deezer.com/track/$it") }
        t.ids["tidal"]?.let { put("tidal", "https://tidal.com/browse/track/$it") }
        t.ids["youtube"]?.let { put("youtubemusic", "https://music.youtube.com/watch?v=$it") }
    }
    val known = fromIds + direct.mapKeys { alias[it.key] ?: it.key }
    val tiles = buildList {
        known["shazam"]?.let { add(Triple("shazam", "Shazam", it to true)) }
        PLATFORMS.forEach { (id, name, search) ->
            val own = known[id]
            // Shazam liefert für Spotify oft nur „spotify:search:…“ – öffnet die App, ist aber eine Suche
            add(Triple(id, name, (own ?: search.format(q)) to (own != null && !own.contains("search", ignoreCase = true))))
        }
    }
    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp), maxItemsInEachRow = 2) {
        tiles.forEach { (id, name, link) ->
            val (url, isDirect) = link
            val (mark, color) = STYLE[id] ?: ("?" to 0xFF888888)
            val c = androidx.compose.ui.graphics.Color(color)
            val shape = RoundedCornerShape(Tb.radiusSm)
            Row(
                Modifier.weight(1f).clip(shape).background(Tb.bg2).border(1.dp, if (isDirect) c.copy(alpha = 0.35f) else Tb.line, shape)
                    .clickable { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))) }.padding(10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Box(Modifier.size(30.dp).clip(RoundedCornerShape(8.dp)).border(1.dp, c.copy(alpha = 0.6f), RoundedCornerShape(8.dp)), contentAlignment = Alignment.Center) {
                    Text(mark, style = TbType.label, color = c, textAlign = TextAlign.Center)
                }
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(name, style = TbType.bodyStrong, color = Tb.text, maxLines = 1)
                    Text(if (isDirect) "direkt" else "Suche", style = TbType.small, color = Tb.text3)
                }
            }
        }
    }
}

@Composable
fun TopBack(back: () -> Unit, title: String? = null) {
    Row(Modifier.fillMaxWidth().padding(start = 6.dp, top = 8.dp, end = 12.dp), verticalAlignment = Alignment.CenterVertically) {
        IconBtn(Ico.Back, "Zurück", back)
        if (title != null) Text(title, style = TbType.heading, color = Tb.text, modifier = Modifier.padding(start = 4.dp))
    }
}

@Composable
fun PlaylistPicker(track: Track, close: () -> Unit) = PlaylistPicker(listOf(track), close)

/** Songs in eine Playlist legen – auf dem Handy oder (gekoppelt) in eine PC-Playlist. */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PlaylistPicker(tracks: List<Track>, close: () -> Unit) {
    val lists by App.repo.playlists.collectAsState()
    val pcs = App.repo.settings.collectAsState().value.pcs
    var name by remember { mutableStateOf("") }
    val targets = listOf(de.bs002.tunebridge.data.PHONE) + pcs.map { it.pcId }
    var target by remember { mutableStateOf(pcs.firstOrNull()?.pcId ?: de.bs002.tunebridge.data.PHONE) }
    val single = tracks.singleOrNull()
    fun add(pc: String, list: String) {
        val n = App.repo.addAllToPlaylist(pc, list, tracks)
        App.snack(when {
            single != null && n == 0 -> "Schon in „$list“"
            single != null -> "Zu „$list“ hinzugefügt"
            n == 0 -> "Alle schon in „$list“"
            else -> "${Fmt.songs(n)} zu „$list“ hinzugefügt"
        })
        close()
    }
    ModalBottomSheet(onDismissRequest = close, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = Tb.bg1) {
        Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
            Text(if (single != null) "Zur Playlist hinzufügen" else "${Fmt.songs(tracks.size)} zur Playlist", style = TbType.title, color = Tb.text)
            val pc = target
            Text(if (pc == de.bs002.tunebridge.data.PHONE) "Bleibt auf dem Handy." else "Landet beim nächsten Abgleich auch in der Playlist am PC.",
                style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 4.dp, bottom = 12.dp))
            if (targets.size > 1) {
                Segmented(targets, pc, { id -> if (id == de.bs002.tunebridge.data.PHONE) "Handy" else pcs.first { it.pcId == id }.pcName }) { target = it }
                Spacer(Modifier.height(10.dp))
            }
            SearchField(name, { name = it }, placeholder = "Neue Playlist oder suchen …")
            Spacer(Modifier.height(8.dp))
            val mine = lists.filter { it.pc == pc }
            val shown = mine.filter { name.isBlank() || it.name.contains(name.trim(), true) }.take(40)
            if (name.isNotBlank() && mine.none { it.name.equals(name.trim(), true) }) {
                PickRow("Neu: ${name.trim()}", null, Ico.Plus) { add(pc, name.trim().take(120)) }
            }
            if (mine.isEmpty() && name.isBlank()) Text(
                if (pc == de.bs002.tunebridge.data.PHONE) "Noch keine Playlist auf dem Handy – oben einen Namen eingeben." else "Noch keine Playlists von diesem PC.",
                style = TbType.small, color = Tb.text3, modifier = Modifier.padding(vertical = 8.dp))
            shown.forEach { p ->
                val inside = single != null && p.tracks.any { it.key == single.key }
                PickRow(p.name, Fmt.songs(p.tracks.size), if (inside) Ico.Check else Ico.Stack) {
                    if (inside) { App.repo.removeFromPlaylist(pc, p.name, single!!); App.snack("Aus „${p.name}“ entfernt"); close() }
                    else add(pc, p.name)
                }
            }
        }
    }
}

@Composable
private fun PickRow(title: String, sub: String?, icon: Ico, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().clip(RoundedCornerShape(Tb.radiusSm)).clickable(onClick = onClick).padding(vertical = 11.dp, horizontal = 4.dp),
        verticalAlignment = Alignment.CenterVertically) {
        TbIcon(icon, if (icon == Ico.Check) Tb.accent else Tb.text2, 18.dp)
        Spacer(Modifier.width(14.dp))
        Text(title, style = TbType.bodyStrong, color = Tb.text, modifier = Modifier.weight(1f), maxLines = 1)
        if (sub != null) Text(sub, style = TbType.small, color = Tb.text3)
    }
}

/** Aus dem Verlauf entfernen, mit „Rückgängig“ in der Meldung unten. */
fun deleteWithUndo(vararg uids: String) {
    val gone = App.repo.deleteMany(uids.toList())
    if (gone.isEmpty()) return
    App.snack(if (gone.size == 1) "„${gone[0].track.title}“ entfernt" else "${Fmt.songs(gone.size)} entfernt", "Rückgängig") { App.repo.restore(gone) }
}
