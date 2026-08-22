package com.mymoney.app.ui.screens.history

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.mymoney.app.data.model.TransactionResponse
import com.mymoney.app.ui.components.MoneyText
import com.mymoney.app.ui.theme.LocalExtendedColors
import com.mymoney.app.ui.theme.MyMoneyTypography
import kotlinx.coroutines.flow.distinctUntilChanged
import kotlinx.coroutines.flow.filter
import java.time.LocalDate
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(
    onNavigateToEdit: (String) -> Unit,
    viewModel: HistoryViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val listState = rememberLazyListState()

    // Trigger load more when reaching end of list
    LaunchedEffect(listState) {
        snapshotFlow { listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index }
            .filter { it != null && it >= state.transactions.size - 5 }
            .distinctUntilChanged()
            .collect {
                if (state.hasMore) viewModel.loadMore()
            }
    }

    var showDeleteConfirm by remember { mutableStateOf<TransactionResponse?>(null) }

    if (showDeleteConfirm != null) {
        AlertDialog(
            onDismissRequest = { showDeleteConfirm = null },
            title = { Text("Hapus Transaksi") },
            text = { Text("Yakin ingin menghapus transaksi ini? Saldo akun akan dikembalikan otomatis.") },
            confirmButton = {
                TextButton(
                    onClick = {
                        viewModel.deleteTransaction(showDeleteConfirm!!.id)
                        showDeleteConfirm = null
                    },
                    colors = ButtonDefaults.textButtonColors(contentColor = MaterialTheme.colorScheme.error)
                ) {
                    Text("Hapus")
                }
            },
            dismissButton = {
                TextButton(onClick = { showDeleteConfirm = null }) { Text("Batal") }
            }
        )
    }

    Scaffold { padding ->
        if (state.isLoading && state.transactions.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }

        // Group by date
        val grouped = state.transactions.groupBy {
            it.transactionDate.substringBefore("T")
        }

        LazyColumn(
            state = listState,
            modifier = Modifier.fillMaxSize().padding(padding),
        ) {
            item {
                Spacer(Modifier.height(24.dp))
                Text("Riwayat", style = MyMoneyTypography.headlineLarge, modifier = Modifier.padding(horizontal = 16.dp))
                Spacer(Modifier.height(16.dp))
            }

            grouped.forEach { (dateStr, txs) ->
                item {
                    val date = LocalDate.parse(dateStr)
                    val formattedDate = date.format(DateTimeFormatter.ofPattern("dd MMM yyyy"))
                    Text(
                        text = formattedDate,
                        style = MyMoneyTypography.labelMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.padding(horizontal = 16.dp, vertical = 8.dp)
                    )
                }

                items(txs, key = { it.id }) { tx ->
                    TransactionListItem(
                        tx = tx,
                        onClick = { onNavigateToEdit(tx.id) },
                        onDeleteClick = { showDeleteConfirm = tx }
                    )
                    HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                }
            }

            if (state.isLoadingMore) {
                item {
                    Box(Modifier.fillMaxWidth().padding(16.dp), contentAlignment = Alignment.Center) {
                        CircularProgressIndicator(modifier = Modifier.size(24.dp))
                    }
                }
            }
            item { Spacer(Modifier.height(80.dp)) }
        }
    }
}

@Composable
fun TransactionListItem(
    tx: TransactionResponse,
    onClick: () -> Unit,
    onDeleteClick: () -> Unit,
) {
    val extColors = LocalExtendedColors.current
    val isIncome = tx.type == "income"
    val color = if (isIncome) extColors.income else extColors.expense
    val sign = if (isIncome) "+" else "-"

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(horizontal = 16.dp, vertical = 12.dp),
        horizontalArrangement = Arrangement.SpaceBetween,
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = tx.merchant ?: tx.category.name,
                style = MyMoneyTypography.titleMedium,
            )
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    text = tx.category.name,
                    style = MyMoneyTypography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant
                )
                if (tx.note != null) {
                    Text(
                        text = " • ${tx.note}",
                        style = MyMoneyTypography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                    )
                }
            }
        }

        Column(horizontalAlignment = Alignment.End) {
            val amountStr = "Rp ${java.text.NumberFormat.getNumberInstance(java.util.Locale("id", "ID")).format(tx.totalAmount)}"
            Text(
                text = "$sign$amountStr",
                style = com.mymoney.app.ui.theme.MoneyTextStyle.medium,
                color = color
            )
            IconButton(
                onClick = onDeleteClick,
                modifier = Modifier.size(24.dp).padding(top = 4.dp)
            ) {
                Icon(
                    Icons.Outlined.Delete,
                    contentDescription = "Hapus",
                    tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    modifier = Modifier.size(16.dp)
                )
            }
        }
    }
}
