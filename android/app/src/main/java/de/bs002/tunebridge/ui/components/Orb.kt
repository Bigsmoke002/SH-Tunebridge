package de.bs002.tunebridge.ui.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.lerp
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.unit.dp
import de.bs002.tunebridge.ui.theme.Tb
import kotlin.math.PI
import kotlin.math.sin

enum class OrbMode { Idle, Live, Thinking }

/**
 * Der Erkennen-Knopf – wie am Desktop: Ring mit Fortschritt, darin ein ruhiger Kreis.
 * Beim Zuhören zeigt er das echte Spektrum des Mikrofons, beim Auswerten ein langsames Pulsieren.
 */
@Composable
fun Orb(mode: OrbMode, progress: Float, bands: FloatArray, onClick: () -> Unit, modifier: Modifier = Modifier) {
    val src = remember { MutableInteractionSource() }
    val pressed by src.collectIsPressedAsState()
    val scale by animateFloatAsState(if (pressed) 0.975f else 1f, label = "druck")
    val shown by animateFloatAsState(progress, tween(220), label = "ring")
    val pulse = rememberInfiniteTransition(label = "puls")
    val t by pulse.animateFloat(0f, 1f, infiniteRepeatable(tween(1800, easing = FastOutSlowInEasing), RepeatMode.Restart), label = "t")
    val glow by animateFloatAsState(if (mode == OrbMode.Idle) 0f else 1f, tween(400), label = "glow")

    Box(modifier.size(248.dp).scale(scale), contentAlignment = Alignment.Center) {
        Canvas(Modifier.size(248.dp)) {
            val stroke = 3.dp.toPx()
            val r = size.minDimension / 2 - stroke
            // sanfter Schein, solange etwas passiert
            if (glow > 0f) drawCircle(
                Brush.radialGradient(listOf(Tb.accent.copy(alpha = 0.10f * glow), Tb.accent.copy(alpha = 0f)), center, r * 1.02f),
                r * 1.02f,
            )
            drawCircle(Tb.bg4, r, style = Stroke(stroke))
            if (shown > 0f) drawArc(
                Tb.accent, -90f, 360f * shown, false, Offset(center.x - r, center.y - r), Size(r * 2, r * 2),
                style = Stroke(stroke, cap = StrokeCap.Round),
            )
        }
        Box(
            Modifier.size(186.dp).clip(CircleShape)
                .clickable(src, null, role = Role.Button, onClickLabel = "Song erkennen", onClick = onClick),
            contentAlignment = Alignment.Center,
        ) {
            Canvas(Modifier.size(186.dp)) {
                val r = size.minDimension / 2
                drawCircle(
                    Brush.radialGradient(
                        listOf(lerp(Tb.bg3, Tb.accent, 0.10f), Tb.bg1), Offset(center.x, center.y - r * 0.3f), r * 1.15f,
                    ), r,
                )
                drawCircle(Tb.accent.copy(alpha = 0.18f + 0.12f * glow), r - 0.5.dp.toPx(), style = Stroke(1.dp.toPx()))
                when (mode) {
                    OrbMode.Live -> bars(bands.size) { i -> bands[i] }
                    OrbMode.Thinking -> bars(5) { i -> 0.35f + 0.55f * ((sin((t + i * 0.17f) * 2 * PI).toFloat() + 1f) / 2f) }
                    OrbMode.Idle -> bars(5) { i -> floatArrayOf(0.28f, 0.6f, 0.92f, 0.5f, 0.32f)[i] }
                }
            }
        }
    }
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.bars(n: Int, height: (Int) -> Float) {
    val maxH = size.height * 0.30f
    val w = if (n > 8) 3.2.dp.toPx() else 5.dp.toPx()
    val gap = if (n > 8) 2.6.dp.toPx() else 5.dp.toPx()
    val total = n * w + (n - 1) * gap
    var x = center.x - total / 2
    for (i in 0 until n) {
        val h = (height(i).coerceIn(0.06f, 1f)) * maxH
        drawRoundRect(Tb.accent, Offset(x, center.y - h / 2), Size(w, h), CornerRadius(w / 2, w / 2))
        x += w + gap
    }
}
