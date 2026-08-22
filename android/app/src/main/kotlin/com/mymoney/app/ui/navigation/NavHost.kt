package com.mymoney.app.ui.navigation

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.*
import androidx.compose.material.icons.automirrored.outlined.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.*
import androidx.navigation.navArgument
import com.mymoney.app.data.local.TokenStore
import com.mymoney.app.ui.screens.account.AccountScreen
import com.mymoney.app.ui.screens.auth.LoginScreen
import com.mymoney.app.ui.screens.auth.RegisterScreen
import com.mymoney.app.ui.screens.history.HistoryScreen
import com.mymoney.app.ui.screens.home.HomeScreen
import com.mymoney.app.ui.screens.report.ReportScreen
import com.mymoney.app.ui.screens.transaction.TransactionFormScreen
import kotlinx.coroutines.flow.first

@Composable
fun MyMoneyNavHost(tokenStore: TokenStore) {
    val navController = rememberNavController()
    val currentBackStack by navController.currentBackStackEntryAsState()
    val currentRoute = currentBackStack?.destination?.route

    // Check initial auth state
    var startDestination by remember { mutableStateOf<String?>(null) }
    LaunchedEffect(Unit) {
        val token = tokenStore.accessToken.first()
        startDestination = if (token != null) Screen.Home.route else Screen.Login.route
    }

    if (startDestination == null) {
        // Splash / loading
        Surface { CircularProgressIndicator() }
        return
    }

    val showBottomBar = currentRoute in bottomNavItems.map { it.screen.route }

    Scaffold(
        bottomBar = {
            if (showBottomBar) {
                NavigationBar {
                    bottomNavItems.forEach { item ->
                        val selected = currentRoute == item.screen.route
                        NavigationBarItem(
                            selected = selected,
                            onClick = {
                                navController.navigate(item.screen.route) {
                                    popUpTo(navController.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            label = { Text(item.label) },
                            icon = {
                                Icon(
                                    imageVector = when (item.iconName) {
                                        "home" -> Icons.Outlined.Home
                                        "receipt_long" -> Icons.AutoMirrored.Outlined.ReceiptLong
                                        "bar_chart" -> Icons.Outlined.BarChart
                                        else -> Icons.Outlined.AccountBalanceWallet
                                    },
                                    contentDescription = item.label,
                                )
                            },
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = startDestination!!,
            modifier = Modifier.padding(innerPadding),
        ) {
            composable(Screen.Login.route) {
                LoginScreen(
                    onNavigateToRegister = { navController.navigate(Screen.Register.route) },
                    onLoginSuccess = {
                        navController.navigate(Screen.Home.route) {
                            popUpTo(Screen.Login.route) { inclusive = true }
                        }
                    },
                )
            }
            composable(Screen.Register.route) {
                RegisterScreen(
                    onNavigateToLogin = { navController.popBackStack() },
                    onRegisterSuccess = {
                        navController.navigate(Screen.Home.route) {
                            popUpTo(Screen.Login.route) { inclusive = true }
                        }
                    },
                )
            }
            composable(Screen.Home.route) {
                HomeScreen(
                    onNavigateToForm = { navController.navigate(Screen.TransactionForm.route()) },
                )
            }
            composable(Screen.History.route) {
                HistoryScreen(
                    onNavigateToEdit = { id ->
                        navController.navigate(Screen.TransactionForm.route(id))
                    },
                )
            }
            composable(Screen.Report.route) {
                ReportScreen()
            }
            composable(Screen.Accounts.route) {
                AccountScreen()
            }
            composable(
                route = Screen.TransactionForm.route,
                arguments = listOf(navArgument("editId") {
                    type = NavType.StringType
                    nullable = true
                    defaultValue = null
                }),
            ) { backStackEntry ->
                val editId = backStackEntry.arguments?.getString("editId")
                TransactionFormScreen(
                    editId = editId,
                    onSaved = { navController.popBackStack() },
                    onCancel = { navController.popBackStack() },
                )
            }
        }
    }
}
