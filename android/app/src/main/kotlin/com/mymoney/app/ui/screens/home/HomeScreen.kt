package com.mymoney.app.ui.screens.home

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.mymoney.app.data.model.AccountResponse
import com.mymoney.app.ui.components.MoneyText
import com.mymoney.app.ui.theme.LocalExtendedColors
import com.mymoney.app.ui.theme.MyMoneyTypography

@Composable
fun HomeScreen(
    onNavigateToForm: () -> Unit,
    viewModel: HomeViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val extColors = LocalExtendedColors.current

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(onClick = onNavigateToForm) {
                Icon(Icons.Outlined.Add, contentDescription = "Catat Transaksi")
            }
        }
    ) { padding ->
        if (state.isLoading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            item {
                Spacer(Modifier.height(24.dp))
                Text("Beranda", style = MyMoneyTypography.headlineLarge)
                Spacer(Modifier.height(20.dp))
            }

            // Total balance card
            item {
                val totalBalance = state.accounts.sumOf { it.currentBalance }
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
                ) {
                    Column(Modifier.padding(20.dp)) {
                        Text("Total Saldo", style = MyMoneyTypography.labelMedium)
                        Spacer(Modifier.height(4.dp))
                        MoneyText(
                            amount = totalBalance,
                            style = com.mymoney.app.ui.theme.MoneyTextStyle.display,
                        )
                    }
                }
            }

            // Month summary
            state.summary?.let { summary ->
                item {
                    Row(
                        Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        // Income card
                        Card(Modifier.weight(1f)) {
                            Column(Modifier.padding(16.dp)) {
                                Text("Pemasukan", style = MyMoneyTypography.labelSmall)
                                Spacer(Modifier.height(4.dp))
                                MoneyText(
                                    amount = summary.totalIncome,
                                    color = extColors.income,
                                    style = com.mymoney.app.ui.theme.MoneyTextStyle.medium,
                                )
                            }
                        }
                        // Expense card
                        Card(Modifier.weight(1f)) {
                            Column(Modifier.padding(16.dp)) {
                                Text("Pengeluaran", style = MyMoneyTypography.labelSmall)
                                Spacer(Modifier.height(4.dp))
                                MoneyText(
                                    amount = summary.totalExpense,
                                    color = extColors.expense,
                                    style = com.mymoney.app.ui.theme.MoneyTextStyle.medium,
                                )
                            }
                        }
                    }
                }
            }

            // Accounts list header
            item {
                Spacer(Modifier.height(8.dp))
                Text("Akun", style = MyMoneyTypography.titleLarge)
            }

            items(state.accounts.filter { it.isActive }) { account ->
                AccountSummaryCard(account = account)
            }

            item { Spacer(Modifier.height(80.dp)) }
        }
    }
}

@Composable
private fun AccountSummaryCard(account: AccountResponse) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Row(
            Modifier.padding(16.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column {
                Text(account.accountName, style = MyMoneyTypography.titleMedium)
                account.bankName?.let {
                    Text(it, style = MyMoneyTypography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            MoneyText(
                amount = account.currentBalance,
                style = com.mymoney.app.ui.theme.MoneyTextStyle.medium,
            )
        }
    }
}
