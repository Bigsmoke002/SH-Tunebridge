package de.bs002.tunebridge.update

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import de.bs002.tunebridge.MainActivity

/**
 * Benachrichtigung zum App-Update: Fortschrittsbalken beim Laden, danach „bereit zum Installieren“.
 * Nur lokal auf dem Handy; ohne Benachrichtigungs-Erlaubnis zeigt Android sie einfach nicht (die App zeigt den Stand trotzdem).
 */
internal object UpdateNote {
    private const val CHANNEL = "update"
    private const val ID = 4711

    private fun nm(ctx: Context): NotificationManager? = runCatching {
        ctx.getSystemService(NotificationManager::class.java)?.also { nm ->
            if (nm.getNotificationChannel(CHANNEL) == null) nm.createNotificationChannel(
                NotificationChannel(CHANNEL, "App-Update", NotificationManager.IMPORTANCE_LOW).apply {
                    description = "Fortschritt beim Laden einer neuen SH-Tunebridge-Version"
                })
        }
    }.getOrNull()

    private fun base(ctx: Context): Notification.Builder =
        Notification.Builder(ctx, CHANNEL)
            .setContentIntent(PendingIntent.getActivity(ctx, 7, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP),
                PendingIntent.FLAG_IMMUTABLE))
            .setOnlyAlertOnce(true)

    private fun mb(b: Long) = "%.1f".format(java.util.Locale.GERMANY, b / 1_048_576.0)

    fun progress(ctx: Context, version: String, done: Long, total: Long) {
        val pct = if (total > 0) (done * 100 / total).toInt().coerceIn(0, 100) else 0
        runCatching {
            nm(ctx)?.notify(ID, base(ctx).setSmallIcon(android.R.drawable.stat_sys_download)
                .setContentTitle("Update $version wird geladen")
                .setContentText("${mb(done)} von ${mb(total)} MB · $pct %")
                .setProgress(100, pct, total <= 0).setOngoing(true).build())
        }
    }

    fun ready(ctx: Context, version: String) = runCatching {
        nm(ctx)?.notify(ID, base(ctx).setSmallIcon(android.R.drawable.stat_sys_download_done)
            .setContentTitle("Update $version bereit")
            .setContentText("Geladen und geprüft – tippen, um zu installieren").setAutoCancel(true).build())
    }

    fun failed(ctx: Context, message: String) = runCatching {
        nm(ctx)?.notify(ID, base(ctx).setSmallIcon(android.R.drawable.stat_notify_error)
            .setContentTitle("Update fehlgeschlagen").setContentText(message).setAutoCancel(true).build())
    }

    fun cancel(ctx: Context) = runCatching { nm(ctx)?.cancel(ID) }
}
