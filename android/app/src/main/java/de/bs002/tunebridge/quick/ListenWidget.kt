package de.bs002.tunebridge.quick

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.ComponentName
import android.content.Context
import android.widget.RemoteViews
import de.bs002.tunebridge.App
import de.bs002.tunebridge.MainActivity
import de.bs002.tunebridge.R

/** Widget für den Startbildschirm: „Erkennen“ (Mikrofon) und „Handy-Ton“, darunter der zuletzt erkannte Song. */
class ListenWidget : AppWidgetProvider() {
    override fun onUpdate(ctx: Context, mgr: AppWidgetManager, ids: IntArray) {
        ids.forEach { mgr.updateAppWidget(it, views(ctx)) }
    }

    companion object {
        private fun pending(ctx: Context, system: Boolean, code: Int) = PendingIntent.getActivity(
            ctx, code, MainActivity.listenIntent(ctx, system), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

        private fun views(ctx: Context) = RemoteViews(ctx.packageName, R.layout.widget_listen).apply {
            setOnClickPendingIntent(R.id.w_mic, pending(ctx, false, 10))
            setOnClickPendingIntent(R.id.w_sys, pending(ctx, true, 11))
            val last = runCatching { App.repo.history.value.firstOrNull() }.getOrNull()
            setTextViewText(R.id.w_last, last?.let { "${it.track.title} · ${it.track.artist}" } ?: "Noch nichts erkannt")
        }

        /** Nach einer Erkennung: „Zuletzt“ im Widget auffrischen (nichts passiert, wenn keins platziert ist). */
        fun refresh(ctx: Context) {
            val mgr = AppWidgetManager.getInstance(ctx)
            val ids = mgr.getAppWidgetIds(ComponentName(ctx, ListenWidget::class.java))
            if (ids.isNotEmpty()) ids.forEach { mgr.updateAppWidget(it, views(ctx)) }
        }
    }
}
