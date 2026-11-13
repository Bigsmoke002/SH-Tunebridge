package de.bs002.tunebridge.ui.screens

import android.content.Intent
import android.net.Uri
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyListScope
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.Text
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.Player
import de.bs002.tunebridge.data.Track
import de.bs002.tunebridge.net.DAlbum
import de.bs002.tunebridge.net.DArtist
import de.bs002.tunebridge.net.DTrack
import de.bs002.tunebridge.net.Discover
import de.bs002.tunebridge.net.DiscoverNeedsConsent
import de.bs002.tunebridge.net.Got
import de.bs002.tunebridge.ui.Fmt
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.Cover
import de.bs002.tunebridge.ui.components.EmptyState
import de.bs002.tunebridge.ui.components.Notice
import de.bs002.tunebridge.ui.components.SectionLabel
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.components.TrackLine
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbType
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.delay
import java.util.Locale

/** Wohin Tipps auf Künstler, Alben und „Remixe & Versionen“ führen. */
class DiscoverNav(val openArtist: (Long) -> Unit, val openAlbum: (Long) -> Unit, val openVersions: (Track) -> Unit, val openMix: () -> Unit)

private sealed interface DLoad<out T> {
    data object Busy : DLoad<Nothing>
    data class Done<T>(val got: Got<T>) : DLoad<T>
    data object NeedConsent : DLoad<Nothing>
    data class Failed(val message: String) : DLoad<Nothing>
}

private class DState<T>(val load: DLoad<T>, val retry: () -> Unit)

/** Lädt [fn] (PC, sonst nach Einwilligung Deezer direkt) neu, sobald sich [key] oder die Einwilligung ändert. [key] null = nichts laden. */
@Composable
private fun <T> loader(key: Any?, fn: suspend () -> Got<T>): DState<T> {
    val direct = App.repo.settings.collectAsState().value.similarDirect
    var retry by remember { mutableIntStateOf(0) }
    var load by remember(key) { mutableStateOf<DLoad<T>>(DLoad.Busy) }
    LaunchedEffect(key, retry, direct) {
        if (key == null) return@LaunchedEffect
        if (load !is DLoad.Done) load = DLoad.Busy
        load = try {
            DLoad.Done(fn())
        } catch (e: CancellationException) {
            throw e
        } catch (e: DiscoverNeedsConsent) {
            DLoad.NeedConsent
        } catch (e: Exception) {
            DLoad.Failed(e.message ?: "Hat nicht geklappt")
        }
    }
    return DState(load) { retry++ }
}

private fun <T> LazyListScope.loadItems(s: DState<T>, content: LazyListScope.(Got<T>) -> Unit) {
    when (val l = s.load) {
        DLoad.Busy -> item { Box(Modifier.fillMaxWidth().padding(40.dp), contentAlignment = Alignment.Center) { CircularProgressIndicator(color = Tb.accent) } }
        DLoad.NeedConsent -> item {
            Notice("Kein PC erreichbar. Unterwegs kann die App direkt bei Deezer stöbern: Dafür gehen deine Suchbegriffe bzw. die " +
                "angetippten Künstler und Alben an Deezer, Deezer sieht deine IP-Adresse. Ausschaltbar unter Mehr › Datenschutz.",
                icon = Ico.Info, color = Tb.accent, modifier = Modifier.padding(horizontal = 20.dp)) {
                Row(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    TbButton("Erlauben", { App.repo.updateSettings { it.copy(similarDirect = true) } }, kind = BtnKind.Primary, small = true)
                }
            }
        }
        is DLoad.Failed -> item { EmptyState(Ico.Info, "Hat nicht geklappt", l.message) { TbButton("Nochmal", s.retry, icon = Ico.Repeat) } }
        is DLoad.Done -> content(l.got)
    }
}

// ------------------------------------------------------------------ Startseite: Suche + Charts
private enum class ChartKind(val label: String) { Songs("Songs"), Artists("Künstler"), Albums("Alben") }

