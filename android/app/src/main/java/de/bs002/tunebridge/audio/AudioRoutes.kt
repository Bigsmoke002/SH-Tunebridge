package de.bs002.tunebridge.audio

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioDeviceInfo
import android.media.AudioManager
import android.media.AudioMixerAttributes
import android.os.Build

/**
 * Wohin geht der Ton, woher kommt das Mikrofon? Wichtig bei USB-Soundkarten:
 * - Ausgabe: Android schickt Musik dort oft unverändert an die Karte (Hi-Res bzw. „bit-perfect“, ab Android 14) –
 *   am Mischer vorbei. Dann kommt beim Handy-Ton nur Stille an; das lässt sich von außen nicht umgehen.
 * - Eingang: Hat die Karte einen Eingang, nimmt Android ihn statt des Handy-Mikrofons. Deshalb wählen wir das
 *   eingebaute Mikrofon ausdrücklich, solange „Externes Mikrofon“ aus ist.
 */
object AudioRoutes {
    private val USB = setOf(AudioDeviceInfo.TYPE_USB_DEVICE, AudioDeviceInfo.TYPE_USB_HEADSET, AudioDeviceInfo.TYPE_USB_ACCESSORY)

    private fun am(ctx: Context) = ctx.getSystemService(AudioManager::class.java)

    /** USB-Soundkarte als Ausgabe angeschlossen? */
    fun usbOutput(ctx: Context): AudioDeviceInfo? =
        am(ctx)?.getDevices(AudioManager.GET_DEVICES_OUTPUTS)?.firstOrNull { it.type in USB }

    /** Hat eine App (z. B. ein Hi-Res-Player) für die USB-Karte „bit-perfect“ eingestellt? Ab Android 14 abfragbar. */
    fun bitPerfect(ctx: Context): Boolean {
        if (Build.VERSION.SDK_INT < 34) return false
        val dev = usbOutput(ctx) ?: return false
        val attrs = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_MEDIA).build()
        return runCatching {
            am(ctx)?.getPreferredMixerAttributes(attrs, dev)?.mixerBehavior == AudioMixerAttributes.MIXER_BEHAVIOR_BIT_PERFECT
        }.getOrDefault(false)
    }

    /** Eingebautes Mikrofon des Handys (null, wenn das Gerät keins meldet). */
    fun builtinMic(ctx: Context): AudioDeviceInfo? =
        am(ctx)?.getDevices(AudioManager.GET_DEVICES_INPUTS)?.firstOrNull { it.type == AudioDeviceInfo.TYPE_BUILTIN_MIC }

    /** Ist ein externer Eingang (USB, Headset-Mikrofon) angeschlossen? */
    fun externalMic(ctx: Context): AudioDeviceInfo? =
        am(ctx)?.getDevices(AudioManager.GET_DEVICES_INPUTS)?.firstOrNull {
            it.type in USB || it.type == AudioDeviceInfo.TYPE_WIRED_HEADSET
        }
}
