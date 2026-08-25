package id.my.mymoney.ui.components

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import id.my.mymoney.ui.theme.ExpenseRed
import id.my.mymoney.ui.theme.IncomeGreen
import java.math.BigDecimal
import java.time.LocalDate

/** Satu titik data grafik arus kas (date + income & expense). */
data class CashFlowPoint(
    val date: LocalDate,
    val income: BigDecimal,
    val expense: BigDecimal,
)

/**
 * Grafik garis tren arus kas — TANPA library chart (DESIGN.md).
 * Garis income = hijau, garis expense = merah. Sumbu Y dinormalisasi ke
 * nilai maksimum kedua seri. Dipakai oleh Dashboard (data backend /trend)
 * dan Account Detail (dihitung client-side dari transaksi).
 */
@Composable
fun CashFlowLineChart(
    points: List<CashFlowPoint>,
    modifier: Modifier = Modifier,
    height: Int = 160,
) {
    if (points.isEmpty()) {
        Box(
            modifier = modifier
                .fillMaxWidth()
                .height(height.dp),
            contentAlignment = Alignment.Center,
        ) {
            Text(
                "Belum ada data untuk periode ini",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
        return
    }

    Column(modifier = modifier.fillMaxWidth()) {
        // Legend.
        Row(verticalAlignment = Alignment.CenterVertically) {
            LegendDot(color = IncomeGreen, label = "Income")
            Spacer(Modifier.width(16.dp))
            LegendDot(color = ExpenseRed, label = "Expense")
        }
        Spacer(Modifier.height(8.dp))
        // Warna tema diambil di sini (context @Composable) untuk dipakai
        // di dalam Canvas draw scope.
        val incomeColor = IncomeGreen
        val expenseColor = ExpenseRed
        val gridColor = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.3f)
        Canvas(
            modifier = Modifier
                .fillMaxWidth()
                .height(height.dp),
        ) {
            // Horizontal gridlines (4) — tipis, netral.
            for (i in 0..3) {
                val y = size.height * i / 3f
                drawLine(
                    color = gridColor,
                    start = Offset(0f, y),
                    end = Offset(size.width, y),
                    strokeWidth = 1f,
                )
            }

            val maxValue = points.maxOfOrNull { point ->
                maxOf(point.income, point.expense)
            }?.takeIf { it > BigDecimal.ZERO } ?: BigDecimal.ONE

            fun yFor(value: BigDecimal): Float =
                size.height * (1f - (value.toFloat() / maxValue.toFloat()))

            val stepX = if (points.size > 1) size.width / (points.size - 1) else 0f

            fun buildPath(selector: (CashFlowPoint) -> BigDecimal): Path {
                val path = Path()
                points.forEachIndexed { index, point ->
                    val x = index * stepX
                    val y = yFor(selector(point))
                    if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
                }
                return path
            }

            val stroke = Stroke(width = 3f)

            // Expense dulu (di belakang), income di depan.
            drawPath(buildPath { it.expense }, color = expenseColor, style = stroke)
            drawPath(buildPath { it.income }, color = incomeColor, style = stroke)
        }
    }
}

@Composable
private fun LegendDot(color: androidx.compose.ui.graphics.Color, label: String) {
    Row(verticalAlignment = Alignment.CenterVertically) {
        Canvas(modifier = Modifier.width(10.dp).height(10.dp)) {
            drawCircle(color = color, radius = size.minDimension / 2f)
        }
        Spacer(Modifier.width(4.dp))
        Text(
            label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            fontSize = 12.sp,
        )
    }
}
