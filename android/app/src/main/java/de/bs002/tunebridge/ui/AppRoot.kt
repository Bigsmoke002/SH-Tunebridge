package de.bs002.tunebridge.ui

import androidx.compose.animation.EnterTransition
import androidx.compose.animation.ExitTransition
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.animation.slideInHorizontally
import androidx.compose.animation.slideOutHorizontally
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.navigationBars
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.safeDrawing
import androidx.compose.foundation.layout.statusBars
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.windowInsetsPadding
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Snackbar
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.unit.dp
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import de.bs002.tunebridge.App
import de.bs002.tunebridge.ui.components.Hairline
import de.bs002.tunebridge.ui.screens.HistoryScreen
import de.bs002.tunebridge.ui.screens.ListenScreen
import de.bs002.tunebridge.ui.screens.PairScreen
import de.bs002.tunebridge.ui.screens.PcScreen
import de.bs002.tunebridge.ui.screens.PlaylistScreen
import de.bs002.tunebridge.ui.screens.PlaylistsScreen
import de.bs002.tunebridge.ui.screens.PrivacyScreen
import de.bs002.tunebridge.ui.screens.SettingsScreen
import de.bs002.tunebridge.ui.screens.SongScreen
import de.bs002.tunebridge.ui.screens.WelcomeScreen
import de.bs002.tunebridge.ui.theme.Ico
import de.bs002.tunebridge.ui.theme.Tb
import de.bs002.tunebridge.ui.theme.TbIcon
import de.bs002.tunebridge.ui.theme.TbType
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.launch
import android.net.Uri

private enum class Tab(val route: String, val label: String, val icon: Ico) {
    Listen("listen", "Erkennen", Ico.Wave),
    History("history", "Verlauf", Ico.Clock),
    Lists("playlists", "Playlists", Ico.Stack),
    More("more", "Mehr", Ico.Sliders),
}

@Composable
fun AppRoot(messages: Flow<String>) {
    val settings by App.repo.settings.collectAsState()
    val snack = remember { SnackbarHostState() }
    val scope = rememberCoroutineScope()
    val toast: (String) -> Unit = { m -> scope.launch { snack.currentSnackbarData?.dismiss(); snack.showSnackbar(m) } }
    LaunchedEffect(messages) { messages.collect { toast(it) } }

    Box(Modifier.fillMaxSize().background(Tb.bg0)) {
        if (settings.consent < App.CONSENT_VERSION) {
            val nav = rememberNavController()
            NavHost(nav, "welcome", Modifier.windowInsetsPadding(WindowInsets.safeDrawing)) {
                composable("welcome") { WelcomeScreen(openPrivacy = { nav.navigate("privacy") }) }
                composable("privacy") { PrivacyScreen(back = { nav.popBackStack() }) }
            }
        } else Main(toast)
        SnackbarHost(snack, Modifier.align(Alignment.BottomCenter).padding(bottom = 96.dp, start = 16.dp, end = 16.dp)) { data ->
            Snackbar(containerColor = Tb.bg4, contentColor = Tb.text, shape = RoundedCornerShape(Tb.radius)) {
                Text(data.visuals.message, style = TbType.body)
            }
        }
    }
}

