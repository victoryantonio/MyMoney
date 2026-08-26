package id.my.mymoney.ui.dashboard

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material.icons.outlined.ArrowDownward
import androidx.compose.material.icons.outlined.ArrowUpward
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.data.model.CategoryTotal
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.ui.components.EmptyState
import id.my.mymoney.ui.components.ErrorView
import id.my.mymoney.ui.components.LoadingView
import id.my.mymoney.ui.theme.ExpenseRed
import id.my.mymoney.ui.theme.IncomeGreen
import id.my.mymoney.ui.theme.MoneyMedium
import id.my.mymoney.ui.theme.MoneySmall
import id.my.mymoney.util.Formatters
import java.math.BigDecimal

/**
 * Daftar kategori per tipe (income/expense) — dibuka dari tap card Income/
 * Expense di Dashboard. Menampilkan ringkasan tiap kategori + transaksinya.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardCategoryListScreen(
    type: String,
    onEditTransaction: (String) -> Unit,
    onBack: (() -> Unit)? = null,
    viewModel: DashboardCategoryListViewModel = viewModel(
        factory = DashboardCategoryListViewModel.factory(type),
    ),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val isExpense = type == "expense"
    val isIncome = type == "income"
    val accent = if (isExpense) ExpenseRed else IncomeGreen
    val title = when {
        isExpense -> "Expense Categories"
        isIncome -> "Income Categories"
        else -> "All Categories"
    }
    // Sort kategori by nominal (Phase 6): default tertinggi ke terendah (desc).
    var sortAsc by rememberSaveable { mutableStateOf(false) }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(title) },
                navigationIcon = {
                    IconButton(onClick = { onBack?.invoke() }) {
                        Icon(Icons.Outlined.ArrowBack, contentDescription = "Back")
                    }
                },
                actions = {
                    IconButton(onClick = { sortAsc = !sortAsc }) {
                        Icon(
                            if (sortAsc) Icons.Outlined.ArrowUpward
                            else Icons.Outlined.ArrowDownward,
                            contentDescription = if (sortAsc) "Sort ascending" else "Sort descending",
                        )
                    }
                },
            )
        },
    ) { innerPadding ->
        when {
            state.loading && state.summary == null -> LoadingView(Modifier.padding(innerPadding))
            state.error != null && state.summary == null ->
                ErrorView(state.error, onRetry = { viewModel.refresh() }, modifier = Modifier.padding(innerPadding))
            else -> {
                val summary = state.summary
                val cats = summary?.categories
                    ?.filter { it.type == type || type == "all" }
                    ?.let { list ->
                        if (sortAsc) {
                            list.sortedBy { it.totalDecimal }
                        } else {
                            list.sortedByDescending { it.totalDecimal }
                        }
                    }
                    .orEmpty()
                LazyColumn(
                    modifier = Modifier
                        .fillMaxSize()
                        .padding(innerPadding),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item {
                        val total = if (isExpense) summary?.expense ?: BigDecimal.ZERO
                        else summary?.income ?: BigDecimal.ZERO
                        CategoryTotalCard(total = total, accent = accent)
                    }
                    if (cats.isEmpty()) {
                        item {
                            EmptyState("No $title yet", modifier = Modifier.height(140.dp))
                        }
                    } else {
                        val max = cats.maxOfOrNull { it.totalDecimal } ?: BigDecimal.ONE
                        items(cats.size) { i ->
                            CategorySummaryRow(cat = cats[i], accent = accent, max = max)
                        }
                    }
                    item {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            "Transactions",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                        )
                    }
                    if (state.transactions.isEmpty()) {
                        item {
                            EmptyState("No transactions yet", modifier = Modifier.height(100.dp))
                        }
                    } else {
                        items(state.transactions.size) { i ->
                            val tx = state.transactions[i]
                            TransactionRow(tx = tx, onClick = { onEditTransaction(tx.id) })
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun CategoryTotalCard(total: BigDecimal, accent: Color) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text(
                "Total",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                Formatters.idr(total),
                style = MoneyMedium,
                color = accent,
            )
        }
    }
}

@Composable
private fun CategorySummaryRow(cat: CategoryTotal, accent: Color, max: BigDecimal) {
    val fraction = (cat.totalDecimal / max).toFloat().coerceIn(0f, 1f)
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Text(
                    cat.name,
                    style = MaterialTheme.typography.bodyMedium,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.weight(1f),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    Formatters.idr(cat.totalDecimal),
                    style = MoneySmall,
                    color = accent,
                    textAlign = TextAlign.End,
                )
            }
            Spacer(Modifier.height(8.dp))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .width(8.dp)
                        .height(8.dp)
                        .clip(CircleShape)
                        .background(accent),
                )
                Spacer(Modifier.width(8.dp))
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(6.dp)
                        .clip(RoundedCornerShape(3.dp))
                        .background(MaterialTheme.colorScheme.outline),
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth(fraction)
                            .height(6.dp)
                            .background(accent, RoundedCornerShape(3.dp)),
                    )
                }
            }
        }
    }
}

@Composable
private fun TransactionRow(tx: TransactionResponse, onClick: () -> Unit) {
    val color = if (tx.isExpense) ExpenseRed else IncomeGreen
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .clickable(onClick = onClick)
            .padding(vertical = 10.dp, horizontal = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Box(
            modifier = Modifier
                .size(8.dp)
                .clip(CircleShape)
                .background(color),
        )
        Spacer(Modifier.width(12.dp))
        Column(modifier = Modifier.weight(1f)) {
            Text(
                tx.merchant ?: tx.note ?: (if (tx.isExpense) "Expense" else "Income"),
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                Formatters.date(tx.transaction_date),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        Spacer(Modifier.width(8.dp))
        Text(
            Formatters.idr(tx.totalAmountDecimal),
            style = MoneySmall,
            color = color,
            textAlign = TextAlign.End,
            maxLines = 1,
            overflow = TextOverflow.Visible,
        )
    }
}
