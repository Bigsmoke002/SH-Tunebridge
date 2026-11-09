package de.bs002.tunebridge.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.App
import de.bs002.tunebridge.Player
import de.bs002.tunebridge.data.Export
import de.bs002.tunebridge.data.Repository
import de.bs002.tunebridge.data.Track
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.Cover
import de.bs002.tunebridge.ui.components.EmptyState
import de.bs002.tunebridge.ui.components.Notice
import de.bs002.tunebridge.ui.components.SectionLabel
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.components.TbCard
import de.bs002.tunebridge.ui.components.TrackLine
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbType
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable
import kotlinx.serialization.json.JsonArray
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.contentOrNull
import kotlinx.serialization.json.intOrNull
import kotlinx.serialization.json.jsonArray
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put

/** Ein Song aus einem Mix/Set (vom PC, mit Tempo/Tonart, soweit gemessen). */
@Serializable
private data class JobItem(
    val title: String, val artists: List<String> = emptyList(), val album: String? = null, val cover: String? = null,
    @SerialName("duration_ms") val durationMs: Long? = null, val isrc: String? = null, val ids: Map<String, String> = emptyMap(),
    @SerialName("preview_url") val previewUrl: String? = null, val bpm: Double? = null, val camelot: String? = null,
    val genre: String? = null, val subgenre: String? = null,
) {
    fun track() = Track(title = title, artists = artists, album = album, durationMs = durationMs, isrc = isrc, ids = ids,
        genre = genre, subgenre = subgenre, cover = cover, previewUrl = previewUrl?.takeIf { it.startsWith("http") })
}

/** Laufender oder fertiger Auftrag am PC. */
private data class Job(
    val id: String, val state: String = "running", val done: Int = 0, val total: Int = 0, val phase: String? = null,
    val error: String? = null, val note: String = "", val items: List<JobItem> = emptyList(), val order: List<Int> = emptyList(),
    val summary: String = "",
) {
    val ordered: List<JobItem> get() = order.mapNotNull { items.getOrNull(it) }
}

private fun JsonObject.str(k: String) = (this[k] as? JsonPrimitive)?.contentOrNull
private fun JsonObject.int(k: String) = (this[k] as? JsonPrimitive)?.intOrNull ?: 0

private fun parseJob(id: String, o: JsonObject, kind: String): Job {
    val items = (o["items"] as? JsonArray)?.map { App.repo.json.decodeFromJsonElement(JobItem.serializer(), it) } ?: emptyList()
    val order = (o["order"] as? JsonArray)?.mapNotNull { (it as? JsonPrimitive)?.intOrNull } ?: emptyList()
    val summary = if (kind == "set" && o["bekannt"] != null)
        "${o.int("harmonisch")} von ${o.int("bekannt")} Übergängen harmonisch · ${o.int("minuten")} min" else ""
    return Job(id, o.str("state") ?: "running", o.int("done"), o.int("total"), o.str("phase"), o.str("error"), o.str("note") ?: "",
        items, order, summary)
}

/** Stand abfragen, bis fertig (alle 2 s). */
private suspend fun poll(link: Repository.PcLink, kind: String, id: String, update: (Job) -> Unit) {
    while (true) {
        val o = App.sync.job(link, "status", buildJsonObject { put("kind", kind); put("job", id) })
        val j = parseJob(id, o, kind)
        update(j)
        if (j.state != "running" && j.state != "analysing") return
        delay(2000)
    }
}

// ------------------------------------------------------------------ Mix erstellen