@Composable
private fun Main(toast: (String) -> Unit) {
    val nav = rememberNavController()
    val entry by nav.currentBackStackEntryAsState()
    val route = entry?.destination?.route
    val tab = Tab.entries.firstOrNull { it.route == route }
    val request by App.listenRequest.collectAsState()
    LaunchedEffect(request) { if (request != null && route != Tab.Listen.route) nav.go(Tab.Listen) }

    de.bs002.tunebridge.ui.screens.UpdatePrompt(openMore = { nav.go(Tab.More) })
    Column(Modifier.fillMaxSize().windowInsetsPadding(WindowInsets.statusBars)) {
        Box(Modifier.weight(1f)) {
            NavHost(
                nav, Tab.Listen.route,
                enterTransition = { fadeIn() }, exitTransition = { fadeOut() },
            ) {
                composable(Tab.Listen.route) { ListenScreen(openSong = { nav.navigate("song/${Uri.encode(it)}") }, openPc = { nav.go(Tab.More) }) }
                composable(Tab.History.route) { HistoryScreen(openSong = { nav.navigate("song/${Uri.encode(it)}") }) }
                composable(Tab.Lists.route) {
                    PlaylistsScreen(open = { pc, name -> nav.navigate("playlist/${Uri.encode(pc)}/${Uri.encode(name)}") }, openPc = { nav.navigate("pair") })
                }
                composable(Tab.More.route) {
                    SettingsScreen(openPair = { nav.navigate("pair") }, openPc = { nav.navigate("pc/${Uri.encode(it)}") }, openPrivacy = { nav.navigate("privacy") }, toast = toast)
                }
                composable("pc/{id}", enterTransition = { slide() }, popExitTransition = { slideOut() }) {
                    PcScreen(Uri.decode(it.arguments?.getString("id").orEmpty()), back = { nav.popBackStack() }, toast = toast)
                }
                composable("song/{uid}", enterTransition = { slide() }, popExitTransition = { slideOut() }) {
                    SongScreen(Uri.decode(it.arguments?.getString("uid").orEmpty()), back = { nav.popBackStack() },
                        openSimilar = { t -> App.similarSeed.value = t; nav.navigate("similar") })
                }
                composable("playlist/{pc}/{name}", enterTransition = { slide() }, popExitTransition = { slideOut() }) {
                    PlaylistScreen(Uri.decode(it.arguments?.getString("pc").orEmpty()), Uri.decode(it.arguments?.getString("name").orEmpty()), back = { nav.popBackStack() },
                        openSimilar = { t -> App.similarSeed.value = t; nav.navigate("similar") })
                }
                composable("similar", enterTransition = { slide() }, popExitTransition = { slideOut() }) {
                    de.bs002.tunebridge.ui.screens.SimilarScreen(back = { nav.popBackStack() })
                }
                composable("pair", enterTransition = { slide() }, popExitTransition = { slideOut() }) {
                    PairScreen(back = { nav.popBackStack() }, done = { msg -> toast(msg); nav.popBackStack() })
                }
                composable("privacy", enterTransition = { slide() }, popExitTransition = { slideOut() }) { PrivacyScreen(back = { nav.popBackStack() }) }
            }
        }
        de.bs002.tunebridge.ui.components.MiniPlayer(if (tab == null) Modifier.windowInsetsPadding(WindowInsets.navigationBars) else Modifier)
        if (tab != null) BottomBar(tab) { nav.go(it) }
    }
}

private fun slide(): EnterTransition = slideInHorizontally { it / 5 } + fadeIn()
private fun slideOut(): ExitTransition = slideOutHorizontally { it / 5 } + fadeOut()

private fun NavHostController.go(t: Tab) = navigate(t.route) {
    popUpTo(Tab.Listen.route) { saveState = true }
    launchSingleTop = true
    restoreState = true
}

@Composable
private fun BottomBar(current: Tab, onSelect: (Tab) -> Unit) {
    Column(Modifier.background(Tb.bg1).windowInsetsPadding(WindowInsets.navigationBars)) {
        Hairline()
        Row(Modifier.fillMaxWidth().height(64.dp).padding(horizontal = 8.dp), verticalAlignment = Alignment.CenterVertically) {
            Tab.entries.forEach { t ->
                val on = t == current
                Column(
                    Modifier.weight(1f).clip(RoundedCornerShape(Tb.radius))
                        .clickable(remember { MutableInteractionSource() }, null) { onSelect(t) }.padding(vertical = 6.dp),
                    horizontalAlignment = Alignment.CenterHorizontally,
                ) {
                    Box(
                        Modifier.clip(RoundedCornerShape(50)).background(if (on) Tb.accentSoft else Tb.bg1).padding(horizontal = 18.dp, vertical = 4.dp),
                    ) { TbIcon(t.icon, if (on) Tb.accent else Tb.text3, 21.dp) }
                    Spacer(Modifier.height(3.dp))
                    Text(t.label, style = TbType.label.copy(letterSpacing = TbType.small.letterSpacing), color = if (on) Tb.text else Tb.text3)
                }
            }
        }
    }
}