@Composable
fun DiscoverScreen(nav: DiscoverNav) {
    var q by rememberSaveable { mutableStateOf("") }
    var query by rememberSaveable { mutableStateOf("") }
    var genre by rememberSaveable { mutableLongStateOf(0L) }
    var kind by rememberSaveable { mutableStateOf(ChartKind.Songs) }
    var sheet by remember { mutableStateOf<Pair<DTrack, List<DTrack>>?>(null) }
    var pick by remember { mutableStateOf<List<Track>?>(null) }
    LaunchedEffect(q) { if (q.isNotBlank()) delay(450); query = q.trim() }
    val s = loader(query.ifEmpty { null }) { Discover.search(query) }
    val gs = loader("genres") { Discover.genres() }
    val cs = loader(genre) { Discover.charts(genre) }

    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item { ScreenHeader("Entdecken", "Im Deezer-Katalog stöbern – Songs, Künstler, Alben, Charts") }
        item { SearchField(q, { q = it }, Modifier.padding(horizontal = 20.dp), placeholder = "Song, Künstler oder Album …") }
        if (query.isNotEmpty()) {
            loadItems(s) { got ->
                val r = got.value
                if (r.tracks.isEmpty() && r.artists.isEmpty() && r.albums.isEmpty()) {
                    item { EmptyState(Ico.Search, "Nichts gefunden", "Zu „${r.q}“ hat Deezer nichts.") }
                    return@loadItems
                }
                if (r.artists.isNotEmpty()) {
                    item { SectionLabel("Künstler", Modifier.padding(horizontal = 20.dp)) }
                    item { ArtistRow(r.artists, nav) }
                }
                if (r.tracks.isNotEmpty()) {
                    item {
                        SectionLabel("Songs", Modifier.padding(horizontal = 20.dp)) { PlayButtons(r.tracks.map { it.toTrack() }, "Suche: ${r.q}") }
                    }
                    items(r.tracks, key = { "t" + it.ids["deezer"] }) { t -> DRow(t) { sheet = t to r.tracks } }
                }
                if (r.albums.isNotEmpty()) {
                    item { SectionLabel("Alben", Modifier.padding(horizontal = 20.dp)) }
                    item { AlbumRow(r.albums, nav) }
                }
                item { Source(got.from) }
            }
        } else {
            item { Spacer(Modifier.height(6.dp)) }
            (gs.load as? DLoad.Done)?.got?.value?.genres?.let { list ->
                item {
                    LazyRow(Modifier.fillMaxWidth().padding(vertical = 6.dp), contentPadding = PaddingValues(horizontal = 20.dp),
                        horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(list, key = { it.id }) { g -> FilterChip(if (g.id == 0L) "Alle" else g.name, genre == g.id) { genre = g.id } }
                    }
                }
            }
            item {
                Row(Modifier.padding(horizontal = 20.dp, vertical = 4.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    ChartKind.entries.forEach { k -> FilterChip(k.label, kind == k) { kind = k } }
                }
            }
            loadItems(cs) { got ->
                val c = got.value
                when (kind) {
                    ChartKind.Songs -> {
                        item {
                            SectionLabel("Charts", Modifier.padding(horizontal = 20.dp)) {
                                if (c.tracks.isNotEmpty()) PlayButtons(c.tracks.map { it.toTrack() }, "Charts")
                            }
                        }
                        itemsIndexed0(c.tracks) { i, t -> DRow(t, num = i + 1) { sheet = t to c.tracks } }
                        if (c.tracks.isNotEmpty()) item {
                            TbButton("Als Playlist speichern", { pick = c.tracks.map { it.toTrack() } }, kind = BtnKind.Ghost, icon = Ico.Plus,
                                small = true, modifier = Modifier.padding(horizontal = 14.dp, vertical = 6.dp))
                        }
                    }
                    ChartKind.Artists -> items(c.artists, key = { "a" + it.id }) { a -> ArtistLine(a) { nav.openArtist(a.id) } }
                    ChartKind.Albums -> items(c.albums, key = { "al" + it.id }) { a -> AlbumLine(a) { nav.openAlbum(a.id) } }
                }
                item { Source(got.from) }
            }
        }
    }
    sheet?.let { (t, list) -> TrackSheet(t, list, "Entdecken", nav, { pick = listOf(it) }) { sheet = null } }
    pick?.let { PlaylistPicker(it) { pick = null } }
}

private fun <T> LazyListScope.itemsIndexed0(list: List<T>, content: @Composable (Int, T) -> Unit) =
    items(list.size) { i -> content(i, list[i]) }