@OptIn(ExperimentalLayoutApi::class)
@Composable
fun MixScreen(back: () -> Unit) {
    val scope = rememberCoroutineScope()
    val link = remember { App.sync.firstReachable() }
    var byGenre by remember { mutableStateOf(false) }
    var q by remember { mutableStateOf("") }
    var found by remember { mutableStateOf<List<Pair<Int, String>>>(emptyList()) }
    var seeds by remember { mutableStateOf<List<Pair<Int, String>>>(emptyList()) }
    var genres by remember { mutableStateOf<List<Pair<String, List<String>>>>(emptyList()) }
    var levels by remember { mutableStateOf<List<Triple<String, String, String>>>(emptyList()) }
    var genre by remember { mutableStateOf<String?>(null) }
    var sub by remember { mutableStateOf<String?>(null) }
    var level by remember { mutableStateOf("passend") }
    var count by remember { mutableStateOf(30) }
    var job by remember { mutableStateOf<Job?>(null) }
    var err by remember { mutableStateOf<String?>(null) }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        TopBack(back)
        ScreenHeader("Mix erstellen", link?.let { "Rechnet am PC „${it.pcName}“" })
        Column(Modifier.padding(horizontal = 20.dp)) {
            if (link == null) {
                EmptyState(Ico.Monitor, "Kein PC erreichbar", "Mix erstellen rechnet am gekoppelten PC (Tempo, Tonart, ähnliche Künstler). " +
                    "Handy und PC müssen im selben Netz oder VPN sein, und „Netzwerke erkennen“ muss an sein.")
                return@Column
            }
            LaunchedEffect(Unit) {
                runCatching { App.sync.job(link, "genres") }.onSuccess { o ->
                    genres = o["genres"]!!.jsonArray.map { g -> g.jsonObject.str("genre")!! to g.jsonObject["subs"]!!.jsonArray.map { it.jsonPrimitive.content } }
                    levels = o["levels"]!!.jsonArray.map { l -> Triple(l.jsonObject.str("id")!!, l.jsonObject.str("name")!!, l.jsonObject.str("hint")!!) }
                }.onFailure { err = it.message }
            }
            val j = job
            if (j != null) { JobResult(link, "mix", j, defaultName = seeds.firstOrNull()?.second?.let { "Mix: $it" } ?: genre?.let { "Mix: ${sub ?: it}" } ?: "Mix",
                onBack = { job = null }); return@Column }

            Segmented(listOf(false, true), byGenre, { if (it) "Genre" else "Künstler" }) { byGenre = it }
            Spacer(Modifier.height(14.dp))
            if (!byGenre) {
                Text("Bis zu 5 Künstler – der Mix nimmt ähnliche Künstler und deren bekannteste Songs.", style = TbType.small, color = Tb.text3)
                Spacer(Modifier.height(8.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box1(Modifier.weight(1f)) { SearchField(q, { q = it }, placeholder = "Künstler suchen …") }
                    Spacer(Modifier.width(8.dp))
                    TbButton("Suchen", {
                        scope.launch {
                            err = null
                            runCatching { App.sync.job(link, "artists", buildJsonObject { put("q", q) }) }
                                .onSuccess { o -> found = o["artists"]!!.jsonArray.map { a -> a.jsonObject.int("id") to a.jsonObject.str("name")!! } }
                                .onFailure { err = it.message }
                        }
                    }, small = true, enabled = q.trim().length >= 2)
                }
                if (found.isNotEmpty()) FlowRow(Modifier.padding(top = 10.dp), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    found.forEach { a ->
                        val on = seeds.any { it.first == a.first }
                        FilterChip(a.second, on, if (on) Ico.Check else Ico.Plus) {
                            seeds = if (on) seeds.filterNot { it.first == a.first } else (seeds + a).take(5)
                        }
                    }
                }
                if (seeds.isNotEmpty()) {
                    SectionLabel("Ausgewählt", Modifier.padding(top = 14.dp))
                    FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                        seeds.forEach { a -> FilterChip(a.second, true, Ico.X) { seeds = seeds - a } }
                    }
                }
            } else {
                Text("Songs aus einem Genre – aus deiner Bibliothek, der Gemeinschafts-Datenbank und Musik-Datenbanken.", style = TbType.small, color = Tb.text3)
                Spacer(Modifier.height(8.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    MenuChip(genre ?: "Genre wählen", genre != null, genres.map { it.first }) { genre = genres[it].first; sub = null }
                    val subs = genres.firstOrNull { it.first == genre }?.second.orEmpty()
                    if (subs.isNotEmpty()) MenuChip(sub ?: "Alle Subgenres", sub != null, listOf("Alle Subgenres") + subs) { sub = if (it == 0) null else subs[it - 1] }
                }
            }
            SectionLabel("Wie passend?", Modifier.padding(top = 18.dp))
            if (levels.isNotEmpty()) {
                Segmented(levels.map { it.first }, level, { id -> levels.first { it.first == id }.second }) { level = it }
                Text(levels.firstOrNull { it.first == level }?.third.orEmpty(), style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 6.dp))
            }
            SectionLabel("Wie viele Songs?", Modifier.padding(top = 18.dp))
            Segmented(listOf(20, 30, 50, 100), count, { "$it" }) { count = it }
            err?.let { Spacer(Modifier.height(12.dp)); Notice(it, color = Tb.danger) }
            Spacer(Modifier.height(18.dp))
            TbButton("Mix erstellen", {
                err = null
                scope.launch {
                    runCatching {
                        val fields = buildJsonObject {
                            if (byGenre) put("genre", buildJsonObject { put("genre", genre); sub?.let { put("sub", it) } })
                            else put("seeds", JsonArray(seeds.map { buildJsonObject { put("id", it.first); put("name", it.second) } }))
                            put("opts", buildJsonObject { put("level", level); put("count", count) })
                        }
                        val id = App.sync.job(link, "mix-start", fields).str("job")!!
                        job = Job(id)
                        poll(link, "mix", id) { job = it }
                    }.onFailure { err = it.message; job = null }
                }
            }, kind = BtnKind.Primary, icon = Ico.Sparkle, enabled = if (byGenre) genre != null else seeds.isNotEmpty())
            Text("Der PC fragt dafür Deezer (ähnliche Künstler, Top-Songs) und misst bei „Mixbar“/„DJ-genau“ Tempo und Tonart an den " +
                "offiziellen Hörproben – wie am PC selbst.", style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 10.dp, bottom = 28.dp))
        }
    }
}

