package de.bs002.tunebridge.ui.screens

import android.Manifest
import android.content.pm.PackageManager
import android.util.Size
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.core.resolutionselector.ResolutionSelector
import androidx.camera.core.resolutionselector.ResolutionStrategy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.SolidColor
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.input.KeyboardCapitalization
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.zxing.BarcodeFormat
import com.google.zxing.BinaryBitmap
import com.google.zxing.DecodeHintType
import com.google.zxing.MultiFormatReader
import com.google.zxing.PlanarYUVLuminanceSource
import com.google.zxing.common.GlobalHistogramBinarizer
import com.google.zxing.common.HybridBinarizer
import de.bs002.tunebridge.App
import de.bs002.tunebridge.sync.PcSync
import de.bs002.tunebridge.ui.components.BtnKind
import de.bs002.tunebridge.ui.components.Notice
import de.bs002.tunebridge.ui.components.TbButton
import de.bs002.tunebridge.ui.components.TbCard
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbType
import kotlinx.coroutines.launch
import java.util.concurrent.Executors

@Composable
fun PairScreen(back: () -> Unit, done: (String) -> Unit) {
    // Schritt 1: QR-Code scannen (oder Code eintippen) – Schritt 2: alles zeigen und bestätigen (PairConfirm)
    var invite by remember { mutableStateOf<PcSync.Invite?>(null) }
    val inv = invite
    if (inv != null) PairConfirm(inv, back = { invite = null }, done = done)
    else ScanStep(back) { invite = it }
}

@Composable
private fun ScanStep(back: () -> Unit, found: (PcSync.Invite) -> Unit) {
    val ctx = LocalContext.current
    var camOk by remember { mutableStateOf(ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) }
    var asked by remember { mutableStateOf(false) }
    var manual by remember { mutableStateOf(false) }
    var addr by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    val permission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { camOk = it; asked = true; if (!it) manual = true }
    LaunchedEffect(Unit) { if (!camOk) permission.launch(Manifest.permission.CAMERA) }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState())) {
        TopBack(back)
        ScreenHeader("Mit PC koppeln")
        Column(Modifier.padding(horizontal = 20.dp)) {
            Text("Am PC in SH-Tunebridge: Einstellungen › Handy › „Handy koppeln“. Dann den QR-Code hier scannen. " +
                "Gekoppelt wird erst, wenn du auf der nächsten Seite und am PC zustimmst.",
                style = TbType.body, color = Tb.text2)
            Spacer(Modifier.height(16.dp))
            if (camOk && !manual) {
                Box(Modifier.fillMaxWidth().aspectRatio(1f).clip(RoundedCornerShape(14.dp)).background(Tb.bg2)) {
                    QrScanner { text ->
                        val inv = PcSync.parseInvite(text)
                        if (inv == null) error = "Das ist kein SH-Tunebridge-Code" else found(inv)
                    }
                    Brackets()
                }
            } else if (!camOk && asked) {
                Notice("Ohne Kamera geht es auch: Adresse und Code am PC ablesen und unten eintippen.", icon = Ico.Info, color = Tb.text2)
            }
            error?.let { Spacer(Modifier.height(12.dp)); Notice(it, color = Tb.danger) }
            Spacer(Modifier.height(16.dp))
            if (!manual) TbButton("Code stattdessen eintippen", { manual = true }, kind = BtnKind.Ghost, icon = Ico.Key)
            else TbCard(Modifier.fillMaxWidth()) {
                Field("Adresse des PCs", addr, "z. B. 192.168.1.20:8766", KeyboardType.Uri) { addr = it.trim() }
                Spacer(Modifier.height(12.dp))
                Field("Kopplungs-Code", code, "XXXX-XXXX-XXXX-XXXX-XXXX", KeyboardType.Ascii, caps = true) { code = it }
                Spacer(Modifier.height(14.dp))
                TbButton("Weiter", {
                    val c = PcSync.normCode(code)
                    if (addr.isBlank() || c.length != 20) error = "Bitte Adresse und den 20-stelligen Code vom PC eingeben"
                    else found(PcSync.Invite(listOf(if (':' in addr) addr else "$addr:8766"), c, "PC", null))
                }, kind = BtnKind.Primary)
            }
            Spacer(Modifier.height(20.dp))
            Text("Handy und PC müssen im selben Netz sein (WLAN oder VPN). Der Code gilt 5 Minuten und nur einmal.",
                style = TbType.small, color = Tb.text3)
            Spacer(Modifier.height(32.dp))
        }
    }
}