// ------------------------------------------------------------------ Künstlerseite
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun DiscoverArtistScreen(id: Long, nav: DiscoverNav, back: () -> Unit) {
    val s = loader(id) { Discover.artist(id) }
    var all by rememberSaveable { mutableStateOf(false) }
    var sheet by remember { mutableStateOf<Pair<DTrack, List<DTrack>>?>(null) }
    var pick by remember { mutableStateOf<List<Track>?>(null) }
    val canMix = remember { App.sync.firstReachable() != null }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item { TopBack(back) }
        loadItems(s) { got ->
            val p = got.value
            val a = p.artist
            item {
                Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                    Cover(a.pictureBig ?: a.picture, 168.dp, 84.dp)
                    Spacer(Modifier.height(14.dp))
                    Text(a.name, style = TbType.display, color = Tb.text)
                    val meta = listOfNotNull(a.fans?.takeIf { it > 0 }?.let { "${String.format(Locale.GERMANY, "%,d", it)} Fans" },
                        a.albums?.takeIf { it > 0 }?.let { "$it Veröffentlichungen" }).joinToString(" · ")
                    if (meta.isNotEmpty()) Text(meta, style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 4.dp))
                    FlowRow(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp, Alignment.CenterHorizontally),
                        verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (p.top.isNotEmpty()) TbButton("Reinhören", { Player.play(p.top.map { it.toTrack() }, 0, a.name) }, kind = BtnKind.Primary, icon = Ico.Play)
                        if (p.top.isNotEmpty()) TbButton("Top-Songs als Playlist", { pick = p.top.map { it.toTrack() } }, icon = Ico.Plus)
                        if (canMix && a.id <= Int.MAX_VALUE) TbButton("Mix mit ${a.name}", {
                            App.mixSeed.value = a.id.toInt() to a.name; nav.openMix()
                        }, kind = BtnKind.Ghost, icon = Ico.Sparkle)
                    }
                }
            }
            if (p.top.isNotEmpty()) {
                item { SectionLabel("Beliebteste Songs", Modifier.padding(horizontal = 20.dp)) }
                val shown = if (all) p.top else p.top.take(10)
                itemsIndexed0(shown) { i, t -> DRow(t, num = i + 1, sub = t.with.takeIf { it.isNotEmpty() }?.let { "mit " + it.joinToString(", ") } ?: t.album) { sheet = t to p.top } }
                if (p.top.size > 10) item {
                    TbButton(if (all) "Weniger zeigen" else "Alle ${p.top.size} zeigen", { all = !all }, kind = BtnKind.Ghost, small = true,
                        modifier = Modifier.padding(horizontal = 14.dp))
                }
            }
            if (p.albums.isNotEmpty()) { item { SectionLabel("Alben", Modifier.padding(horizontal = 20.dp)) }; item { AlbumRow(p.albums, nav) } }
            if (p.singles.isNotEmpty()) { item { SectionLabel("Singles & EPs", Modifier.padding(horizontal = 20.dp)) }; item { AlbumRow(p.singles, nav) } }
            if (p.related.isNotEmpty()) { item { SectionLabel("Ähnliche Künstler", Modifier.padding(horizontal = 20.dp)) }; item { ArtistRow(p.related, nav) } }
            item { Source(got.from, a.link) }
        }
    }
    sheet?.let { (t, list) -> TrackSheet(t, list, (s.load as? DLoad.Done)?.got?.value?.artist?.name ?: "Künstler", nav, { pick = listOf(it) }) { sheet = null } }
    pick?.let { PlaylistPicker(it) { pick = null } }
}

/** Künstler eines Songs per Name öffnen (Song-Seite): gleicher Name bevorzugt, sonst bester Treffer. */
@Composable
fun DiscoverArtistByName(name: String, nav: DiscoverNav, back: () -> Unit) {
    val s = loader(name) { Got("", Discover.artistByName(name) ?: -1L) }
    val id = ((s.load as? DLoad.Done)?.got?.value)?.takeIf { it > 0 }
    if (id != null) { DiscoverArtistScreen(id, nav, back); return }
    LazyColumn(Modifier.fillMaxSize()) {
        item { TopBack(back) }
        loadItems(s) { item { EmptyState(Ico.Search, "Nicht gefunden", "„$name“ gibt es bei Deezer nicht als Künstler.") } }
    }
}

