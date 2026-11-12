package de.bs002.tunebridge.ui.theme

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Dieselben Linien-Symbole wie in der Desktop-App (ICONS in app.js, 24er-Raster, Strich 1,8).
 * Bewusst keine Material-Icons: beide Apps sollen gleich aussehen.
 */
enum class Ico(val paths: List<String>, val circles: List<Triple<Float, Float, Float>> = emptyList(),
               val rects: List<FloatArray> = emptyList(), val filled: Boolean = false) {
    Wave(listOf("M3 10v4", "M7 6v12", "M11 3v18", "M15 8v8", "M19 5v14")),
    Clock(listOf("M12 7v5l3 2"), listOf(Triple(12f, 12f, 9f))),
    Stack(listOf("M21 15V6", "M18.5 18a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5Z", "M12 12H3", "M16 6H3", "M12 18H3")),
    Sliders(listOf("M4 21v-7", "M4 10V3", "M12 21v-9", "M12 8V3", "M20 21v-5", "M20 12V3", "M2 14h4", "M10 8h4", "M18 16h4")),
    Play(listOf("M7 4.6v14.8a1 1 0 0 0 1.52.85l12-7.4a1 1 0 0 0 0-1.7l-12-7.4A1 1 0 0 0 7 4.6Z"), filled = true),
    Pause(emptyList(), rects = listOf(floatArrayOf(6f, 4f, 4f, 16f, 1.2f), floatArrayOf(14f, 4f, 4f, 16f, 1.2f)), filled = true),
    Plus(listOf("M12 5v14", "M5 12h14")),
    Check(listOf("M20 6 9 17l-5-5")),
    X(listOf("M18 6 6 18", "m6 6 12 12")),
    Shuffle(listOf("M2 18h1.4c1.3 0 2.5-.6 3.3-1.7l6.1-8.6c.7-1.1 2-1.7 3.3-1.7H22", "m18 2 4 4-4 4",
        "M2 6h1.9c1.5 0 2.9.9 3.6 2.2", "M22 18h-5.9c-1.3 0-2.6-.7-3.3-1.8l-.5-.8", "m18 14 4 4-4 4")),
    Next(listOf("M5 5.2v13.6a1 1 0 0 0 1.5.86l10-6.8a1 1 0 0 0 0-1.72l-10-6.8A1 1 0 0 0 5 5.2Z"),
        rects = listOf(floatArrayOf(17f, 4f, 2.4f, 16f, 1f)), filled = true),
    Prev(listOf("M19 5.2v13.6a1 1 0 0 1-1.5.86l-10-6.8a1 1 0 0 1 0-1.72l10-6.8A1 1 0 0 1 19 5.2Z"),
        rects = listOf(floatArrayOf(4.6f, 4f, 2.4f, 16f, 1f)), filled = true),
    Heart(listOf("M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z")),
    HeartFill(listOf("M19 14c1.49-1.46 3-3.21 3-5.5A5.5 5.5 0 0 0 16.5 3c-1.76 0-3 .5-4.5 2-1.5-1.5-2.74-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.3 1.5 4.05 3 5.5l7 7Z"), filled = true),
    Chart(listOf("M3 3v18h18", "M8 17v-5", "M13 17V7", "M18 17v-8")),
    Trash(listOf("M3 6h18", "M8 6V4.5A1.5 1.5 0 0 1 9.5 3h5A1.5 1.5 0 0 1 16 4.5V6", "m19 6-.8 13.2a2 2 0 0 1-2 1.8H7.8a2 2 0 0 1-2-1.8L5 6")),
    External(listOf("M15 3h6v6", "M10 14 21 3", "M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6")),
    Search(listOf("m20 20-3.5-3.5"), listOf(Triple(11f, 11f, 7f))),
    Mic(listOf("M19 10v1a7 7 0 0 1-14 0v-1", "M12 18v4"), rects = listOf(floatArrayOf(9f, 2f, 6f, 12f, 3f))),
    Disc(emptyList(), listOf(Triple(12f, 12f, 9f), Triple(12f, 12f, 2.5f))),
    Info(listOf("M12 8v4", "M12 16h.01"), listOf(Triple(12f, 12f, 9f))),
    Arrow(listOf("M5 12h14", "m13 6 6 6-6 6")),
    Back(listOf("M19 12H5", "m11 18-6-6 6-6")),
    Chevron(listOf("m9 6 6 6-6 6")),
    Repeat(listOf("m17 2 4 4-4 4", "M3 11v-1a4 4 0 0 1 4-4h14", "m7 22-4-4 4-4", "M21 13v1a4 4 0 0 1-4 4H3")),
    Share(listOf("M18 8a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z", "M6 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z", "M18 22a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z", "m8.6 13.5 6.8 4", "m15.4 6.5-6.8 4")),
    Key(listOf("m10.8 12.2 9.2-9.2", "m17 6 3 3", "m14 9 2 2"), listOf(Triple(8f, 15f, 4f))),
    Sparkle(listOf("M12 3v4", "M12 17v4", "M3 12h4", "M17 12h4", "m6 6 2 2", "m16 16 2 2", "m6 18 2-2", "m16 8 2-2")),
    Monitor(listOf("M8 21h8", "M12 17v4"), rects = listOf(floatArrayOf(3f, 4f, 18f, 13f, 2f))),
    Shield(listOf("M12 3 4.5 6v5.5c0 4.6 3.2 8.4 7.5 9.5 4.3-1.1 7.5-4.9 7.5-9.5V6Z", "m9 12 2 2 4-4")),
    Qr(listOf("M14 14h3v3h-3z", "M20 14v1", "M14 20h1", "M18 18h3v3", "M17 21h1"),
        rects = listOf(floatArrayOf(3f, 3f, 7f, 7f, 1.2f), floatArrayOf(14f, 3f, 7f, 7f, 1.2f), floatArrayOf(3f, 14f, 7f, 7f, 1.2f))),
    Sync(listOf("M21 12a9 9 0 0 1-15.5 6.2L3 16", "M3 12a9 9 0 0 1 15.5-6.2L21 8", "M21 3v5h-5", "M3 21v-5h5")),
    More(emptyList(), listOf(Triple(12f, 5f, 0.9f), Triple(12f, 12f, 0.9f), Triple(12f, 19f, 0.9f))),
    Phone(listOf("M11 18h2"), rects = listOf(floatArrayOf(6f, 2f, 12f, 20f, 2.5f))),
    Edit(listOf("M12 20h9", "M16.4 3.6a2.1 2.1 0 1 1 3 3L7 19l-4 1 1-4Z")),
    Download(listOf("M12 3v12", "m7 10 5 5 5-5", "M5 21h14")),
    Upload(listOf("M12 21V9", "m7 14 5-5 5 5", "M5 3h14")),
    Select(listOf("m9 11 3 3L22 4", "M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11")),
}

@Composable
fun TbIcon(icon: Ico, tint: Color = Tb.text2, size: Dp = 20.dp, modifier: Modifier = Modifier) {
    val paths = remember(icon) { icon.paths.map { PathParser().parsePathString(it).toPath() } }
    Canvas(modifier.size(size)) {
        val k = this.size.minDimension / 24f
        scale(k, k, pivot = Offset.Zero) {
            val style = if (icon.filled) Fill else Stroke(width = 1.8f, cap = StrokeCap.Round, join = StrokeJoin.Round)
            paths.forEach { drawPath(it, tint, style = style) }
            icon.circles.forEach { (cx, cy, r) -> drawCircle(tint, r, Offset(cx, cy), style = Stroke(1.8f)) }
            icon.rects.forEach { r ->
                drawRoundRect(tint, Offset(r[0], r[1]), Size(r[2], r[3]), CornerRadius(r[4], r[4]), style = style)
            }
        }
    }
}
