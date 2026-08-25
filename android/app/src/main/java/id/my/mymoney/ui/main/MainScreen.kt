package id.my.mymoney.ui.main

import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ReceiptLong
import androidx.compose.material.icons.outlined.AccountBalance
import androidx.compose.material.icons.outlined.Category
import androidx.compose.material.icons.outlined.Dashboard
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import id.my.mymoney.ui.accounts.AccountsScreen
import id.my.mymoney.ui.categories.CategoriesScreen
import id.my.mymoney.ui.dashboard.DashboardScreen
import id.my.mymoney.ui.transactions.TransactionFormScreen
import id.my.mymoney.ui.transactions.TransactionsScreen

object Routes {
    const val DASHBOARD = "dashboard"
    const val TRANSACTIONS = "transactions"
    const val CATEGORIES = "categories"
    const val ACCOUNTS = "accounts"
    const val TRANSACTION_FORM = "transaction_form?txId={txId}&type={type}"
    fun transactionForm(txId: String?, type: String? = null) =
        "transaction_form?txId=${txId ?: ""}&type=${type ?: ""}"
}

private data class BottomTab(val route: String, val label: String, val icon: androidx.compose.ui.graphics.vector.ImageVector)

private val tabs = listOf(
    BottomTab(Routes.DASHBOARD, "Dashboard", Icons.Outlined.Dashboard),
    BottomTab(Routes.TRANSACTIONS, "Transactions", Icons.AutoMirrored.Outlined.ReceiptLong),
    BottomTab(Routes.CATEGORIES, "Categories", Icons.Outlined.Category),
    BottomTab(Routes.ACCOUNTS, "Accounts", Icons.Outlined.AccountBalance),
)

@Composable
fun MainScreen(onLogout: () -> Unit) {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = backStackEntry?.destination

    Scaffold(
        bottomBar = {
            NavigationBar {
                tabs.forEach { tab ->
                    val selected = currentDestination?.hierarchy?.any { it.route == tab.route } == true
                    NavigationBarItem(
                        selected = selected,
                        onClick = {
                            navController.navigate(tab.route) {
                                popUpTo(navController.graph.findStartDestination().id) {
                                    saveState = true
                                }
                                launchSingleTop = true
                                restoreState = true
                            }
                        },
                        icon = { Icon(tab.icon, contentDescription = tab.label) },
                        label = { Text(tab.label) },
                    )
                }
            }
        },
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Routes.DASHBOARD,
            modifier = Modifier.padding(innerPadding),
        ) {
            composable(Routes.DASHBOARD) {
                DashboardScreen(
                    onLogout = onLogout,
                    onAddExpense = { navController.navigate(Routes.transactionForm(null)) },
                    onAddIncome = { navController.navigate(Routes.transactionForm(null, "income")) },
                    onOpenTransactions = {
                        navController.navigate(Routes.TRANSACTIONS) {
                            popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                    onEditTransaction = { txId -> navController.navigate(Routes.transactionForm(txId)) },
                )
            }
            composable(Routes.TRANSACTIONS) { entry ->
                val refresh by entry.savedStateHandle
                    .getStateFlow("tx_changed", false)
                    .collectAsStateWithLifecycle()
                TransactionsScreen(
                    refreshTrigger = refresh,
                    onAdd = { navController.navigate(Routes.transactionForm(null)) },
                    onEdit = { txId -> navController.navigate(Routes.transactionForm(txId)) },
                )
            }
            composable(
                route = Routes.TRANSACTION_FORM,
                arguments = listOf(
                    navArgument("txId") { type = NavType.StringType; defaultValue = "" },
                    navArgument("type") { type = NavType.StringType; defaultValue = "" },
                ),
            ) { entry ->
                TransactionFormScreen(
                    txId = entry.arguments?.getString("txId")?.takeIf { it.isNotBlank() },
                    initialType = entry.arguments?.getString("type")?.takeIf { it.isNotBlank() },
                    onDone = {
                        navController.previousBackStackEntry
                            ?.savedStateHandle
                            ?.set("tx_changed", true)
                        navController.popBackStack()
                    },
                )
            }
            composable(Routes.CATEGORIES) {
                CategoriesScreen()
            }
            composable(Routes.ACCOUNTS) {
                AccountsScreen()
            }
        }
    }
}