@Composable
private fun Box1(modifier: Modifier, content: @Composable () -> Unit) = androidx.compose.foundation.layout.Box(modifier) { content() }

// ------------------------------------------------------------------ Set-Planer

@Composable
fun SetPlanScreen(pc: String, name: String, back: () -> Unit) {
    val scope = rememberCoroutineScope()
    val link = remember { App.repo.link(pc)?.takeIf { App.sync.reachable(it).isNotEmpty() && de.bs002.tunebridge.sync.Nets.allowed() } }
    var curve by remember { mutableStateOf("peak") }
    var job by remember { mutableStateOf<Job?>(null) }
    var err by remember { mutableStateOf<String?>(null) }
    val curves = listOf("aufbau" to "Aufbauen", "peak" to "Peak", "gleich" to "Gleich", "runter" to "Runter")
    val hints = mapOf("aufbau" to "ruhig starten, immer mehr Energie", "peak" to "aufbauen, Höhepunkt bei etwa 70 %, sanft ausklingen",
        "gleich" to "Energie egal – nur Tempo und Tonart", "runter" to "mit Energie starten, ruhig enden")
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        TopBack(back)
        ScreenHeader("Set planen", name)
        Column(Modifier.padding(horizontal = 20.dp)) {
            if (link == null) {
                EmptyState(Ico.Monitor, "PC nicht erreichbar", "Der Set-Planer misst Tempo und Tonart am PC, dem diese Playlist gehört. " +
                    "Handy und PC müssen im selben Netz oder VPN sein.")
                return@Column
            }
            val j = job
            if (j != null) { JobResult(link, "set", j, defaultName = "$name (Set)", onBack = { job = null }); return@Column }
            Text("Der PC holt Tempo, Tonart und Energie jedes Songs (aus dem Speicher oder der Hörprobe) und baut eine DJ-taugliche " +
                "Reihenfolge: kleine Tempo-Sprünge, harmonische Übergänge (Camelot), passende Energie-Kurve.", style = TbType.small, color = Tb.text3)
            SectionLabel("Energie-Verlauf", Modifier.padding(top = 18.dp))
            Segmented(curves.map { it.first }, curve, { id -> curves.first { it.first == id }.second }) { curve = it }
            Text(hints[curve].orEmpty(), style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 6.dp))
            err?.let { Spacer(Modifier.height(12.dp)); Notice(it, color = Tb.danger) }
            Spacer(Modifier.height(18.dp))
            TbButton("Set planen", {
                err = null
                scope.launch {
                    runCatching {
                        val id = App.sync.job(link, "set-start", buildJsonObject { put("playlist", name); put("curve", curve) }).str("job")!!
                        job = Job(id, state = "analysing")
                        poll(link, "set", id) { job = it }
                    }.onFailure { err = it.message; job = null }
                }
            }, kind = BtnKind.Primary, icon = Ico.Sparkle)
        }
    }
}

// ------------------------------------------------------------------ Ergebnis (gemeinsam)

