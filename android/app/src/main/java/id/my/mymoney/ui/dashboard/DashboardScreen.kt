package id.my.mymoney.ui.dashboard

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
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
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Logout
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.outlined.ArrowDownward
import androidx.compose.material.icons.outlined.ArrowUpward
import androidx.compose.material.icons.outlined.History
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.data.model.CategoryTotal
import id.my.mymoney.data.model.ReportSummaryResponse
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.ui.components.EmptyState
import id.my.mymoney.ui.components.ErrorView
import id.my.mymoney.ui.components.LoadingView
import id.my.mymoney.ui.theme.ExpenseRed
import id.my.mymoney.ui.theme.IncomeGreen
import id.my.mymoney.ui.theme.MoneyDisplay
import id.my.mymoney.ui.theme.MoneyMedium
import id.my.mymoney.ui.theme.MoneySmall
import id.my.mymoney.ui.theme.NetBlue
import id.my.mymoney.util.Formatters
import java.math.BigDecimal
import kotlin.math.atan2
import kotlin.math.sqrt

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun DashboardScreen(
    onLogout: () -> Unit,
    onAddExpense: () -> Unit,
    onAddIncome: () -> Unit,
    onOpenTransactions: () -> Unit,
    onEditTransaction: (String) -> Unit,
    viewModel: DashboardViewModel = viewModel(factory = DashboardViewModel.Factory),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()

    // Filter kategori aktif dari tap donut/legend (§8.4) — state lokal, tanpa network call.
    var selectedCategory by remember { mutableStateOf<String?>(null) }
    val filteredTransactions = remember(state.recentTransactions, selectedCategory) {
        val nameOf = state.categories.associate { it.id to it.name }
        if (selectedCategory == null) {
            state.recentTransactions
        } else {
            state.recentTransactions.filter { nameOf[it.category_id] == selectedCategory }
        }
    }

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
        floatingActionButton = {
            FloatingActionButton(onClick = onAddExpense) {
                Icon(Icons.Filled.Add, contentDescription = "Add transaction")
            }
        },
    ) { innerPadding ->
        Column(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            PeriodSelector(period = state.period, onSelect = viewModel::selectPeriod)

            when {
                state.loading && state.summary == null && state.accounts.isEmpty() -> LoadingView()
                state.error != null && state.summary == null && state.accounts.isEmpty() ->
                    ErrorView(state.error, onRetry = { viewModel.refresh() })
                else -> LazyColumn(
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    item { BalanceCard(totalBalance = state.totalBalance) }
                    item {
                        QuickActionRow(
                            onExpense = onAddExpense,
                            onIncome = onAddIncome,
                            onHistory = onOpenTransactions,
                        )
                    }
                    if (state.summary != null) {
                        item { SummaryCards(state.summary!!) }
                        item {
                            CategoryBreakdownCard(
                                summary = state.summary!!,
                                selectedCategory = selectedCategory,
                                onCategorySelect = { name ->
                                    selectedCategory = if (selectedCategory == name) null else name
                                },
                                recentTransactions = filteredTransactions,
                                onTransactionClick = onEditTransaction,
                            )
                        }
                    }
                }
            }
        }
    }
}

// ── Period selector (DESIGN.md §8.4) ────────────────────────────────────────
// Segmented control: lebar tetap per opsi + horizontalScroll. Tidak pernah
// terpotong di layar sempit (fix BUG 1: chip wrapContentWidth tanpa scroll).
@Composable
private fun PeriodSelector(period: ReportPeriod, onSelect: (ReportPeriod) -> Unit) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 16.dp, vertical = 8.dp)
            .clip(RoundedCornerShape(8.dp))
            .background(MaterialTheme.colorScheme.surfaceVariant)
            .padding(4.dp)
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        ReportPeriod.entries.forEach { option ->
            val selected = option == period
            Box(
                modifier = Modifier
                    .widthIn(min = 84.dp)
                    .clip(RoundedCornerShape(8.dp))
                    .background(
                        if (selected) MaterialTheme.colorScheme.primaryContainer else Color.Transparent,
                    )
                    .clickable { onSelect(option) }
                    .padding(horizontal = 12.dp, vertical = 8.dp),
                contentAlignment = Alignment.Center,
            ) {
                Text(
                    option.label,
                    style = MaterialTheme.typography.labelLarge,
                    color = if (selected) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.onSurfaceVariant
                    },
                    maxLines = 1,
                )
            }
        }
    }
}

