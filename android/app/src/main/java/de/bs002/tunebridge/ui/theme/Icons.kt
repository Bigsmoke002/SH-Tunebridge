package de.bs002.tunebridge.ui.theme

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.remember
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathFillType
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.StrokeJoin
import androidx.compose.ui.graphics.drawscope.Fill
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.scale
import androidx.compose.ui.graphics.vector.PathParser
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp

/**
 * Dieselben Glyph-Symbole wie in der Desktop-App – beide werden aus scripts/gen-icons.py erzeugt (eine Quelle).
 * fill: gefüllte Flächen (gerade/ungerade-Regel, innere Teilpfade sind Löcher), stroke: kräftige Linien.
 * Eigene Zeichnungen, keine Material-Icons und keine Logos von Diensten.
 */
// ICONS:BEGIN – erzeugt von scripts/gen-icons.py, nicht von Hand ändern
enum class Ico(val fill: List<String>, val stroke: List<String>) {
    Wave(listOf("M4 9.5h0a1.3 1.3 0 0 1 1.3 1.3v2.4a1.3 1.3 0 0 1 -1.3 1.3h0a1.3 1.3 0 0 1 -1.3 -1.3v-2.4a1.3 1.3 0 0 1 1.3 -1.3ZM8 6.5h0a1.3 1.3 0 0 1 1.3 1.3v8.4a1.3 1.3 0 0 1 -1.3 1.3h0a1.3 1.3 0 0 1 -1.3 -1.3v-8.4a1.3 1.3 0 0 1 1.3 -1.3ZM12 3.5h0a1.3 1.3 0 0 1 1.3 1.3v14.4a1.3 1.3 0 0 1 -1.3 1.3h0a1.3 1.3 0 0 1 -1.3 -1.3v-14.4a1.3 1.3 0 0 1 1.3 -1.3ZM16 7.5h0a1.3 1.3 0 0 1 1.3 1.3v6.4a1.3 1.3 0 0 1 -1.3 1.3h0a1.3 1.3 0 0 1 -1.3 -1.3v-6.4a1.3 1.3 0 0 1 1.3 -1.3ZM20 9.5h0a1.3 1.3 0 0 1 1.3 1.3v2.4a1.3 1.3 0 0 1 -1.3 1.3h0a1.3 1.3 0 0 1 -1.3 -1.3v-2.4a1.3 1.3 0 0 1 1.3 -1.3Z"),
        emptyList()),
    Clock(listOf("M2.5 12a9.5 9.5 0 1 0 19 0a9.5 9.5 0 1 0 -19 0ZM11 7.5a1 1 0 0 1 2 0v3.97l2.55 1.7a1 1 0 1 1-1.1 1.66l-3-2A1 1 0 0 1 11 12Z"),
        emptyList()),
    Stack(listOf("M4.2 5h9.6a1.2 1.2 0 0 1 1.2 1.2v0a1.2 1.2 0 0 1 -1.2 1.2h-9.6a1.2 1.2 0 0 1 -1.2 -1.2v0a1.2 1.2 0 0 1 1.2 -1.2ZM4.2 10h9.6a1.2 1.2 0 0 1 1.2 1.2v0a1.2 1.2 0 0 1 -1.2 1.2h-9.6a1.2 1.2 0 0 1 -1.2 -1.2v0a1.2 1.2 0 0 1 1.2 -1.2ZM4.2 15h5.1a1.2 1.2 0 0 1 1.2 1.2v0a1.2 1.2 0 0 1 -1.2 1.2h-5.1a1.2 1.2 0 0 1 -1.2 -1.2v0a1.2 1.2 0 0 1 1.2 -1.2Z", "M13.8 17.4a3 3 0 1 0 6 0a3 3 0 1 0 -6 0Z", "M18.7 5h0a1.1 1.1 0 0 1 1.1 1.1v10.3a1.1 1.1 0 0 1 -1.1 1.1h0a1.1 1.1 0 0 1 -1.1 -1.1v-10.3a1.1 1.1 0 0 1 1.1 -1.1Z"),
        emptyList()),
    Sliders(listOf("M11.5 7a3 3 0 1 0 6 0a3 3 0 1 0 -6 0Z", "M6.5 17a3 3 0 1 0 6 0a3 3 0 1 0 -6 0Z"),
        listOf("M4 7h7", "M18 7h2", "M4 17h2", "M13 17h7")),
    Play(listOf("M7.5 5.6v12.8a1.3 1.3 0 0 0 2 1.1l10.2-6.4a1.3 1.3 0 0 0 0-2.2L9.5 4.5a1.3 1.3 0 0 0-2 1.1Z"),
        emptyList()),
    Pause(listOf("M7.4 4h1.4a1.4 1.4 0 0 1 1.4 1.4v13.2a1.4 1.4 0 0 1 -1.4 1.4h-1.4a1.4 1.4 0 0 1 -1.4 -1.4v-13.2a1.4 1.4 0 0 1 1.4 -1.4ZM15.2 4h1.4a1.4 1.4 0 0 1 1.4 1.4v13.2a1.4 1.4 0 0 1 -1.4 1.4h-1.4a1.4 1.4 0 0 1 -1.4 -1.4v-13.2a1.4 1.4 0 0 1 1.4 -1.4Z"),
        emptyList()),
    Plus(listOf("M2.5 12a9.5 9.5 0 1 0 19 0a9.5 9.5 0 1 0 -19 0ZM11 7.5h2v3.5h3.5v2H13v3.5h-2V13H7.5v-2H11Z"),
        emptyList()),
    Check(emptyList(),
        listOf("M20 6 9 17l-5-5")),
    X(emptyList(),
        listOf("M18 6 6 18", "m6 6 12 12")),
    Shuffle(emptyList(),
        listOf("m18 14 3.5 3.5L18 21", "m18 3 3.5 3.5L18 10", "M2.5 17.5h1.4a4 4 0 0 0 3.3-1.7l6.1-8.6a4 4 0 0 1 3.3-1.7h4.9", "M2.5 6.5h1.4a4 4 0 0 1 3.1 1.5", "M21.5 17.5h-4.9a4 4 0 0 1-3.1-1.5")),
    Next(listOf("M18.2 5h0a1.2 1.2 0 0 1 1.2 1.2v11.6a1.2 1.2 0 0 1 -1.2 1.2h0a1.2 1.2 0 0 1 -1.2 -1.2v-11.6a1.2 1.2 0 0 1 1.2 -1.2Z", "M5 6.2v11.6a1 1 0 0 0 1.55.83l8.6-5.8a1 1 0 0 0 0-1.66l-8.6-5.8A1 1 0 0 0 5 6.2Z"),
        emptyList()),
    Prev(listOf("M5.8 5h0a1.2 1.2 0 0 1 1.2 1.2v11.6a1.2 1.2 0 0 1 -1.2 1.2h0a1.2 1.2 0 0 1 -1.2 -1.2v-11.6a1.2 1.2 0 0 1 1.2 -1.2Z", "M19 6.2v11.6a1 1 0 0 1-1.55.83l-8.6-5.8a1 1 0 0 1 0-1.66l8.6-5.8A1 1 0 0 1 19 6.2Z"),
        emptyList()),
    Heart(emptyList(),
        listOf("M19.2 13.9c1.5-1.5 2.8-3.2 2.8-5.4A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.2 1.3 3.9 2.8 5.4l6.5 6.5a1 1 0 0 0 1.4 0Z")),
    HeartFill(listOf("M19.2 13.9c1.5-1.5 2.8-3.2 2.8-5.4A5.5 5.5 0 0 0 16.5 3c-1.8 0-3 .5-4.5 2-1.5-1.5-2.7-2-4.5-2A5.5 5.5 0 0 0 2 8.5c0 2.2 1.3 3.9 2.8 5.4l6.5 6.5a1 1 0 0 0 1.4 0Z"),
        emptyList()),
    Chart(listOf("M4.8 11h0.8a1.3 1.3 0 0 1 1.3 1.3v6.9a1.3 1.3 0 0 1 -1.3 1.3h-0.8a1.3 1.3 0 0 1 -1.3 -1.3v-6.9a1.3 1.3 0 0 1 1.3 -1.3ZM11.6 3.5h0.8a1.3 1.3 0 0 1 1.3 1.3v14.4a1.3 1.3 0 0 1 -1.3 1.3h-0.8a1.3 1.3 0 0 1 -1.3 -1.3v-14.4a1.3 1.3 0 0 1 1.3 -1.3ZM18.4 7.5h0.8a1.3 1.3 0 0 1 1.3 1.3v10.4a1.3 1.3 0 0 1 -1.3 1.3h-0.8a1.3 1.3 0 0 1 -1.3 -1.3v-10.4a1.3 1.3 0 0 1 1.3 -1.3Z"),
        emptyList()),
    Trash(listOf("M4.2 4.6h15.6a1.2 1.2 0 0 1 1.2 1.2v0a1.2 1.2 0 0 1 -1.2 1.2h-15.6a1.2 1.2 0 0 1 -1.2 -1.2v0a1.2 1.2 0 0 1 1.2 -1.2Z", "M9 4.8V3.8A1.3 1.3 0 0 1 10.3 2.5h3.4A1.3 1.3 0 0 1 15 3.8v1Z", "M5.2 8.2h13.6l-.83 11.4a2 2 0 0 1-2 1.86H8.03a2 2 0 0 1-2-1.86ZM10.8 17.5L10.74 17.81L10.57 18.07L10.31 18.24L10 18.3L9.69 18.24L9.43 18.07L9.26 17.81L9.2 17.5L9.2 11L9.26 10.69L9.43 10.43L9.69 10.26L10 10.2L10.31 10.26L10.57 10.43L10.74 10.69L10.8 11ZM14.8 17.5L14.74 17.81L14.57 18.07L14.31 18.24L14 18.3L13.69 18.24L13.43 18.07L13.26 17.81L13.2 17.5L13.2 11L13.26 10.69L13.43 10.43L13.69 10.26L14 10.2L14.31 10.26L14.57 10.43L14.74 10.69L14.8 11Z"),
        emptyList()),
    External(listOf("M14.5 2.5h6a1 1 0 0 1 1 1v6a.8.8 0 0 1-1.37.57L13.93 3.87A.8.8 0 0 1 14.5 2.5Z"),
        listOf("M18.5 5.5 11 13", "M11 4.5H6.3A3.3 3.3 0 0 0 3 7.8v9.9A3.3 3.3 0 0 0 6.3 21h9.9a3.3 3.3 0 0 0 3.3-3.3V13")),
    Search(emptyList(),
        listOf("M4.2 10.8a6.6 6.6 0 1 0 13.2 0a6.6 6.6 0 1 0 -13.2 0Z", "m15.8 15.8 4.7 4.7")),
    Mic(listOf("M12 2h0a3.5 3.5 0 0 1 3.5 3.5v5.5a3.5 3.5 0 0 1 -3.5 3.5h0a3.5 3.5 0 0 1 -3.5 -3.5v-5.5a3.5 3.5 0 0 1 3.5 -3.5Z"),
        listOf("M19 10.5a7 7 0 0 1-14 0", "M12 17.5v4")),
    Disc(listOf("M2.5 12a9.5 9.5 0 1 0 19 0a9.5 9.5 0 1 0 -19 0ZM9.4 12a2.6 2.6 0 1 0 5.2 0a2.6 2.6 0 1 0 -5.2 0Z"),
        emptyList()),
    Compass(listOf("M2.5 12a9.5 9.5 0 1 0 19 0a9.5 9.5 0 1 0 -19 0ZM15.6 8.4l-2.1 5.1-5.1 2.1 2.1-5.1Z"),
        emptyList()),
    Info(listOf("M2.5 12a9.5 9.5 0 1 0 19 0a9.5 9.5 0 1 0 -19 0ZM13 16.5L12.92 16.88L12.71 17.21L12.38 17.42L12 17.5L11.62 17.42L11.29 17.21L11.08 16.88L11 16.5L11 11L11.08 10.62L11.29 10.29L11.62 10.08L12 10L12.38 10.08L12.71 10.29L12.92 10.62L13 11ZM10.7 7.6a1.3 1.3 0 1 0 2.6 0a1.3 1.3 0 1 0 -2.6 0Z"),
        emptyList()),
    Arrow(emptyList(),
        listOf("M5 12h14", "m13 6 6 6-6 6")),
    Back(emptyList(),
        listOf("M19 12H5", "m11 18-6-6 6-6")),
    Chevron(emptyList(),
        listOf("m9 6 6 6-6 6")),
    Repeat(emptyList(),
        listOf("m17 2.5 3.5 3.5L17 9.5", "M3.5 11v-1a4 4 0 0 1 4-4h13", "m7 21.5-3.5-3.5L7 14.5", "M20.5 13v1a4 4 0 0 1-4 4h-13")),
    Share(listOf("M15 5.5a3 3 0 1 0 6 0a3 3 0 1 0 -6 0ZM3 12a3 3 0 1 0 6 0a3 3 0 1 0 -6 0ZM15 18.5a3 3 0 1 0 6 0a3 3 0 1 0 -6 0Z"),
        listOf("m8.6 10.6 6.8-3.7", "m8.6 13.4 6.8 3.7")),
    Key(listOf("M3 15.5a5 5 0 1 0 10 0a5 5 0 1 0 -10 0ZM6.2 15.5a1.8 1.8 0 1 0 3.6 0a1.8 1.8 0 1 0 -3.6 0Z"),
        listOf("m11.6 11.9 8.4-8.4", "m17 6.5 3 3", "m14.3 9.2 2 2")),
    Sparkle(listOf("M10.5 3c.6 5 2.5 7 7.5 7.5-5 .5-6.9 2.5-7.5 7.5-.6-5-2.5-7-7.5-7.5 5-.5 6.9-2.5 7.5-7.5Z", "M18.5 14c.3 2.1 1.2 3.1 3.5 3.5-2.3.4-3.2 1.4-3.5 3.5-.3-2.1-1.2-3.1-3.5-3.5 2.3-.4 3.2-1.4 3.5-3.5Z"),
        emptyList()),
    Monitor(listOf("M4.5 3h15a2.5 2.5 0 0 1 2.5 2.5v8.5a2.5 2.5 0 0 1 -2.5 2.5h-15a2.5 2.5 0 0 1 -2.5 -2.5v-8.5a2.5 2.5 0 0 1 2.5 -2.5Z", "M8.6 19h6.8a1.1 1.1 0 0 1 1.1 1.1v0a1.1 1.1 0 0 1 -1.1 1.1h-6.8a1.1 1.1 0 0 1 -1.1 -1.1v0a1.1 1.1 0 0 1 1.1 -1.1Z", "M10.9 15h2.2a0 0 0 0 1 0 0v5a0 0 0 0 1 0 0h-2.2a0 0 0 0 1 0 0v-5a0 0 0 0 1 0 0Z"),
        emptyList()),
    Shield(listOf("M12 2.5 4 5.7v5.8c0 4.9 3.4 8.9 8 10 4.6-1.1 8-5.1 8-10V5.7ZM8.1 12.4l1.4-1.4 1.8 1.8 3.9-3.9 1.4 1.4-5.3 5.3Z"),
        emptyList()),
    Qr(listOf("M4.6 3h4.3a1.6 1.6 0 0 1 1.6 1.6v4.3a1.6 1.6 0 0 1 -1.6 1.6h-4.3a1.6 1.6 0 0 1 -1.6 -1.6v-4.3a1.6 1.6 0 0 1 1.6 -1.6ZM5.8 5.3h1.9a0.5 0.5 0 0 1 0.5 0.5v1.9a0.5 0.5 0 0 1 -0.5 0.5h-1.9a0.5 0.5 0 0 1 -0.5 -0.5v-1.9a0.5 0.5 0 0 1 0.5 -0.5Z", "M15.1 3h4.3a1.6 1.6 0 0 1 1.6 1.6v4.3a1.6 1.6 0 0 1 -1.6 1.6h-4.3a1.6 1.6 0 0 1 -1.6 -1.6v-4.3a1.6 1.6 0 0 1 1.6 -1.6ZM16.3 5.3h1.9a0.5 0.5 0 0 1 0.5 0.5v1.9a0.5 0.5 0 0 1 -0.5 0.5h-1.9a0.5 0.5 0 0 1 -0.5 -0.5v-1.9a0.5 0.5 0 0 1 0.5 -0.5Z", "M4.6 13.5h4.3a1.6 1.6 0 0 1 1.6 1.6v4.3a1.6 1.6 0 0 1 -1.6 1.6h-4.3a1.6 1.6 0 0 1 -1.6 -1.6v-4.3a1.6 1.6 0 0 1 1.6 -1.6ZM5.8 15.8h1.9a0.5 0.5 0 0 1 0.5 0.5v1.9a0.5 0.5 0 0 1 -0.5 0.5h-1.9a0.5 0.5 0 0 1 -0.5 -0.5v-1.9a0.5 0.5 0 0 1 0.5 -0.5Z", "M14.2 13.5h1.6a0.7 0.7 0 0 1 0.7 0.7v1.6a0.7 0.7 0 0 1 -0.7 0.7h-1.6a0.7 0.7 0 0 1 -0.7 -0.7v-1.6a0.7 0.7 0 0 1 0.7 -0.7ZM18.7 13.5h1.6a0.7 0.7 0 0 1 0.7 0.7v1.6a0.7 0.7 0 0 1 -0.7 0.7h-1.6a0.7 0.7 0 0 1 -0.7 -0.7v-1.6a0.7 0.7 0 0 1 0.7 -0.7ZM14.2 18h1.6a0.7 0.7 0 0 1 0.7 0.7v1.6a0.7 0.7 0 0 1 -0.7 0.7h-1.6a0.7 0.7 0 0 1 -0.7 -0.7v-1.6a0.7 0.7 0 0 1 0.7 -0.7ZM18.7 18h1.6a0.7 0.7 0 0 1 0.7 0.7v1.6a0.7 0.7 0 0 1 -0.7 0.7h-1.6a0.7 0.7 0 0 1 -0.7 -0.7v-1.6a0.7 0.7 0 0 1 0.7 -0.7Z"),
        emptyList()),
    Sync(emptyList(),
        listOf("M20.5 12a8.5 8.5 0 0 1-14.7 5.8L3.5 15.5", "M3.5 12A8.5 8.5 0 0 1 18.2 6.2l2.3 2.3", "M20.5 3.5v5h-5", "M3.5 20.5v-5h5")),
    More(listOf("M10.1 5a1.9 1.9 0 1 0 3.8 0a1.9 1.9 0 1 0 -3.8 0ZM10.1 12a1.9 1.9 0 1 0 3.8 0a1.9 1.9 0 1 0 -3.8 0ZM10.1 19a1.9 1.9 0 1 0 3.8 0a1.9 1.9 0 1 0 -3.8 0Z"),
        emptyList()),
    Phone(listOf("M9 2h6a3 3 0 0 1 3 3v14a3 3 0 0 1 -3 3h-6a3 3 0 0 1 -3 -3v-14a3 3 0 0 1 3 -3ZM13.4 17.7L13.71 17.76L13.97 17.93L14.14 18.19L14.2 18.5L14.14 18.81L13.97 19.07L13.71 19.24L13.4 19.3L10.6 19.3L10.29 19.24L10.03 19.07L9.86 18.81L9.8 18.5L9.86 18.19L10.03 17.93L10.29 17.76L10.6 17.7Z"),
        emptyList()),
    Edit(listOf("M16.3 3.3a2.4 2.4 0 0 1 3.4 0l1 1a2.4 2.4 0 0 1 0 3.4L8.4 20 3 21l1-5.4Z"),
        listOf("M13.5 21h7")),
    Download(listOf("M5.2 18.8h13.6a1.2 1.2 0 0 1 1.2 1.2v0a1.2 1.2 0 0 1 -1.2 1.2h-13.6a1.2 1.2 0 0 1 -1.2 -1.2v0a1.2 1.2 0 0 1 1.2 -1.2Z"),
        listOf("M12 3.5v11", "m7 10 5 5 5-5")),
    Upload(listOf("M5.2 2.8h13.6a1.2 1.2 0 0 1 1.2 1.2v0a1.2 1.2 0 0 1 -1.2 1.2h-13.6a1.2 1.2 0 0 1 -1.2 -1.2v0a1.2 1.2 0 0 1 1.2 -1.2Z"),
        listOf("M12 20.5v-11", "m7 14 5-5 5 5")),
    Select(emptyList(),
        listOf("m9 11 3 3L22 4", "M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11")),
    Listen(listOf("M5 12.5h0.8a2.2 2.2 0 0 1 2.2 2.2v4.1a2.2 2.2 0 0 1 -2.2 2.2h-0.8a2.2 2.2 0 0 1 -2.2 -2.2v-4.1a2.2 2.2 0 0 1 2.2 -2.2Z", "M18.2 12.5h0.8a2.2 2.2 0 0 1 2.2 2.2v4.1a2.2 2.2 0 0 1 -2.2 2.2h-0.8a2.2 2.2 0 0 1 -2.2 -2.2v-4.1a2.2 2.2 0 0 1 2.2 -2.2Z"),
        listOf("M4.2 14v-2a7.8 7.8 0 0 1 15.6 0v2")),
    Copy(listOf("M11.1 8.5h6.8a2.6 2.6 0 0 1 2.6 2.6v6.8a2.6 2.6 0 0 1 -2.6 2.6h-6.8a2.6 2.6 0 0 1 -2.6 -2.6v-6.8a2.6 2.6 0 0 1 2.6 -2.6Z"),
        listOf("M15.5 5.6v-.3A2.3 2.3 0 0 0 13.2 3H5.3A2.3 2.3 0 0 0 3 5.3v7.9a2.3 2.3 0 0 0 2.3 2.3h.3"));
}
// ICONS:END

@Composable
fun TbIcon(icon: Ico, tint: Color = Tb.text2, size: Dp = 20.dp, modifier: Modifier = Modifier) {
    val fills = remember(icon) { icon.fill.map { PathParser().parsePathString(it).toPath().apply { fillType = PathFillType.EvenOdd } } }
    val strokes = remember(icon) { icon.stroke.map { PathParser().parsePathString(it).toPath() } }
    Canvas(modifier.size(size)) {
        val k = this.size.minDimension / 24f
        scale(k, k, pivot = Offset.Zero) {
            fills.forEach { drawPath(it, tint, style = Fill) }
            val line = Stroke(width = 2.2f, cap = StrokeCap.Round, join = StrokeJoin.Round)
            strokes.forEach { drawPath(it, tint, style = line) }
        }
    }
}
