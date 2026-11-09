package de.bs002.tunebridge.ui.components

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.RowScope
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import coil.compose.SubcomposeAsyncImage
import coil.request.ImageRequest
import de.bs002.tunebridge.App
import de.bs002.tunebridge.ui.theme.GenreColors
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType

@Composable
fun TbCard(modifier: Modifier = Modifier, padding: Dp = 16.dp, onClick: (() -> Unit)? = null, content: @Composable ColumnScope.() -> Unit) {
    val shape = RoundedCornerShape(Tb.radius)
    Column(
        modifier
            .clip(shape)
            .background(Tb.bg2)
            .border(1.dp, Tb.line, shape)
            .then(if (onClick != null) Modifier.clickable(onClick = onClick) else Modifier)
            .padding(padding),
        content = content,
    )
}

enum class BtnKind { Primary, Ghost, Plain, Danger }

/** Knopf im Stil der Desktop-App: flach, 7er-Radius, leichtes Nachgeben beim Drücken. */
@Composable
fun TbButton(
    text: String,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
    kind: BtnKind = BtnKind.Plain,
    icon: Ico? = null,
    small: Boolean = false,
    enabled: Boolean = true,
) {
    val src = remember { MutableInteractionSource() }
    val pressed by src.collectIsPressedAsState()
    val s by animateFloatAsState(if (pressed) 0.97f else 1f, label = "druck")
    val (bg, fg, border) = when (kind) {
        BtnKind.Primary -> Triple(Tb.accent, Tb.accentInk, Color.Transparent)
        BtnKind.Ghost -> Triple(Color.Transparent, Tb.text2, Color.Transparent)
        BtnKind.Plain -> Triple(Tb.bg3, Tb.text, Tb.line)
        BtnKind.Danger -> Triple(Tb.dangerSoft, Tb.danger, Color.Transparent)
    }
    val shape = RoundedCornerShape(Tb.radiusSm)
    Row(
        modifier
            .scale(s)
            .clip(shape)
            .background(if (enabled) bg else bg.copy(alpha = bg.alpha * 0.4f))
            .border(1.dp, border, shape)
            .clickable(src, null, enabled = enabled, role = Role.Button, onClick = onClick)
            .padding(PaddingValues(horizontal = if (small) 11.dp else 15.dp, vertical = if (small) 7.dp else 11.dp)),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.Center,
    ) {
        val c = if (enabled) fg else fg.copy(alpha = 0.45f)
        if (icon != null) {
            TbIcon(icon, c, if (small) 15.dp else 17.dp)
            Spacer(Modifier.width(if (small) 6.dp else 8.dp))
        }
        Text(text, style = if (small) TbType.small.copy(fontWeight = TbType.button.fontWeight) else TbType.button, color = c, maxLines = 1)
    }
}

@Composable
fun IconBtn(icon: Ico, contentDescription: String, onClick: () -> Unit, tint: Color = Tb.text2, modifier: Modifier = Modifier) {
    Box(
        modifier.size(40.dp).clip(CircleShape).clickable(onClickLabel = contentDescription, role = Role.Button, onClick = onClick),
        contentAlignment = Alignment.Center,
    ) { TbIcon(icon, tint, 20.dp) }
}

