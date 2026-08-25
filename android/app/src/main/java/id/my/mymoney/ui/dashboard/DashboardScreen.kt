package id.my.mymoney.ui.dashboard

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.data.model.CategoryTotal
import id.my.mymoney.data.model.ReportSummaryResponse
import id.my.mymoney.ui.components.EmptyState
import id.my.mymoney.ui.components.ErrorView
import id.my.mymoney.ui.components.LoadingView
import id.my.mymoney.ui.theme.ExpenseRed
import id.my.mymoney.ui.theme.IncomeGreen
import id.my.mymoney.ui.theme.NetBlue
import id.my.mymoney.util.Formatters
import java.math.BigDecimal

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(onLogout: () -> Unit, viewModel: DashboardViewModel = viewModel(factory = DashboardViewModel.Factory)) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Dashboard") },
                actions = {
                    IconButton(onClick = onLogout) {
                        Icon(Icons.AutoMirrored.Filled.Logout, contentDescription = "Logout")
                    }
                },
            )
        },
    ) { innerPadding ->
        Column(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            // Period selector
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                ReportPeriod.entries.forEach { period ->
                    FilterChip(
                        selected = state.period == period,
                        onClick = { viewModel.selectPeriod(period) },
                        label = { Text(period.label) },
                    )
                }
            }

            when {
                state.loading && state.summary == null -> LoadingView()
                state.error != null && state.summary == null ->
                    ErrorView(state.error, onRetry = { viewModel.refresh() })
                state.summary != null -> {
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp),
                    ) {
                        item { SummaryCards(state.summary!!) }
                        item { CategoryBreakdown(state.summary!!) }
                    }
                }
            }
        }
    }
}

@Composable
private fun SummaryCards(summary: ReportSummaryResponse) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        SummaryCard("Income", summary.income, IncomeGreen, Modifier.weight(1f))
        SummaryCard("Expense", summary.expense, ExpenseRed, Modifier.weight(1f))
        SummaryCard("Net", summary.netDecimal, NetBlue, Modifier.weight(1f))
    }
}

@Composable
private fun SummaryCard(label: String, amount: BigDecimal, color: Color, modifier: Modifier = Modifier) {
    Card(
        modifier = modifier,
        colors = CardDefaults.cardColors(containerColor = color.copy(alpha = 0.12f)),
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
            Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Spacer(Modifier.height(4.dp))
            Text(
                Formatters.idr(amount),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = color,
                maxLines = 1,
            )
        }
    }
}

@Composable
private fun CategoryBreakdown(summary: ReportSummaryResponse) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text("By category", style = MaterialTheme.typography.titleMedium, fontWeight = FontWeight.SemiBold)
            Spacer(Modifier.height(8.dp))

            val categories = summary.categories
            if (categories.isEmpty()) {
                EmptyState("No transactions in this period", modifier = Modifier.height(120.dp))
                return@Card
            }

            // Expense bars (most finance apps focus on expense breakdown).
            val expenseCats = categories.filter { it.type == "expense" }
            val incomeCats = categories.filter { it.type == "income" }

            if (expenseCats.isNotEmpty()) {
                Text("Expenses", style = MaterialTheme.typography.labelLarge, color = ExpenseRed)
                Spacer(Modifier.height(6.dp))
                BarChart(expenseCats, ExpenseRed)
            }
            if (incomeCats.isNotEmpty()) {
                Spacer(Modifier.height(12.dp))
                Text("Income", style = MaterialTheme.typography.labelLarge, color = IncomeGreen)
                Spacer(Modifier.height(6.dp))
                BarChart(incomeCats, IncomeGreen)
            }
        }
    }
}

/** Simple proportional horizontal bar chart (Vico-free, zero extra deps). */
@Composable
private fun BarChart(cats: List<CategoryTotal>, color: Color) {
    val max = cats.maxOfOrNull { it.totalDecimal } ?: BigDecimal.ONE
    androidx.compose.foundation.layout.BoxWithConstraints(modifier = Modifier.fillMaxWidth()) {
        val maxWidthPx = maxWidth
        cats.forEach { cat ->
            val fraction = (cat.totalDecimal / max).toFloat().coerceIn(0f, 1f)
            Row(
                modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    cat.name,
                    style = MaterialTheme.typography.bodyMedium,
                    modifier = Modifier.width(110.dp),
                    maxLines = 1,
                )
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .height(10.dp)
                        .background(
                            color = MaterialTheme.colorScheme.surfaceVariant,
                            shape = RoundedCornerShape(5.dp),
                        ),
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth(fraction)
                            .height(10.dp)
                            .background(color, shape = RoundedCornerShape(5.dp)),
                    )
                }
                Spacer(Modifier.width(8.dp))
                Text(
                    Formatters.idr(cat.totalDecimal),
                    style = MaterialTheme.typography.bodySmall,
                    fontWeight = FontWeight.Medium,
                    maxLines = 1,
                )
            }
        }
    }
}
