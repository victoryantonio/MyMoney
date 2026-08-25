package id.my.mymoney.ui.main

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ReceiptLong
import androidx.compose.material.icons.outlined.CameraAlt
import androidx.compose.material.icons.outlined.Dashboard
import androidx.compose.material.icons.outlined.Notifications
import androidx.compose.material.icons.outlined.Person
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.navigation.NavDestination.Companion.hierarchy
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.NavType
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import androidx.navigation.navArgument
import id.my.mymoney.data.model.UserResponse
import id.my.mymoney.ui.accounts.AccountDetailScreen
import id.my.mymoney.ui.accounts.AccountsScreen
import id.my.mymoney.ui.categories.CategoriesScreen
import id.my.mymoney.ui.dashboard.DashboardCategoryListScreen
import id.my.mymoney.ui.dashboard.DashboardScreen
import id.my.mymoney.ui.notifications.NotificationsScreen
import id.my.mymoney.ui.profile.ProfileScreen
import id.my.mymoney.ui.receipt.ReceiptCaptureScreen
import id.my.mymoney.ui.transactions.TransactionFormScreen
import id.my.mymoney.ui.transactions.TransactionsScreen

object Routes {
    const val DASHBOARD = "dashboard"
    const val TRANSACTIONS = "transactions"
    const val NOTIFICATIONS = "notifications"
    const val PROFILE = "profile"
    const val CATEGORIES = "categories"
    const val ACCOUNTS = "accounts"
    const val ACCOUNT_DETAIL = "account_detail/{accountId}"
    const val RECEIPT_CAPTURE = "receipt_capture"
    fun accountDetail(id: String) = "account_detail/$id"
    const val CATEGORY_LIST = "category_list?type={type}"
    const val TRANSACTION_FORM = "transaction_form?txId={txId}&type={type}"
    fun transactionForm(txId: String?, type: String? = null) =
        "transaction_form?txId=${txId ?: ""}&type=${type ?: ""}"
    fun categoryList(type: String) = "category_list?type=$type"
}

private data class BottomTab(val route: String, val label: String, val icon: ImageVector)

// Menu utama (DESIGN.md §8.5): Dashboard, Transactions, Notifications, Profile.
private val tabs = listOf(
    BottomTab(Routes.DASHBOARD, "Dashboard", Icons.Outlined.Dashboard),
    BottomTab(Routes.TRANSACTIONS, "Transactions", Icons.AutoMirrored.Outlined.ReceiptLong),
    BottomTab(Routes.NOTIFICATIONS, "Notifications", Icons.Outlined.Notifications),
    BottomTab(Routes.PROFILE, "Profile", Icons.Outlined.Person),
)

@Composable
fun MainScreen(user: UserResponse, onLogout: () -> Unit) {
    val navController = rememberNavController()
    val backStackEntry by navController.currentBackStackEntryAsState()
    val currentDestination = backStackEntry?.destination

    val isTabDestination = tabs.any { tab ->
        currentDestination?.hierarchy?.any { it.route == tab.route } == true
    }

    Scaffold(
        bottomBar = {
            if (isTabDestination) {
                NavigationBar {
                    tabs.forEachIndexed { index, tab ->
                        val selected =
                            currentDestination?.hierarchy?.any { it.route == tab.route } == true
                        if (index == 1) {
                            // Ikon Foto di antara Transactions & Notifications:
                            // aksi capture nota, bukan tab.
                            CameraAction(
                                onClick = { navController.navigate(Routes.RECEIPT_CAPTURE) },
                            )
                        }
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
                    onOpenTransactions = {
                        navController.navigate(Routes.TRANSACTIONS) {
                            popUpTo(navController.graph.findStartDestination().id) { saveState = true }
                            launchSingleTop = true
                            restoreState = true
                        }
                    },
                    onOpenCategoryList = { type -> navController.navigate(Routes.categoryList(type)) },
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
            composable(Routes.NOTIFICATIONS) {
                NotificationsScreen()
            }
            composable(Routes.PROFILE) {
                ProfileScreen(
                    user = user,
                    onLogout = onLogout,
                    onOpenCategories = { navController.navigate(Routes.CATEGORIES) },
                    onOpenAccounts = { navController.navigate(Routes.ACCOUNTS) },
                )
            }
            composable(Routes.CATEGORIES) {
                CategoriesScreen()
            }
            composable(Routes.ACCOUNTS) {
                AccountsScreen(
                    onOpenDetail = { id -> navController.navigate(Routes.accountDetail(id)) },
                )
            }
            composable(
                route = Routes.ACCOUNT_DETAIL,
                arguments = listOf(
                    navArgument("accountId") { type = NavType.StringType },
                ),
            ) { entry ->
                AccountDetailScreen(
                    accountId = entry.arguments?.getString("accountId") ?: "",
                    onDone = { navController.popBackStack() },
                )
            }
            composable(
                route = Routes.CATEGORY_LIST,
                arguments = listOf(
                    navArgument("type") { type = NavType.StringType; defaultValue = "expense" },
                ),
            ) { entry ->
                val type = entry.arguments?.getString("type") ?: "expense"
                DashboardCategoryListScreen(
                    type = type,
                    onEditTransaction = { txId -> navController.navigate(Routes.transactionForm(txId)) },
                    onBack = { navController.popBackStack() },
                )
            }
            composable(Routes.RECEIPT_CAPTURE) {
                ReceiptCaptureScreen(
                    onDone = {
                        navController.previousBackStackEntry
                            ?.savedStateHandle
                            ?.set("tx_changed", true)
                        navController.popBackStack()
                    },
                    onOpenForm = { txId, type ->
                        navController.navigate(Routes.transactionForm(txId, type))
                    },
                )
            }
        }
    }
}

/** Tombol kamera melingkar di tengah bottom bar (aksi capture nota). */
@Composable
private fun CameraAction(onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .padding(horizontal = 4.dp)
            .size(44.dp)
            .clip(CircleShape)
            .background(MaterialTheme.colorScheme.primaryContainer)
            .clickable(onClick = onClick),
        contentAlignment = Alignment.Center,
    ) {
        Icon(
            Icons.Outlined.CameraAlt,
            contentDescription = "Capture receipt",
            tint = MaterialTheme.colorScheme.primary,
            modifier = Modifier.size(24.dp),
        )
    }
}