// ── Saldo total (DESIGN.md §8.1) ────────────────────────────────────────────
@Composable
private fun BalanceCard(totalBalance: BigDecimal) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.primaryContainer),
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(20.dp)) {
            Text(
                "Total Balance",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                Formatters.idr(totalBalance),
                style = MoneyDisplay,
                color = MaterialTheme.colorScheme.onSurface,
                maxLines = 1,
                overflow = TextOverflow.Visible,
            )
        }
    }
}

// ── Quick actions (icon Material Symbols outlined) ──────────────────────────
@Composable
private fun QuickActionRow(
    onExpense: () -> Unit,
    onIncome: () -> Unit,
    onHistory: () -> Unit,
) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(12.dp)) {
        QuickAction("Expense", Icons.Outlined.ArrowDownward, ExpenseRed, onExpense, Modifier.weight(1f))
        QuickAction("Income", Icons.Outlined.ArrowUpward, IncomeGreen, onIncome, Modifier.weight(1f))
        QuickAction("History", Icons.Outlined.History, MaterialTheme.colorScheme.primary, onHistory, Modifier.weight(1f))
    }
}

@Composable
private fun QuickAction(
    label: String,
    icon: ImageVector,
    tint: Color,
    onClick: () -> Unit,
    modifier: Modifier = Modifier,
) {
    Card(
        modifier = modifier.clip(RoundedCornerShape(12.dp)).clickable(onClick = onClick),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(vertical = 12.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Box(
                modifier = Modifier
                    .size(40.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primaryContainer),
                contentAlignment = Alignment.Center,
            ) {
                Icon(icon, contentDescription = label, tint = tint, modifier = Modifier.size(20.dp))
            }
            Spacer(Modifier.height(6.dp))
            Text(label, style = MaterialTheme.typography.labelMedium, color = MaterialTheme.colorScheme.onSurface)
        }
    }
}

// ── Ringkasan Income/Expense/Net ────────────────────────────────────────────
// Card berbagi lebar proporsional (weight(1f)) — tidak ada lebar tetap yang
// menyempit. Nominal IBM Plex Mono maxLines=1 overflow Visible + autoSize:
// data finansial tidak boleh terpotong (diuji dengan nilai 7 digit).
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
            Text(
                label,
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                Formatters.idr(amount),
                style = MoneyMedium,
                color = color,
                textAlign = TextAlign.End,
                maxLines = 1,
                overflow = TextOverflow.Visible,
                softWrap = false,
            )
        }
    }
}

// ── Breakdown kategori + donut + transaksi terfilter (DESIGN.md §8.4) ───────
@Composable
private fun CategoryBreakdownCard(
    summary: ReportSummaryResponse,
    selectedCategory: String?,
    onCategorySelect: (String) -> Unit,
    recentTransactions: List<TransactionResponse>,
    onTransactionClick: (String) -> Unit,
) {
    Card(modifier = Modifier.fillMaxWidth()) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
            Text(
                "By category",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(12.dp))

            val expenseCats = summary.categories.filter { it.type == "expense" }
            val incomeCats = summary.categories.filter { it.type == "income" }

            if (expenseCats.isEmpty() && incomeCats.isEmpty()) {
                EmptyState("No transactions in this period", modifier = Modifier.height(120.dp))
                return@Card
            }

            if (expenseCats.isNotEmpty()) {
                DonutChart(
                    cats = expenseCats,
                    selectedCategory = selectedCategory,
                    onSelect = onCategorySelect,
                )
                Spacer(Modifier.height(12.dp))
            }

            val expenseMax = expenseCats.maxOfOrNull { it.totalDecimal } ?: BigDecimal.ONE
            expenseCats.forEach { cat ->
                CategoryRow(
                    cat = cat,
                    color = ExpenseRed,
                    max = expenseMax,
                    selected = selectedCategory == cat.name,
                    onClick = { onCategorySelect(cat.name) },
                )
            }

            if (incomeCats.isNotEmpty()) {
                Spacer(Modifier.height(8.dp))
                Text("Income", style = MaterialTheme.typography.labelLarge, color = IncomeGreen)
                Spacer(Modifier.height(4.dp))
                val incomeMax = incomeCats.maxOfOrNull { it.totalDecimal } ?: BigDecimal.ONE
                incomeCats.forEach { cat ->
                    CategoryRow(
                        cat = cat,
                        color = IncomeGreen,
                        max = incomeMax,
                        selected = selectedCategory == cat.name,
                        onClick = { onCategorySelect(cat.name) },
                    )
                }
            }

            Spacer(Modifier.height(12.dp))
            HorizontalDivider(color = MaterialTheme.colorScheme.outline)
            Spacer(Modifier.height(12.dp))

            Text(
                if (selectedCategory != null) "Transactions · $selectedCategory" else "Recent transactions",
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(4.dp))

            if (recentTransactions.isEmpty()) {
                EmptyState("No transactions in this period", modifier = Modifier.height(100.dp))
            } else {
                recentTransactions.take(5).forEach { tx ->
                    TransactionListItem(tx = tx, onClick = { onTransactionClick(tx.id) })
                }
            }
        }
    }
}

