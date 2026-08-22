package com.mymoney.app.ui.navigation

sealed class Screen(val route: String) {
    object Login : Screen("login")
    object Register : Screen("register")
    object Home : Screen("home")
    object History : Screen("history")
    object Report : Screen("report")
    object Accounts : Screen("accounts")
    object Categories : Screen("categories")
    object TransactionForm : Screen("transaction_form?editId={editId}") {
        fun route(editId: String? = null) =
            if (editId != null) "transaction_form?editId=$editId" else "transaction_form"
    }
}

// Bottom nav items — Home, History, Report, Accounts
data class BottomNavItem(val screen: Screen, val label: String, val iconName: String)

val bottomNavItems = listOf(
    BottomNavItem(Screen.Home, "Beranda", "home"),
    BottomNavItem(Screen.History, "Riwayat", "receipt_long"),
    BottomNavItem(Screen.Report, "Laporan", "bar_chart"),
    BottomNavItem(Screen.Accounts, "Akun", "account_balance_wallet"),
)