@Composable
private fun Field(label: String, value: String, hint: String, type: KeyboardType, caps: Boolean = false, onChange: (String) -> Unit) {
    val shape = RoundedCornerShape(Tb.radiusSm)
    Text(label, style = TbType.label, color = Tb.text3)
    Spacer(Modifier.height(6.dp))
    BasicTextField(
        value, onChange, singleLine = true, textStyle = TbType.body.copy(color = Tb.text), cursorBrush = SolidColor(Tb.accent),
        keyboardOptions = KeyboardOptions(keyboardType = type, capitalization = if (caps) KeyboardCapitalization.Characters else KeyboardCapitalization.None, autoCorrectEnabled = false),
        modifier = Modifier.fillMaxWidth().clip(shape).background(Tb.bg3).border(1.dp, Tb.line, shape).padding(horizontal = 12.dp, vertical = 12.dp),
        decorationBox = { inner -> if (value.isEmpty()) Text(hint, style = TbType.body, color = Tb.text3); inner() },
    )
}

/** Ecken-Markierung über dem Kamerabild. */
@Composable
private fun Brackets() {
    Canvas(Modifier.fillMaxSize().padding(36.dp)) {
        val l = size.minDimension * 0.16f
        val w = 3.dp.toPx()
        listOf(Offset(0f, 0f) to (1 to 1), Offset(size.width, 0f) to (-1 to 1), Offset(0f, size.height) to (1 to -1), Offset(size.width, size.height) to (-1 to -1))
            .forEach { (p, d) ->
                drawLine(Tb.accent, p, Offset(p.x + l * d.first, p.y), w, StrokeCap.Round)
                drawLine(Tb.accent, p, Offset(p.x, p.y + l * d.second), w, StrokeCap.Round)
            }
    }
}

@Composable
private fun QrScanner(onCode: (String) -> Unit) {
    val ctx = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val executor = remember { Executors.newSingleThreadExecutor() }
    var last by remember { mutableStateOf("") }
    var frames = 0
    DisposableEffect(Unit) { onDispose { executor.shutdown() } }
    AndroidView(factory = { c ->
        // COMPATIBLE (TextureView): fügt sich in Rahmen und Ecken ein. Die schnellere SurfaceView läge „unter“ dem
        // Fenster und würde vom Hintergrund der Karte verdeckt – Kamera läuft, Bild bleibt schwarz.
        val view = PreviewView(c).apply {
            implementationMode = PreviewView.ImplementationMode.COMPATIBLE
            scaleType = PreviewView.ScaleType.FILL_CENTER
        }
        val future = ProcessCameraProvider.getInstance(c)
        future.addListener({
            val provider = future.get()
            val preview = Preview.Builder().build().also { it.surfaceProvider = view.surfaceProvider }
            val reader = MultiFormatReader().apply {
                setHints(mapOf(DecodeHintType.POSSIBLE_FORMATS to listOf(BarcodeFormat.QR_CODE), DecodeHintType.TRY_HARDER to true))
            }
            val analysis = ImageAnalysis.Builder()
                .setResolutionSelector(ResolutionSelector.Builder().setResolutionStrategy(
                    ResolutionStrategy(Size(1280, 720), ResolutionStrategy.FALLBACK_RULE_CLOSEST_HIGHER_THEN_LOWER)).build())
                .setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
            analysis.setAnalyzer(executor) { img ->
                try {
                    val plane = img.planes[0]
                    val buf = plane.buffer
                    val data = ByteArray(buf.remaining()).also { buf.get(it) }
                    val src = PlanarYUVLuminanceSource(data, plane.rowStride, img.height, 0, 0, img.width, img.height, false)
                    if (frames++ == 0) android.util.Log.d("TbQr", "erstes Kamerabild ${img.width}x${img.height}")
                    // Bildschirm abfotografiert: Moiré/Spiegelungen – zweiter Versuch mit anderem Schwellwert
                    val text = runCatching { reader.decodeWithState(BinaryBitmap(HybridBinarizer(src))).text }.getOrNull()
                        ?: runCatching { reader.reset(); reader.decodeWithState(BinaryBitmap(GlobalHistogramBinarizer(src))).text }.getOrNull()
                    if (text != null && text != last) {
                        last = text
                        ContextCompat.getMainExecutor(ctx).execute { onCode(text) }
                    }
                } finally {
                    reader.reset()
                    img.close()
                }
            }
            runCatching {
                provider.unbindAll()
                provider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
            }.onFailure { android.util.Log.w("TbQr", "Kamera ließ sich nicht starten", it) }
        }, ContextCompat.getMainExecutor(c))
        view
    }, modifier = Modifier.fillMaxSize())
}