/** Donut chart pengeluaran. Tap slice = filter daftar transaksi. */
@Composable
private fun DonutChart(
    cats: List<CategoryTotal>,
    selectedCategory: String?,
    onSelect: (String) -> Unit,
) {
    val total = cats.fold(BigDecimal.ZERO) { acc, cat -> acc + cat.totalDecimal }
    if (total <= BigDecimal.ZERO) return

    val fractions = cats.map { (it.totalDecimal / total).toFloat() }
    // Palet monokrom turunan token expense — bukan warna random (DESIGN.md §8.4).
    val palette = List(cats.size) { i ->
        ExpenseRed.copy(alpha = (1f - 0.18f * i).coerceAtLeast(0.25f))
    }

    Box(contentAlignment = Alignment.Center) {
        Canvas(
            modifier = Modifier
                .size(160.dp)
                .pointerInput(cats, selectedCategory) {
                    detectTapGestures { offset ->
                        val stroke = 18.dp.toPx()
                        val center = Offset(size.width / 2f, size.height / 2f)
                        val dx = offset.x - center.x
                        val dy = offset.y - center.y
                        val dist = sqrt(dx * dx + dy * dy)
                        val outer = minOf(size.width, size.height) / 2f
                        val inner = outer - stroke
                        if (dist in inner..outer) {
                            var angle = Math.toDegrees(atan2(dy, dx).toDouble()).toFloat() + 90f
                            if (angle < 0f) angle += 360f
                            var acc = 0f
                            cats.forEachIndexed { index, cat ->
                                val sweep = fractions[index] * 360f
                                if (angle in acc..(acc + sweep)) {
                                    onSelect(cat.name)
                                    return@detectTapGestures
                                }
                                acc += sweep
                            }
                        }
                    }
                },
        ) {
            val stroke = 18.dp.toPx()
            val diameter = minOf(size.width, size.height) - stroke
            val topLeft = Offset((size.width - diameter) / 2f, (size.height - diameter) / 2f)
            var startAngle = -90f
            cats.forEachIndexed { index, cat ->
                val sweep = fractions[index] * 360f
                val gap = if (cat.name == selectedCategory) 0f else 2f
                drawArc(
                    color = palette[index],
                    startAngle = startAngle,
                    sweepAngle = (sweep - gap).coerceAtLeast(0f),
                    useCenter = false,
                    topLeft = topLeft,
                    size = Size(diameter, diameter),
                    style = Stroke(width = stroke),
                )
                startAngle += sweep
            }
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(Formatters.idr(total), style = MoneyMedium, color = MaterialTheme.colorScheme.onSurface)
            Text(
                "Expenses",
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

/**
 * Baris kategori — struktur Row terstruktur (label weight + progress bar lebar
 * tetap + nominal kanan), bukan Box+offset manual. Nominal overflow Visible
 * agar tidak terpotong (fix BUG 3: lebar label 110dp tetap + clip).
 */
@Composable
private fun CategoryRow(
    cat: CategoryTotal,
    color: Color,
    max: BigDecimal,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val fraction = (cat.totalDecimal / max).toFloat().coerceIn(0f, 1f)
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(8.dp))
            .background(
                if (selected) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.4f)
                else Color.Transparent,
            )
            .clickable(onClick = onClick)
            .padding(horizontal = 8.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Text(
            cat.name,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f),
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        Spacer(Modifier.width(8.dp))
        Box(
            modifier = Modifier
                .width(72.dp)
                .height(8.dp)
                .clip(RoundedCornerShape(4.dp))
                .background(MaterialTheme.colorScheme.surfaceVariant),
        ) {
            Box(
                modifier = Modifier
                    .fillMaxWidth(fraction)
                    .height(8.dp)
                    .background(color, RoundedCornerShape(4.dp)),
            )
        }
        Spacer(Modifier.width(8.dp))
        Text(
            Formatters.idr(cat.totalDecimal),
            style = MoneySmall,
            color = color,
            textAlign = TextAlign.End,
            maxLines = 1,
            overflow = TextOverflow.Visible,
        )
    }
}

/** Item transaksi terbaru (DESIGN.md §8.3): nama kiri, nominal kanan. */
@Composable
private fun TransactionListItem(tx: TransactionResponse, onClick: () -> Unit) {
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
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
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
