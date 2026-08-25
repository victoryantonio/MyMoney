package id.my.mymoney.ui.navigation

import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.data.AuthState
import id.my.mymoney.ui.auth.AuthScreen
import id.my.mymoney.ui.auth.AuthViewModel
import id.my.mymoney.ui.components.LoadingView
import id.my.mymoney.ui.main.MainScreen

/**
 * Top-level navigation: shows the auth screen until the user is authenticated,
 * then the main app (dashboard / transactions / categories / accounts).
 */
@Composable
fun AppNavHost(modifier: Modifier = Modifier) {
    val authViewModel: AuthViewModel = viewModel(factory = AuthViewModel.Factory)
    val authState by authViewModel.authState.collectAsStateWithLifecycle()

    when (val state = authState) {
        is AuthState.Authenticated -> MainScreen(onLogout = { authViewModel.logout() })
        is AuthState.Loading -> LoadingView(modifier)
        is AuthState.Unknown -> LoadingView(modifier)
        is AuthState.Unauthenticated -> AuthScreen(
            viewModel = authViewModel,
            onAuthenticated = {},
        )
    }
}
