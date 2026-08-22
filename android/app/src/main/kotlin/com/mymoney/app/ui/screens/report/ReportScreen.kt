package com.mymoney.app.ui.screens.report

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.mymoney.app.ui.components.MoneyText
import com.mymoney.app.ui.theme.LocalExtendedColors
import com.mymoney.app.ui.theme.MyMoneyTypography

// Vico Charts
import com.patrykandpatrick.vico.compose.m3.style.m3ChartStyle
import com.patrykandpatrick.vico.compose.axis.horizontal.rememberBottomAxis
import com.patrykandpatrick.vico.compose.axis.vertical.rememberStartAxis
import com.patrykandpatrick.vico.compose.chart.Chart
import com.patrykandpatrick.vico.compose.chart.line.lineChart
import com.patrykandpatrick.vico.compose.style.ProvideChartStyle
import com.patrykandpatrick.vico.core.chart.line.LineChart
import com.patrykandpatrick.vico.core.entry.entryModelOf
import com.patrykandpatrick.vico.core.entry.FloatEntry

@Composable
fun ReportScreen(
    viewModel: ReportViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val extColors = LocalExtendedColors.current

    Scaffold { padding ->
        if (state.isLoading) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                CircularProgressIndicator()
            }
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            item {
                Spacer(Modifier.height(24.dp))
                Text("Laporan Bulan Ini", style = MyMoneyTypography.headlineLarge)
                Spacer(Modifier.height(8.dp))
            }

            // Trend Chart
            if (state.trend.isNotEmpty()) {
                item {
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Column(Modifier.padding(16.dp)) {
                            Text("Tren Harian", style = MyMoneyTypography.titleMedium)
                            Spacer(Modifier.height(16.dp))
                            
                            // Map DailyTrend to Vico FloatEntry
                            val incomeEntries = state.trend.mapIndexed { idx, t -> FloatEntry(idx.toFloat(), t.income.toFloat()) }
                            val expenseEntries = state.trend.mapIndexed { idx, t -> FloatEntry(idx.toFloat(), t.expense.toFloat()) }
                            val chartEntryModel = entryModelOf(incomeEntries, expenseEntries)
                            
                            ProvideChartStyle(m3ChartStyle()) {
                                Chart(
                                    chart = lineChart(),
                                    model = chartEntryModel,
                                    startAxis = rememberStartAxis(),
                                    bottomAxis = rememberBottomAxis(),
                                    modifier = Modifier.height(200.dp)
                                )
                            }
                        }
                    }
                }
            }

            // Summary List
            state.summary?.let { summary ->
                item {
                    Text("Pengeluaran per Kategori", style = MyMoneyTypography.titleMedium, modifier = Modifier.padding(top = 8.dp))
                }
                items(summary.expenseByCategory) { cat ->
                    Row(
                        modifier = Modifier.fillMaxWidth().padding(vertical = 8.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                    ) {
                        Text(cat.category, style = MyMoneyTypography.bodyLarge)
                        MoneyText(
                            amount = cat.total,
                            style = com.mymoney.app.ui.theme.MoneyTextStyle.medium,
                            color = extColors.expense
                        )
                    }
                    HorizontalDivider(color = MaterialTheme.colorScheme.surfaceVariant)
                }
            }
            
            item { Spacer(Modifier.height(80.dp)) }
        }
    }
}