@Composable
private fun JobResult(link: Repository.PcLink, kind: String, j: Job, defaultName: String, onBack: () -> Unit) {
    val scope = rememberCoroutineScope()
    var saveName by remember { mutableStateOf(defaultName) }
    var msg by remember { mutableStateOf<String?>(null) }
    var share by remember { mutableStateOf(false) }
    when (j.state) {
        "running", "analysing" -> {
            val label = when {
                kind == "set" -> "Messe Tempo und Tonart … ${j.done} von ${j.total}"
                j.phase == "measuring" -> "Messe Tempo und Tonart … ${j.done} von ${j.total}"
                else -> "Suche passende Künstler und Songs …"
            }
            Text(label, style = TbType.body, color = Tb.text2)
            Spacer(Modifier.height(10.dp))
            if (j.total > 0 && (kind == "set" || j.phase == "measuring"))
                LinearProgressIndicator(progress = { j.done.toFloat() / j.total }, modifier = Modifier.fillMaxWidth(), color = Tb.accent, trackColor = Tb.bg3)
            else LinearProgressIndicator(modifier = Modifier.fillMaxWidth(), color = Tb.accent, trackColor = Tb.bg3)
            Text("Du kannst das Handy weglegen – der PC rechnet weiter. Bleib auf dieser Seite, um das Ergebnis zu sehen.",
                style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 10.dp))
            Spacer(Modifier.height(14.dp))
            TbButton("Abbrechen", {
                scope.launch { runCatching { App.sync.job(link, "cancel", buildJsonObject { put("kind", kind); put("job", j.id) }) }; onBack() }
            }, kind = BtnKind.Ghost, icon = Ico.X)
        }
        "done" -> {
            val list = j.ordered
            if (list.isEmpty()) {
                Notice(j.note.ifBlank { "Nichts gefunden – „Locker“ oder ein anderer Künstler findet mehr." }) {}
                Spacer(Modifier.height(12.dp)); TbButton("Zurück", onBack, kind = BtnKind.Ghost); return
            }
            Text("${list.size} Songs" + (if (j.summary.isNotBlank()) " · ${j.summary}" else ""), style = TbType.bodyStrong, color = Tb.text)
            if (j.note.isNotBlank()) Text(j.note, style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 4.dp))
            Spacer(Modifier.height(12.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                TbButton("Abspielen", { Player.play(list.map { it.track() }, 0, defaultName) }, kind = BtnKind.Primary, icon = Ico.Play, small = true)
                TbButton("Teilen", { share = true }, kind = BtnKind.Ghost, icon = Ico.Share, small = true)
                TbButton("Neu", onBack, kind = BtnKind.Ghost, icon = Ico.Repeat, small = true)
            }
            if (share) ExportSheet(defaultName, list.map { Export.Item(it.track()) }) { share = false }
            SectionLabel("Als Playlist am PC speichern", Modifier.padding(top = 18.dp))
            val shape = RoundedCornerShape(Tb.radiusSm)
            Row(verticalAlignment = Alignment.CenterVertically) {
                BasicTextField(saveName, { saveName = it }, singleLine = true, textStyle = TbType.body.copy(color = Tb.text), cursorBrush = SolidColor(Tb.accent),
                    modifier = Modifier.weight(1f).clip(shape).background(Tb.bg3).border(1.dp, Tb.line, shape).padding(horizontal = 12.dp, vertical = 11.dp))
                Spacer(Modifier.width(8.dp))
                TbButton("Speichern", {
                    scope.launch {
                        runCatching {
                            App.sync.job(link, "save", buildJsonObject {
                                put("kind", kind); put("job", j.id); put("name", saveName.trim())
                                put("idx", JsonArray(j.order.map { JsonPrimitive(it) }))
                            })
                            App.sync.sync(link.pcId)
                        }.onSuccess { msg = "Gespeichert – „${saveName.trim()}“ ist jetzt unter Playlists." }
                            .onFailure { msg = it.message }
                    }
                }, kind = BtnKind.Primary, small = true, enabled = saveName.isNotBlank())
            }
            msg?.let { Text(it, style = TbType.small, color = Tb.text2, modifier = Modifier.padding(top = 8.dp)) }
            Spacer(Modifier.height(14.dp))
            TbCard(Modifier.fillMaxWidth(), padding = 4.dp) {
                list.forEachIndexed { n, it ->
                    Row(Modifier.fillMaxWidth().clickable { Player.play(list.map { x -> x.track() }, n, defaultName) }.padding(horizontal = 10.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically) {
                        Text("${n + 1}", style = TbType.small, color = Tb.text3, modifier = Modifier.width(24.dp))
                        Cover(it.cover, 40.dp)
                        Spacer(Modifier.width(10.dp))
                        TrackLine(it.title, it.artists.joinToString(", "), Modifier.weight(1f))
                        Column(horizontalAlignment = Alignment.End) {
                            it.bpm?.let { b -> Text("${b.toInt()} BPM", style = TbType.small, color = Tb.text3, maxLines = 1, overflow = TextOverflow.Clip) }
                            it.camelot?.let { c -> Text(c, style = TbType.small, color = Tb.accent) }
                        }
                    }
                }
            }
            Spacer(Modifier.height(28.dp))
        }
        else -> {
            Notice(j.error ?: if (j.state == "cancelled") "Abgebrochen." else "Hat nicht geklappt.", color = Tb.danger) {}
            Spacer(Modifier.height(12.dp)); TbButton("Zurück", onBack, kind = BtnKind.Ghost)
        }
    }
}

