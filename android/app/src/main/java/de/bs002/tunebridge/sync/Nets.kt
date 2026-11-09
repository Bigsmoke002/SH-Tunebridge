package de.bs002.tunebridge.sync

import java.net.Inet4Address
import java.net.NetworkInterface

/**
 * Welche Netze hat das Handy gerade? (WLAN, z. B. 192.168.178.0/24, und VPN.)
 * Liest nur die eigenen Netzwerkkarten – braucht keine Standort- oder WLAN-Berechtigung und sendet nichts.
 * Damit spricht die App einen PC nur an, wenn das Handy im selben Netz ist: im Café-WLAN wird nichts versucht.
 */
object Nets {
    data class Net(val cidr: String, val ip: String, val iface: String, val vpn: Boolean) {
        val label: String get() = if (vpn) "VPN" else if (iface.startsWith("wlan")) "WLAN" else "Netz"
    }

    private const val CGNAT_BASE = (100 shl 24) or (64 shl 16)
    private const val CGNAT_MASK = -0x400000     // /10

    /** Ohne Zustimmung (Mehr › Datenschutz bzw. beim Koppeln) wird nichts ausgelesen – dann ist auch kein PC „erreichbar“. */
    fun allowed(): Boolean = runCatching { de.bs002.tunebridge.App.repo.settings.value.netConsent }.getOrDefault(false)

    fun current(): List<Net> = if (!allowed()) emptyList() else runCatching {
        NetworkInterface.getNetworkInterfaces().toList().filter { it.isUp && !it.isLoopback }.flatMap { nif ->
            nif.interfaceAddresses.mapNotNull { a ->
                val ip = a.address as? Inet4Address ?: return@mapNotNull null
                if (ip.isLinkLocalAddress) return@mapNotNull null
                val host = ip.hostAddress ?: return@mapNotNull null
                val vpn = inCgnat(host) || nif.name.startsWith("tun") || nif.name.startsWith("wg") || nif.name.startsWith("ppp")
                val prefix = if (inCgnat(host)) 10 else a.networkPrefixLength.toInt().coerceIn(8, 32)
                Net("${network(host, prefix)}/$prefix", host, nif.name, vpn)
            }
        }.filter { isPrivate(it.ip) || inCgnat(it.ip) }
    }.getOrDefault(emptyList())

    /** Ist diese PC-Adresse („ip:port“) aus einem der aktuellen Netze des Handys erreichbar? */
    fun reachable(addr: String, nets: List<Net> = current()): Boolean {
        val ip = addr.substringBeforeLast(':')
        val v = toInt(ip) ?: return false
        if (inCgnat(ip)) return nets.any { inCgnat(it.ip) }
        return nets.any { n ->
            val prefix = n.cidr.substringAfter('/').toInt()
            val mask = if (prefix == 0) 0 else -1 shl (32 - prefix)
            (toInt(n.ip)!! and mask) == (v and mask)
        }
    }

    /** Netz, in dem eine PC-Adresse liegt – für die Anzeige („Heimnetz 192.168.178.0/24“). */
    fun describe(addr: String, nets: List<Net> = current()): String {
        val ip = addr.substringBeforeLast(':')
        if (inCgnat(ip)) return "VPN"
        nets.firstOrNull { reachable(addr, listOf(it)) }?.let { return "Heimnetz ${it.cidr}" }
        val parts = ip.split('.')
        return if (parts.size == 4) "Heimnetz ${parts[0]}.${parts[1]}.${parts[2]}.x" else "Netz"
    }

    fun inCgnat(ip: String): Boolean = toInt(ip)?.let { (it and CGNAT_MASK) == CGNAT_BASE } ?: false

    private fun isPrivate(ip: String): Boolean {
        val v = toInt(ip) ?: return false
        val a = (v ushr 24) and 0xff; val b = (v ushr 16) and 0xff
        return a == 10 || (a == 172 && b in 16..31) || (a == 192 && b == 168)
    }

    private fun network(ip: String, prefix: Int): String {
        val v = toInt(ip)!!
        val mask = if (prefix == 0) 0 else -1 shl (32 - prefix)
        val n = v and mask
        return "${(n ushr 24) and 0xff}.${(n ushr 16) and 0xff}.${(n ushr 8) and 0xff}.${n and 0xff}"
    }

    private fun toInt(ip: String): Int? {
        val p = ip.split('.')
        if (p.size != 4) return null
        var v = 0
        for (x in p) { val n = x.toIntOrNull() ?: return null; if (n !in 0..255) return null; v = (v shl 8) or n }
        return v
    }
}