// ------------------------------------------------------------------ Albumseite
@OptIn(ExperimentalLayoutApi::class)
@Composable
fun DiscoverAlbumScreen(id: Long, nav: DiscoverNav, back: () -> Unit) {
    val s = loader(id) { Discover.album(id) }
    var sheet by remember { mutableStateOf<Pair<DTrack, List<DTrack>>?>(null) }
    var pick by remember { mutableStateOf<List<Track>?>(null) }
    LazyColumn(Modifier.fillMaxSize(), contentPadding = PaddingValues(bottom = 24.dp)) {
        item { TopBack(back) }
        loadItems(s) { got ->
            val p = got.value
            val a = p.album
            item {
                Column(Modifier.fillMaxWidth().padding(horizontal = 20.dp)) {
                    Box(Modifier.fillMaxWidth(), contentAlignment = Alignment.Center) { Cover(a.coverBig ?: a.cover, 220.dp, 12.dp) }
                    Spacer(Modifier.height(18.dp))
                    Text(a.title, style = TbType.display, color = Tb.text)
                    val who = a.artists.ifEmpty { listOfNotNull(a.artist) }.joinToString(", ")
                    Text(who, style = TbType.heading.copy(fontWeight = TbType.body.fontWeight), color = Tb.accent,
                        modifier = Modifier.padding(top = 2.dp).clickable(enabled = a.artistId != null) { a.artistId?.let(nav.openArtist) })
                    val meta = listOfNotNull(a.type.ifEmpty { null }, a.year, a.label, p.tracks.size.takeIf { it > 0 }?.let { Fmt.songs(it) },
                        a.durationMs?.let { "${it / 60000} Min." }).joinToString("  ·  ")
                    if (meta.isNotEmpty()) Text(meta, style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 8.dp))
                    if (a.genres.isNotEmpty()) Text(a.genres.joinToString(" · "), style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 2.dp))
                    FlowRow(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        if (p.tracks.isNotEmpty()) {
                            TbButton("Abspielen", { Player.play(p.tracks.map { it.toTrack() }, 0, a.title) }, kind = BtnKind.Primary, icon = Ico.Play)
                            TbButton("Als Playlist", { pick = p.tracks.map { it.toTrack() } }, icon = Ico.Plus)
                        }
                    }
                }
            }
            item { SectionLabel("Titel", Modifier.padding(horizontal = 20.dp)) }
            itemsIndexed0(p.tracks) { i, t -> DRow(t, num = i + 1, showCover = false) { sheet = t to p.tracks } }
            if (p.tracks.isEmpty()) item { Text("Deezer liefert zu diesem Album keine Titelliste.", style = TbType.small, color = Tb.text3, modifier = Modifier.padding(20.dp)) }
            item { Source(got.from, a.link) }
        }
    }
    sheet?.let { (t, list) -> TrackSheet(t, list, (s.load as? DLoad.Done)?.got?.value?.album?.title ?: "Album", nav, { pick = listOf(it) }) { sheet = null } }
    pick?.let { PlaylistPicker(it) { pick = null } }
}

// ------------------------------------------------------------------ Bausteine
@Composable
private fun DRow(t: DTrack, num: Int? = null, sub: String? = null, showCover: Boolean = true, onClick: () -> Unit) {
    Row(
        Modifier.fillMaxWidth().padding(horizontal = 10.dp).clip(RoundedCornerShape(Tb.radiusSm)).clickable(onClick = onClick)
            .padding(horizontal = 10.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (num != null) Text("$num", style = TbType.small, color = Tb.text3, modifier = Modifier.width(26.dp))
        if (showCover) { Cover(t.cover, 44.dp); Spacer(Modifier.width(12.dp)) }
        Column(Modifier.weight(1f)) {
            TrackLine(t.title, t.artists.joinToString(", "))
            if (sub != null) Text(sub, style = TbType.small, color = Tb.text3, maxLines = 1, overflow = TextOverflow.Ellipsis)
        }
        if (t.explicit) Text("E", style = TbType.small, color = Tb.text3, modifier = Modifier.padding(horizontal = 6.dp))
        t.durationMs?.let { Text(Fmt.duration(it), style = TbType.small, color = Tb.text3) }
    }
}

@Composable
private fun ArtistRow(list: List<DArtist>, nav: DiscoverNav) {
    LazyRow(Modifier.fillMaxWidth(), contentPadding = PaddingValues(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(14.dp)) {
        items(list, key = { it.id }) { a ->
            Column(Modifier.width(96.dp).clip(RoundedCornerShape(Tb.radiusSm)).clickable { nav.openArtist(a.id) }.padding(vertical = 4.dp),
                horizontalAlignment = Alignment.CenterHorizontally) {
                Cover(a.picture, 88.dp, 44.dp)
                Text(a.name, style = TbType.small, color = Tb.text, maxLines = 2, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 6.dp))
            }
        }
    }
}

@Composable
private fun AlbumRow(list: List<DAlbum>, nav: DiscoverNav) {
    LazyRow(Modifier.fillMaxWidth(), contentPadding = PaddingValues(horizontal = 20.dp), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        items(list, key = { it.id }) { a ->
            Column(Modifier.width(128.dp).clip(RoundedCornerShape(Tb.radiusSm)).clickable { nav.openAlbum(a.id) }.padding(vertical = 4.dp)) {
                Cover(a.cover, 128.dp)
                Text(a.title, style = TbType.bodyStrong, color = Tb.text, maxLines = 1, overflow = TextOverflow.Ellipsis, modifier = Modifier.padding(top = 6.dp))
                Text(listOfNotNull(a.year, a.type.ifEmpty { null }, a.artist).joinToString(" · "), style = TbType.small, color = Tb.text3,
                    maxLines = 1, overflow = TextOverflow.Ellipsis)
            }
        }
    }
}

@Composable
private fun ArtistLine(a: DArtist, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp).clip(RoundedCornerShape(Tb.radiusSm)).clickable(onClick = onClick)
        .padding(horizontal = 10.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Cover(a.picture, 48.dp, 24.dp)
        Spacer(Modifier.width(12.dp))
        TrackLine(a.name, a.fans?.takeIf { it > 0 }?.let { "${String.format(Locale.GERMANY, "%,d", it)} Fans" } ?: "Künstler", Modifier.weight(1f))
    }
}

