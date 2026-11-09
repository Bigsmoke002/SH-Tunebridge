package de.bs002.tunebridge.audio

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.IBinder
import android.os.Looper
import androidx.core.content.ContextCompat
import de.bs002.tunebridge.App
import de.bs002.tunebridge.MainActivity
import de.bs002.tunebridge.R
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Handy-Ton erkennen (AudioPlaybackCapture, ab Android 10).
 *
 * Android verlangt dafür deine Freigabe im System-Dialog („Aufnahme starten“) und einen Vordergrund-Dienst mit
 * sichtbarer Benachrichtigung. Genutzt wird nur der Ton – kein Bild. Die Freigabe bleibt bestehen, bis du sie in der
 * Benachrichtigung beendest oder 15 Minuten lang nicht erkannt wurde; dann ist sie weg und Android fragt neu.
 */
class CaptureService : Service() {
    private val idle = Handler(Looper.getMainLooper())
    private val stopIdle = Runnable { stopSelf() }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) { stopSelf(); return START_NOT_STICKY }
        val code = intent?.getIntExtra(EXTRA_CODE, 0) ?: 0
        val data: Intent? = intent?.let {
            if (Build.VERSION.SDK_INT >= 33) it.getParcelableExtra(EXTRA_DATA, Intent::class.java) else @Suppress("DEPRECATION") it.getParcelableExtra(EXTRA_DATA)
        }
        startForeground(NOTE_ID, note(), ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)   // vor getMediaProjection (Android 14)
        if (data == null) { stopSelf(); return START_NOT_STICKY }
        val mpm = getSystemService(MediaProjectionManager::class.java)
        val p = runCatching { mpm.getMediaProjection(code, data) }.getOrNull()
        if (p == null) { stopSelf(); return START_NOT_STICKY }
        p.registerCallback(object : MediaProjection.Callback() {
            override fun onStop() { if (_projection.value === p) _projection.value = null; stopSelf() }
        }, Handler(Looper.getMainLooper()))
        _projection.value = p
        touch()
        if (intent.getBooleanExtra(EXTRA_LISTEN, false)) App.listener.start(App.repo.settings.value.seconds, system = true)
        return START_NOT_STICKY
    }

    override fun onDestroy() {
        idle.removeCallbacks(stopIdle)
        _projection.value?.let { runCatching { it.stop() } }
        _projection.value = null
        instance = null
        super.onDestroy()
    }

    override fun onCreate() {
        super.onCreate()
        instance = this
    }

    private fun touch() {
        idle.removeCallbacks(stopIdle)
        idle.postDelayed(stopIdle, IDLE_MS)
    }

    private fun note(): Notification {
        val nm = getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(CHANNEL) == null) {
            nm.createNotificationChannel(NotificationChannel(CHANNEL, "Handy-Ton erkennen", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Sichtbar, solange SH-Tunebridge den Ton des Handys hören darf"
            })
        }
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1, Intent(this, CaptureService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_wave)
            .setContentTitle("Handy-Ton freigegeben")
            .setContentText("Gehört wird nur beim Tippen auf Erkennen – nichts wird gespeichert.")
            .setContentIntent(open)
            .setOngoing(true)
            .addAction(Notification.Action.Builder(null, "Beenden", stop).build())
            .build()
    }

    companion object {
        private const val CHANNEL = "capture"
        private const val NOTE_ID = 7
        private const val IDLE_MS = 15 * 60 * 1000L
        private const val EXTRA_CODE = "code"
        private const val EXTRA_DATA = "data"
        private const val EXTRA_LISTEN = "listen"
        private const val ACTION_STOP = "stop"
        private var instance: CaptureService? = null

        private val _projection = MutableStateFlow<MediaProjection?>(null)
        /** Aktive Freigabe für den Handy-Ton (null = keine; dann muss Android neu fragen). */
        val projection: StateFlow<MediaProjection?> = _projection.asStateFlow()

        /** Nach dem System-Dialog: Dienst starten, Freigabe übernehmen und (optional) gleich erkennen. */
        fun begin(ctx: Context, code: Int, data: Intent, listen: Boolean) {
            ContextCompat.startForegroundService(ctx, Intent(ctx, CaptureService::class.java)
                .putExtra(EXTRA_CODE, code).putExtra(EXTRA_DATA, data).putExtra(EXTRA_LISTEN, listen))
        }

        fun stop(ctx: Context) { ctx.stopService(Intent(ctx, CaptureService::class.java)) }

        /** Bei jeder Erkennung: die 15-Minuten-Frist neu starten. */
        fun used() { instance?.touch() }
    }
}