@Composable
fun GenreChip(genre: String?, sub: String? = null) {
    val c = GenreColors.of(genre)
    Row(
        Modifier.clip(RoundedCornerShape(50)).background(c.copy(alpha = 0.12f)).padding(horizontal = 9.dp, vertical = 3.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(Modifier.size(6.dp).clip(CircleShape).background(c))
        Spacer(Modifier.width(6.dp))
        Text(sub ?: genre ?: "Genre offen", style = TbType.small, color = if (genre == null) Tb.text3 else Tb.text, maxLines = 1)
    }
}

@Composable
fun Pill(text: String, color: Color = Tb.text2, background: Color = Tb.bg3, icon: Ico? = null) {
    Row(
        Modifier.clip(RoundedCornerShape(50)).background(background).padding(horizontal = 10.dp, vertical = 4.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        if (icon != null) { TbIcon(icon, color, 13.dp); Spacer(Modifier.width(5.dp)) }
        Text(text, style = TbType.small, color = color, maxLines = 1)
    }
}

/** Cover – nur geladen, wenn erlaubt (Einstellungen › Datenschutz). Sonst ein ruhiger Platzhalter. */
@Composable
fun Cover(url: String?, size: Dp, radius: Dp = Tb.radiusSm, modifier: Modifier = Modifier) {
    val allowed = App.repo.settings.value.covers
    val shape = RoundedCornerShape(radius)
    val placeholder = @Composable {
        Box(Modifier.size(size).background(Tb.bg3), contentAlignment = Alignment.Center) {
            TbIcon(Ico.Disc, Tb.text3, size * 0.4f)
        }
    }
    Box(modifier.size(size).clip(shape)) {
        if (url == null || !allowed) placeholder()
        else SubcomposeAsyncImage(
            model = ImageRequest.Builder(LocalContext.current).data(url).crossfade(180).build(),
            contentDescription = null, contentScale = ContentScale.Crop, modifier = Modifier.size(size),
            loading = { placeholder() }, error = { placeholder() },
        )
    }
}

@Composable
fun SectionLabel(text: String, modifier: Modifier = Modifier, trailing: @Composable RowScope.() -> Unit = {}) {
    Row(modifier.fillMaxWidth().padding(top = 22.dp, bottom = 10.dp), verticalAlignment = Alignment.CenterVertically) {
        Text(text.uppercase(), style = TbType.label, color = Tb.text3, modifier = Modifier.weight(1f))
        trailing()
    }
}

@Composable
fun EmptyState(icon: Ico, title: String, text: String, modifier: Modifier = Modifier, action: @Composable () -> Unit = {}) {
    Column(modifier.fillMaxWidth().padding(horizontal = 32.dp, vertical = 48.dp), horizontalAlignment = Alignment.CenterHorizontally) {
        Box(Modifier.size(52.dp).clip(CircleShape).background(Tb.bg3), contentAlignment = Alignment.Center) { TbIcon(icon, Tb.text3, 24.dp) }
        Spacer(Modifier.height(16.dp))
        Text(title, style = TbType.heading, color = Tb.text)
        Spacer(Modifier.height(6.dp))
        Text(text, style = TbType.body, color = Tb.text3, modifier = Modifier.widthIn(max = 320.dp),
            textAlign = androidx.compose.ui.text.style.TextAlign.Center)
        Spacer(Modifier.height(18.dp))
        action()
    }
}

@Composable
fun SettingRow(title: String, text: String? = null, checked: Boolean, onChange: (Boolean) -> Unit) {
    val c by animateColorAsState(if (checked) Tb.text else Tb.text2, label = "farbe")
    Row(
        Modifier.fillMaxWidth().clickable(role = Role.Switch) { onChange(!checked) }.padding(vertical = 12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(Modifier.weight(1f).padding(end = 12.dp)) {
            Text(title, style = TbType.bodyStrong, color = c)
            if (text != null) Text(text, style = TbType.small, color = Tb.text3, modifier = Modifier.padding(top = 2.dp))
        }
        Switch(
            checked = checked, onCheckedChange = onChange,
            colors = SwitchDefaults.colors(
                checkedThumbColor = Tb.accentInk, checkedTrackColor = Tb.accent, checkedBorderColor = Tb.accent,
                uncheckedThumbColor = Tb.text3, uncheckedTrackColor = Tb.bg3, uncheckedBorderColor = Tb.lineStrong,
            ),
        )
    }
}

@Composable
fun Hairline(modifier: Modifier = Modifier) = Box(modifier.fillMaxWidth().height(1.dp).background(Tb.lineSoft))

@Composable
fun TrackLine(title: String, sub: String, modifier: Modifier = Modifier) {
    Column(modifier) {
        Text(title, style = TbType.bodyStrong, color = Tb.text, maxLines = 1, overflow = TextOverflow.Ellipsis)
        Text(sub, style = TbType.small, color = Tb.text2, maxLines = 1, overflow = TextOverflow.Ellipsis)
    }
}

@Composable
fun Notice(text: String, icon: Ico = Ico.Info, color: Color = Tb.warn, modifier: Modifier = Modifier, content: @Composable ColumnScope.() -> Unit = {}) {
    val shape = RoundedCornerShape(Tb.radius)
    Row(
        modifier.fillMaxWidth().clip(shape).background(color.copy(alpha = 0.07f)).border(1.dp, color.copy(alpha = 0.16f), shape).padding(14.dp),
    ) {
        TbIcon(icon, color, 18.dp, Modifier.padding(top = 1.dp))
        Spacer(Modifier.width(12.dp))
        Column(Modifier.weight(1f)) {
            Text(text, style = TbType.body, color = Tb.text2)
            content()
        }
    }
}