@Composable
private fun AlbumLine(a: DAlbum, onClick: () -> Unit) {
    Row(Modifier.fillMaxWidth().padding(horizontal = 10.dp).clip(RoundedCornerShape(Tb.radiusSm)).clickable(onClick = onClick)
        .padding(horizontal = 10.dp, vertical = 8.dp), verticalAlignment = Alignment.CenterVertically) {
        Cover(a.cover, 48.dp)
        Spacer(Modifier.width(12.dp))
        TrackLine(a.title, listOfNotNull(a.artist, a.year, a.type.ifEmpty { null }).joinToString(" · "), Modifier.weight(1f))
    }
}

@Composable
private fun Source(from: String, link: String? = null) {
    val ctx = LocalContext.current
    Row(Modifier.fillMaxWidth().padding(horizontal = 20.dp, vertical = 14.dp), verticalAlignment = Alignment.CenterVertically) {
        Text("Daten von Deezer · $from", style = TbType.small, color = Tb.text3, modifier = Modifier.weight(1f))
        if (link != null && link.startsWith("https://")) TbButton("Bei Deezer", {
            runCatching { ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(link))) }
        }, kind = BtnKind.Ghost, icon = Ico.External, small = true)
    }
}

/** Song antippen: Reinhören, Zur Playlist, Remixe & Versionen, Künstler/Album, Links. */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalLayoutApi::class)
@Composable
private fun TrackSheet(d: DTrack, list: List<DTrack>, title: String, nav: DiscoverNav, pick: (Track) -> Unit, close: () -> Unit) {
    val s = d.toTrack()
    ModalBottomSheet(onDismissRequest = close, sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true), containerColor = Tb.bg1) {
        Column(Modifier.padding(horizontal = 20.dp).padding(bottom = 28.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Cover(s.cover, 64.dp)
                Spacer(Modifier.width(14.dp))
                Column(Modifier.weight(1f)) {
                    TrackLine(s.title, s.artist)
                    d.album?.let { Text(it, style = TbType.small, color = Tb.text3, maxLines = 1, overflow = TextOverflow.Ellipsis) }
                }
            }
            FlowRow(Modifier.padding(top = 14.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                TbButton("Reinhören", {
                    val tracks = list.map { it.toTrack() }
                    Player.play(tracks, list.indexOf(d).coerceAtLeast(0), title); close()
                }, kind = BtnKind.Primary, icon = Ico.Play)
                TbButton("Zur Playlist", { close(); pick(s) }, icon = Ico.Plus)
                TbButton("Remixe & Versionen", { close(); nav.openVersions(s) }, kind = BtnKind.Ghost, icon = Ico.Disc)
            }
            val people = d.artists.mapIndexedNotNull { i, n -> d.artistIds.getOrNull(i)?.let { n to it } }
            if (people.isNotEmpty() || d.albumId != null) {
                SectionLabel("Mehr davon")
                FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    people.forEach { (n, id) -> FilterChip(n, false, Ico.Compass) { close(); nav.openArtist(id) } }
                    d.albumId?.let { id -> FilterChip(d.album ?: "Album", false, Ico.Disc) { close(); nav.openAlbum(id) } }
                }
            }
            SectionLabel("Anhören & öffnen")
            LinkGrid(s, emptyMap())
        }
    }
}
