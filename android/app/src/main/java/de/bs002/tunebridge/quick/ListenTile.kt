package de.bs002.tunebridge.quick

import android.annotation.SuppressLint
import android.app.PendingIntent
import android.os.Build
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import de.bs002.tunebridge.App
import de.bs002.tunebridge.MainActivity

/**
 * Schnellkachel „Erkennen“ im Benachrichtigungsfeld: öffnet die App und erkennt sofort – mit der zuletzt gewählten
 * Quelle (Mikrofon oder Handy-Ton). Das Mikrofon geht wie immer erst nach diesem Tipp an.
 */
class ListenTile : TileService() {
    override fun onStartListening() {
        qsTile?.apply {
            state = Tile.STATE_INACTIVE
            if (Build.VERSION.SDK_INT >= 29) subtitle = if (App.repo.settings.value.system) "Handy-Ton" else "Mikrofon"
            updateTile()
        }
    }

    @SuppressLint("StartActivityAndCollapseDeprecated")
    override fun onClick() {
        val intent = MainActivity.listenIntent(this, App.repo.settings.value.system)
        if (Build.VERSION.SDK_INT >= 34) {
            startActivityAndCollapse(PendingIntent.getActivity(this, 0, intent, PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT))
        } else {
            @Suppress("DEPRECATION") startActivityAndCollapse(intent)
        }
    }
}
