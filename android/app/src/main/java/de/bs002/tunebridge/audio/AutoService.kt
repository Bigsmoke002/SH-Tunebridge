package de.bs002.tunebridge.audio

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.os.IBinder
import android.os.PowerManager
import androidx.core.content.ContextCompat
import de.bs002.tunebridge.App
import de.bs002.tunebridge.Listener
import de.bs002.tunebridge.MainActivity
import de.bs002.tunebridge.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Dauer-Erkennen: hört in festen Abständen kurz zu (wie ein Tipp auf den Kreis) und sammelt die Songs – z. B. bei
 * einer Party oder beim Radio. Nur mit sichtbarer Benachrichtigung („Beenden“), endet von selbst nach der gewählten
 * Dauer. Der Ton bleibt wie immer nur im Arbeitsspeicher; an Shazam geht nur der Fingerabdruck.
 */
class AutoService : Service() {
    data class Run(val active: Boolean = false, val system: Boolean = false, val intervalS: Int = 120, val until: Long = 0,
                   val rounds: Int = 0, val found: Int = 0, val last: String? = null, val status: String = "")

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var loop: Job? = null
    private var wake: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) { stopSelf(); return START_NOT_STICKY }
        val system = intent?.getBooleanExtra(EXTRA_SYSTEM, false) ?: false
        val interval = (intent?.getIntExtra(EXTRA_INTERVAL, 120) ?: 120).coerceAtLeast(60)
        val minutes = (intent?.getIntExtra(EXTRA_MINUTES, 60) ?: 60).coerceIn(5, 240)
        val until = System.currentTimeMillis() + minutes * 60_000L
        _run.value = Run(true, system, interval, until, status = "Startet …")
        val type = if (system) ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION else ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE
        runCatching { startForeground(NOTE_ID, note(_run.value), type) }.onFailure { stopSelf(); return START_NOT_STICKY }
        // Zwischen den Durchgängen darf das Handy sonst einschlafen – dann käme der nächste Durchgang viel zu spät
        wake = getSystemService(PowerManager::class.java).newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "tunebridge:auto")
            .apply { setReferenceCounted(false); acquire(minutes * 60_000L + 60_000L) }
        loop?.cancel()
        loop = scope.launch {
            val seen = HashSet<String>()
            while (System.currentTimeMillis() < until) {
                if (system && CaptureService.projection.value == null) { update { it.copy(status = "Handy-Ton-Freigabe beendet") }; break }
                update { it.copy(status = "Hört zu …") }
                val r = App.listener.runOnce(App.repo.settings.value.seconds, system)
                update { cur ->
                    when (r) {
                        is Listener.State.Found -> {
                            val new = seen.add(r.rec.uid)
                            cur.copy(rounds = cur.rounds + 1, found = cur.found + if (new) 1 else 0,
                                last = r.rec.uid, status = "${r.rec.track.title} – ${r.rec.track.artist}")
                        }
                        is Listener.State.Queued -> cur.copy(rounds = cur.rounds + 1, status = "Kein Internet – Fingerabdruck gemerkt")
                        is Listener.State.Silent -> cur.copy(rounds = cur.rounds + 1, status = "Gerade nichts zu hören")
                        is Listener.State.NotFound -> cur.copy(rounds = cur.rounds + 1, status = "Nichts erkannt")
                        is Listener.State.Limited -> cur.copy(rounds = cur.rounds + 1, status = "Shazam macht eine Pause")
                        is Listener.State.Failed -> cur.copy(rounds = cur.rounds + 1, status = r.message)
                        else -> cur.copy(rounds = cur.rounds + 1)
                    }
                }
                // Bei Shazam-Pause länger warten
                val wait = if (r is Listener.State.Limited) maxOf(interval, r.waitSeconds + 5) else interval
                delay(wait * 1000L)
            }
            stopSelf()
        }
        return START_NOT_STICKY
    }

    private fun update(change: (Run) -> Run) {
        _run.value = change(_run.value)
        if (_run.value.active) getSystemService(NotificationManager::class.java).notify(NOTE_ID, note(_run.value))
    }

    private fun note(r: Run): Notification {
        val nm = getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(CHANNEL) == null) {
            nm.createNotificationChannel(NotificationChannel(CHANNEL, "Dauer-Erkennen", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Sichtbar, solange SH-Tunebridge in Abständen zuhört"
            })
        }
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val stop = PendingIntent.getService(this, 1, Intent(this, AutoService::class.java).setAction(ACTION_STOP), PendingIntent.FLAG_IMMUTABLE)
        val end = java.text.SimpleDateFormat("HH:mm", java.util.Locale.GERMANY).format(java.util.Date(r.until))
        return Notification.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_wave)
            .setContentTitle("Dauer-Erkennen · ${if (r.found == 1) "1 Song" else "${r.found} Songs"}")
            .setContentText("${r.status} · ${if (r.system) "Handy-Ton" else "Mikrofon"}, alle ${r.intervalS / 60} min, bis $end")
            .setContentIntent(open)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .addAction(Notification.Action.Builder(null, "Beenden", stop).build())
            .build()
    }

    override fun onDestroy() {
        loop?.cancel()
        scope.cancel()
        App.listener.cancel()
        runCatching { wake?.release() }
        _run.value = _run.value.copy(active = false, status = "Beendet")
        super.onDestroy()
    }

    companion object {
        private const val CHANNEL = "auto"
        private const val NOTE_ID = 9
        private const val EXTRA_SYSTEM = "system"
        private const val EXTRA_INTERVAL = "interval"
        private const val EXTRA_MINUTES = "minutes"
        private const val ACTION_STOP = "stop"

        private val _run = MutableStateFlow(Run())
        val run: StateFlow<Run> = _run.asStateFlow()

        /** Nur aus der sichtbaren App starten (Android verlangt das für Mikrofon im Hintergrund). */
        fun start(ctx: Context, system: Boolean, intervalS: Int, minutes: Int) {
            ContextCompat.startForegroundService(ctx, Intent(ctx, AutoService::class.java)
                .putExtra(EXTRA_SYSTEM, system).putExtra(EXTRA_INTERVAL, intervalS).putExtra(EXTRA_MINUTES, minutes))
        }

        fun stop(ctx: Context) { ctx.startService(Intent(ctx, AutoService::class.java).setAction(ACTION_STOP)) }
    }
}
