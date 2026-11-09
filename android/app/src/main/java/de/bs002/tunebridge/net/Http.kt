package de.bs002.tunebridge.net

import okhttp3.OkHttpClient
import java.util.concurrent.TimeUnit

/** Ein gemeinsamer HTTP-Client. Kein Cookie-Speicher, kein Cache auf Platte – nichts bleibt liegen. */
object Http {
    val client: OkHttpClient by lazy {
        OkHttpClient.Builder()
            .connectTimeout(8, TimeUnit.SECONDS)
            .readTimeout(15, TimeUnit.SECONDS)
            .callTimeout(20, TimeUnit.SECONDS)
            .retryOnConnectionFailure(false)
            .build()
    }

    /** Kurze Zeitlimits für den PC im WLAN: ist er nicht da, soll die App nicht hängen. */
    val lan: OkHttpClient by lazy {
        client.newBuilder().connectTimeout(3, TimeUnit.SECONDS).readTimeout(30, TimeUnit.SECONDS)
            .callTimeout(45, TimeUnit.SECONDS).build()
    }

    /** Koppeln: der PC antwortet erst, wenn dort „Zulassen“ geklickt wurde (bis zu 2 Minuten). */
    val pairing: OkHttpClient by lazy {
        client.newBuilder().connectTimeout(4, TimeUnit.SECONDS).readTimeout(150, TimeUnit.SECONDS)
            .callTimeout(160, TimeUnit.SECONDS).build()
    }
}
