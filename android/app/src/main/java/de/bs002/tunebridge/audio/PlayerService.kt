package de.bs002.tunebridge.audio

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.content.pm.ServiceInfo
import android.graphics.Bitmap
import android.graphics.drawable.BitmapDrawable
import android.media.AudioManager
import android.media.MediaMetadata
import android.media.session.MediaSession
import android.media.session.PlaybackState
import android.os.IBinder
import androidx.core.content.ContextCompat
import coil.imageLoader
import coil.request.ImageRequest
import de.bs002.tunebridge.App
import de.bs002.tunebridge.MainActivity
import de.bs002.tunebridge.Player
import de.bs002.tunebridge.R
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.launch

/**
 * Hörproben-Player in der Benachrichtigung und auf dem Sperrbildschirm (Play/Pause, Vor, Zurück, Stopp) –
 * auch über Kopfhörer- und Auto-Tasten. Läuft nur, solange etwas in der Warteschlange ist; nichts wird gespeichert.
 */
class PlayerService : Service() {
    private lateinit var session: MediaSession
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main)
    private var art: Pair<String, Bitmap>? = null
    private var artJob: Job? = null
    private var foreground = false

    /** Kopfhörer abgezogen / Bluetooth weg: pausieren statt plötzlich laut über den Lautsprecher. */
    private val noisy = object : BroadcastReceiver() {
        override fun onReceive(c: Context?, i: Intent?) { if (Player.state.value.playing) Player.playPause() }
    }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        session = MediaSession(this, "SH-Tunebridge").apply {
            setCallback(object : MediaSession.Callback() {
                override fun onPlay() { if (!Player.state.value.playing) Player.playPause() }
                override fun onPause() { if (Player.state.value.playing) Player.playPause() }
                override fun onSkipToNext() = Player.next()
                override fun onSkipToPrevious() = Player.prev()
                override fun onStop() = Player.stop()
                override fun onSeekTo(pos: Long) = Player.seekTo(pos)
            })
            setSessionActivity(PendingIntent.getActivity(this@PlayerService, 0, Intent(this@PlayerService, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE))
            isActive = true
        }
        ContextCompat.registerReceiver(this, noisy, IntentFilter(AudioManager.ACTION_AUDIO_BECOMING_NOISY), ContextCompat.RECEIVER_NOT_EXPORTED)
        scope.launch { Player.state.collect { update(it) } }
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACT_TOGGLE -> Player.playPause()
            ACT_NEXT -> Player.next()
            ACT_PREV -> Player.prev()
            ACT_STOP -> Player.stop()
        }
        // Android verlangt startForeground kurz nach dem Start – auch wenn der Zustand gleich bleibt
        if (!foreground) update(Player.state.value)
        return START_NOT_STICKY
    }

    private fun update(s: Player.State) {
        val t = s.current
        if (t == null) {
            stopForeground(STOP_FOREGROUND_REMOVE); foreground = false
            stopSelf(); return
        }
        val cover = t.cover
        if (cover != null && art?.first != cover && artJob?.isActive != true && App.repo.settings.value.covers) {
            artJob = scope.launch {
                val r = imageLoader.execute(ImageRequest.Builder(this@PlayerService).data(cover).size(512).allowHardware(false).build())
                (r.drawable as? BitmapDrawable)?.bitmap?.let { art = cover to it; update(Player.state.value) }
            }
        }
        val bmp = art?.takeIf { it.first == cover }?.second
        session.setMetadata(MediaMetadata.Builder()
            .putString(MediaMetadata.METADATA_KEY_TITLE, t.title)
            .putString(MediaMetadata.METADATA_KEY_ARTIST, t.artist)
            .putString(MediaMetadata.METADATA_KEY_ALBUM, s.title ?: t.album ?: "Hörprobe")
            .putLong(MediaMetadata.METADATA_KEY_DURATION, Player.duration())
            .apply { bmp?.let { putBitmap(MediaMetadata.METADATA_KEY_ART, it) } }
            .build())
        var actions = PlaybackState.ACTION_PLAY_PAUSE or PlaybackState.ACTION_PLAY or PlaybackState.ACTION_PAUSE or
            PlaybackState.ACTION_STOP or PlaybackState.ACTION_SEEK_TO or PlaybackState.ACTION_SKIP_TO_PREVIOUS
        if (s.hasNext) actions = actions or PlaybackState.ACTION_SKIP_TO_NEXT
        session.setPlaybackState(PlaybackState.Builder()
            .setActions(actions)
            .setState(when { s.loading -> PlaybackState.STATE_BUFFERING; s.playing -> PlaybackState.STATE_PLAYING; else -> PlaybackState.STATE_PAUSED },
                Player.position(), if (s.playing) 1f else 0f)
            .build())

        val n = note(s, t.title, t.artist, bmp)
        if (!foreground) {
            startForeground(NOTE_ID, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PLAYBACK); foreground = true
        } else getSystemService(NotificationManager::class.java).notify(NOTE_ID, n)
    }

    private fun action(icon: Int, label: String, act: String, code: Int) = Notification.Action.Builder(
        android.graphics.drawable.Icon.createWithResource(this, icon), label,
        PendingIntent.getService(this, code, Intent(this, PlayerService::class.java).setAction(act), PendingIntent.FLAG_IMMUTABLE),
    ).build()

    private fun note(s: Player.State, title: String, artist: String, bmp: Bitmap?): Notification {
        val nm = getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel(CHANNEL) == null) {
            nm.createNotificationChannel(NotificationChannel(CHANNEL, "Hörproben-Player", NotificationManager.IMPORTANCE_LOW).apply {
                description = "Steuerung der Hörproben in der Benachrichtigung und auf dem Sperrbildschirm"
                setShowBadge(false)
            })
        }
        return Notification.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_wave)
            .setContentTitle(title)
            .setContentText(artist.ifBlank { "Hörprobe" })
            .setSubText(s.title ?: "Hörprobe · 30 s")
            .setLargeIcon(bmp)
            .setContentIntent(session.controller.sessionActivity)
            .setDeleteIntent(PendingIntent.getService(this, 9, Intent(this, PlayerService::class.java).setAction(ACT_STOP), PendingIntent.FLAG_IMMUTABLE))
            .setVisibility(Notification.VISIBILITY_PUBLIC)
            .setOngoing(s.playing)
            .addAction(action(android.R.drawable.ic_media_previous, "Zurück", ACT_PREV, 1))
            .addAction(if (s.playing) action(android.R.drawable.ic_media_pause, "Pause", ACT_TOGGLE, 2)
                       else action(android.R.drawable.ic_media_play, "Abspielen", ACT_TOGGLE, 2))
            .addAction(action(android.R.drawable.ic_media_next, "Weiter", ACT_NEXT, 3))
            .addAction(action(android.R.drawable.ic_menu_close_clear_cancel, "Beenden", ACT_STOP, 4))
            .setStyle(Notification.MediaStyle().setMediaSession(session.sessionToken).setShowActionsInCompactView(0, 1, 2))
            .build()
    }

    override fun onDestroy() {
        scope.cancel()
        runCatching { unregisterReceiver(noisy) }
        session.isActive = false
        session.release()
        super.onDestroy()
    }

    companion object {
        private const val CHANNEL = "player"
        private const val NOTE_ID = 8
        private const val ACT_TOGGLE = "toggle"
        private const val ACT_NEXT = "next"
        private const val ACT_PREV = "prev"
        private const val ACT_STOP = "stop"

        /** Vom Player beim Abspielen aufgerufen (immer nach einem Tippen in der App). */
        fun ensure(ctx: Context) {
            runCatching { ContextCompat.startForegroundService(ctx, Intent(ctx, PlayerService::class.java)) }
        }
    }
}
