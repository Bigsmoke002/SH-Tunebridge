package de.bs002.tunebridge.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Typography
import androidx.compose.material3.darkColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.em
import androidx.compose.ui.unit.sp
import de.bs002.tunebridge.R

/** Farben 1:1 aus der Desktop-App (app.css :root) – ruhiges Graphit-Dunkel, ein Akzent (Mint). */
object Tb {
    val bg0 = Color(0xFF0E1013)
    val bg1 = Color(0xFF12151A)
    val bg2 = Color(0xFF171A20)
    val bg3 = Color(0xFF1D2128)
    val bg4 = Color(0xFF252A32)
    val line = Color(0xFF232830)
    val lineSoft = Color(0xFF1B1F26)
    val lineStrong = Color(0xFF353B45)
    val text = Color(0xFFE4E6EA)
    val text2 = Color(0xFFA2A8B2)
    val text3 = Color(0xFF6B717C)
    val accent = Color(0xFF6CC8A8)
    val accentSoft = Color(0x1F6CC8A8)
    val accentInk = Color(0xFF0D1A15)
    val warn = Color(0xFFE0B46A)
    val danger = Color(0xFFE2786E)
    val dangerSoft = Color(0x1FE2786E)

    val radius = 10.dp
    val radiusSm = 7.dp
}

val Inter = FontFamily(
    Font(R.font.inter_regular, FontWeight.Normal),
    Font(R.font.inter_medium, FontWeight.Medium),
    Font(R.font.inter_semibold, FontWeight.SemiBold),
    Font(R.font.inter_bold, FontWeight.Bold),
)

object TbType {
    val display = TextStyle(fontFamily = Inter, fontWeight = FontWeight.SemiBold, fontSize = 26.sp, lineHeight = 32.sp, letterSpacing = (-0.02).em)
    val title = TextStyle(fontFamily = Inter, fontWeight = FontWeight.SemiBold, fontSize = 20.sp, lineHeight = 26.sp, letterSpacing = (-0.015).em)
    val heading = TextStyle(fontFamily = Inter, fontWeight = FontWeight.SemiBold, fontSize = 16.sp, lineHeight = 22.sp, letterSpacing = (-0.01).em)
    val body = TextStyle(fontFamily = Inter, fontWeight = FontWeight.Normal, fontSize = 14.sp, lineHeight = 20.sp)
    val bodyStrong = body.copy(fontWeight = FontWeight.Medium)
    val small = TextStyle(fontFamily = Inter, fontWeight = FontWeight.Normal, fontSize = 12.5.sp, lineHeight = 17.sp)
    val label = TextStyle(fontFamily = Inter, fontWeight = FontWeight.SemiBold, fontSize = 11.5.sp, lineHeight = 14.sp, letterSpacing = 0.02.em)
    val button = TextStyle(fontFamily = Inter, fontWeight = FontWeight.Medium, fontSize = 13.5.sp, lineHeight = 18.sp)
}

private val scheme = darkColorScheme(
    primary = Tb.accent, onPrimary = Tb.accentInk,
    secondary = Tb.accent, onSecondary = Tb.accentInk,
    background = Tb.bg0, onBackground = Tb.text,
    surface = Tb.bg1, onSurface = Tb.text,
    surfaceVariant = Tb.bg3, onSurfaceVariant = Tb.text2,
    surfaceContainer = Tb.bg2, surfaceContainerHigh = Tb.bg3, surfaceContainerHighest = Tb.bg4,
    surfaceContainerLow = Tb.bg1, surfaceContainerLowest = Tb.bg0,
    outline = Tb.lineStrong, outlineVariant = Tb.line,
    error = Tb.danger, onError = Tb.bg0,
)

@Composable
fun TbTheme(content: @Composable () -> Unit) {
    @Suppress("UNUSED_VARIABLE") val dark = isSystemInDarkTheme()   // App ist bewusst immer dunkel (wie am Desktop)
    MaterialTheme(
        colorScheme = scheme,
        typography = Typography(
            bodyLarge = TbType.body, bodyMedium = TbType.body, bodySmall = TbType.small,
            titleLarge = TbType.title, titleMedium = TbType.heading, titleSmall = TbType.bodyStrong,
            labelLarge = TbType.button, labelMedium = TbType.label, labelSmall = TbType.label,
            headlineSmall = TbType.display,
        ),
        content = content,
    )
}

/** Genre-Farben wie am Desktop (GENRE_COLORS), unbekannte Genres bekommen einen festen, gedämpften Farbton. */
object GenreColors {
    private val map = mapOf(
        "Drum & Bass" to 0xFFD9A65E, "Dubstep" to 0xFFA495EF, "House" to 0xFF5FBCCB, "Techno" to 0xFF91A2BB,
        "UK Garage / Bass" to 0xFFDF93AE, "Trance" to 0xFF7AA9EA, "Hardstyle / Hardcore" to 0xFFE3826F,
        "Trap / Future Bass" to 0xFFE6C56D, "Breakbeat" to 0xFF9EC97B, "Hip-Hop" to 0xFFCFB18C, "Pop" to 0xFFE99ACB,
        "Rock / Metal" to 0xFFC97676, "Ambient / Chill" to 0xFF86CDD3, "Breakcore" to 0xFFE07AB8, "Phonk" to 0xFFB07DE0,
        "Hyperpop" to 0xFFF08FD9, "Synthwave" to 0xFFD47CF0, "IDM / Experimental" to 0xFFA8B46F, "R&B / Soul" to 0xFFD99A7A,
        "Indie / Alternative" to 0xFF9BB7A0, "Latin" to 0xFFEFA25F, "Reggae / Dancehall" to 0xFF7FC27A, "Jazz / Funk" to 0xFFC9A86A,
        "Country / Folk" to 0xFFB9A079, "Classical / Cinematic" to 0xFFA7B8D8, "Electronic" to 0xFF8FA3B3,
    )

    fun of(genre: String?): Color {
        if (genre.isNullOrBlank()) return Tb.text3
        map[genre]?.let { return Color(it) }
        var h = 0
        for (ch in genre) h = (h * 31 + ch.code) and 0x7fffffff
        return Color.hsl((h % 360).toFloat(), 0.35f, 0.62f)
    }
}
