package id.my.mymoney.ui.components

import android.graphics.Paint
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.nativeCanvas
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import id.my.mymoney.ui.theme.ExpenseRed
import id.my.mymoney.ui.theme.IncomeGreen
import id.my.mymoney.util.Formatters
import java.math.BigDecimal
import java.text.NumberFormat
import java.time.LocalDate
import java.time.format.DateTimeFormatter
import java.util.Locale
import kotlin.math.roundToInt

/** Satu titik data grafik arus kas (date + income & expense). */
data class CashFlowPoint(
    val date: LocalDate,
    val income: BigDecimal,
    val expense: BigDecimal,
)

private val ID_DATE_FMT = DateTimeFormatter.ofPattern("d MMM", Locale.forLanguageTag("id-ID"))

/** Label sumbu Y ringkas: "950", "21 rb", "1,5 jt" — tanpa library chart. */
private fun compactIdr(value: BigDecimal): String {
    val abs = value.abs()
    val juta = BigDecimal("1000000")
    val ribu = BigDecimal("1000")
    return when {
        abs >= juta -> String.format(Locale.ROOT, "%.1f jt", value / juta)
        abs >= ribu -> String.format(Locale.ROOT, "%.0f rb", value / ribu)
        else -> value.setScale(0, java.math.RoundingMode.HALF_UP).toPlainString()
    }
}

/**
 * Grafik garis tren arus kas — TANPA library chart (DESIGN.md).
 * Garis income = hijau, garis expense = merah. Punya sumbu X (tanggal) dan
 * sumbu Y (nominal) + long-press tiap titik menampilkan income & expense.
 * Dipakai oleh Dashboard (data backend /trend) dan Account Detail (dihitung
 * client-side dari transaksi).
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
        val axisColor = MaterialTheme.colorScheme.onSurfaceVariant
        val surfaceColor = MaterialTheme.colorScheme.surfaceVariant
        val density = LocalDensity.current

        val maxValue = points.maxOfOrNull { point ->
            maxOf(point.income, point.expense)
        }?.takeIf { it > BigDecimal.ZERO } ?: BigDecimal.ONE

        // Ruang untuk label sumbu: kiri (Y) & bawah (X).
        val leftPad = 46.dp
        val rightPad = 10.dp
        val topPad = 6.dp
        val bottomPad = 22.dp

        var boxWidthPx by remember { mutableStateOf(0) }
        var boxHeightPx by remember { mutableStateOf(0) }
        var selectedIndex by remember(points) { mutableStateOf<Int?>(null) }

        val plotLeft = with(density) { leftPad.toPx() }
        val plotTop = with(density) { topPad.toPx() }
        val plotRight = (boxWidthPx - with(density) { rightPad.toPx() }).coerceAtLeast(plotLeft + 1f)
        val plotBottom = (boxHeightPx - with(density) { bottomPad.toPx() }).coerceAtLeast(plotTop + 1f)
        val plotWidth = plotRight - plotLeft
        val plotHeight = plotBottom - plotTop
        val stepX = if (points.size > 1) plotWidth / (points.size - 1) else 0f

        fun xFor(index: Int): Float =
            if (points.size > 1) plotLeft + index * stepX else plotLeft + plotWidth / 2f

        Box(
            modifier = Modifier
                .fillMaxWidth()
                .height(height.dp)
                .onSizeChanged { size ->
                    boxWidthPx = size.width
                    boxHeightPx = size.height
                },
        ) {
            Canvas(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(height.dp)
                    .pointerInput(points) {
                        detectTapGestures(
                            onLongPress = { offset ->
                                if (points.size > 1 && plotWidth > 0f) {
                                    val index = ((offset.x - plotLeft) / stepX)
                                        .roundToInt()
                                        .coerceIn(0, points.size - 1)
                                    selectedIndex = index
                                } else if (points.size == 1) {
                                    selectedIndex = 0
                                }
                            },
                        )
                    },
            ) {
                val axisPaint = Paint().apply {
                    color = gridColor.toArgb()
                    isAntiAlias = true
                }
                val textPaint = Paint().apply {
                    color = axisColor.toArgb()
                    textSize = 9.sp.toPx()
                    isAntiAlias = true
                }

                // Sumbu Y (kiri) & sumbu X (bawah).
                drawLine(
                    color = gridColor,
                    start = Offset(plotLeft, plotTop),
                    end = Offset(plotLeft, plotBottom),
                    strokeWidth = 1f,
                )
                drawLine(
                    color = gridColor,
                    start = Offset(plotLeft, plotBottom),
                    end = Offset(plotRight, plotBottom),
                    strokeWidth = 1f,
                )

                // Gridlines horizontal (4) + label sumbu Y (0, tengah, max).
                for (i in 0..3) {
                    val fraction = i / 3f
                    val y = plotTop + plotHeight * fraction
                    drawLine(
                        color = gridColor,
                        start = Offset(plotLeft, y),
                        end = Offset(plotRight, y),
                        strokeWidth = 1f,
                    )
                    if (i % 2 == 0) {
                        val value = maxValue * BigDecimal.valueOf((1f - fraction).toDouble())
                        textPaint.textAlign = Paint.Align.RIGHT
                        drawContext.canvas.nativeCanvas.drawText(
                            compactIdr(value.setScale(0, java.math.RoundingMode.HALF_UP)),
                            plotLeft - 6.dp.toPx(),
                            y + 3.dp.toPx(),
                            textPaint,
                        )
                    }
                }

                // Label sumbu X: tanggal pertama, tengah, terakhir.
                val labelIndexes = buildSet {
                    add(0)
                    if (points.size > 2) add(points.size / 2)
                    add(points.size - 1)
                }
                textPaint.textAlign = Paint.Align.CENTER
                labelIndexes.forEach { index ->
                    val x = xFor(index).coerceIn(plotLeft, plotRight)
                    drawContext.canvas.nativeCanvas.drawText(
                        points[index].date.format(ID_DATE_FMT),
                        x,
                        plotBottom + 4.dp.toPx(),
                        textPaint,
                    )
                }

                fun yFor(value: BigDecimal): Float =
                    plotTop + plotHeight * (1f - (value.toFloat() / maxValue.toFloat()))

                fun buildPath(selector: (CashFlowPoint) -> BigDecimal): Path {
                    val path = Path()
                    points.forEachIndexed { index, point ->
                        val x = xFor(index)
                        val y = yFor(selector(point))
                        if (index == 0) path.moveTo(x, y) else path.lineTo(x, y)
                    }
                    return path
                }

                val stroke = Stroke(width = 3f)

                // Expense dulu (di belakang), income di depan.
                drawPath(buildPath { it.expense }, color = expenseColor, style = stroke)
                drawPath(buildPath { it.income }, color = incomeColor, style = stroke)

                // Titik data (lingkaran kecil) supaya long-press jelas sasarannya.
                points.forEachIndexed { index, point ->
                    drawCircle(
                        color = incomeColor,
                        radius = 3.dp.toPx(),
                        center = Offset(xFor(index), yFor(point.income)),
                    )
                    drawCircle(
                        color = expenseColor,
                        radius = 3.dp.toPx(),
                        center = Offset(xFor(index), yFor(point.expense)),
                    )
                }
            }

            // Tooltip long-press: tampilkan income & expense pada titik terpilih.
            selectedIndex?.let { index ->
                val point = points[index]
                val valueAt = maxOf(point.income, point.expense)
                val x = xFor(index)
                val y = plotTop + plotHeight * (1f - valueAt.toFloat() / maxValue.toFloat())
                val tooltipX = (x - with(density) { 66.dp.toPx() }).coerceAtLeast(0f)
                val tooltipY = (y - with(density) { 82.dp.toPx() }).coerceAtLeast(0f)
                Surface(
                    modifier = Modifier.offset(
                        x = with(density) { tooltipX.toDp() },
                        y = with(density) { tooltipY.toDp() },
                    ),
                    shape = RoundedCornerShape(8.dp),
                    color = surfaceColor,
                    shadowElevation = 3.dp,
                ) {
                    Column(modifier = Modifier.padding(horizontal = 10.dp, vertical = 6.dp)) {
                        Text(
                            point.date.format(ID_DATE_FMT),
                            style = MaterialTheme.typography.labelSmall,
                            color = axisColor,
                        )
                        Spacer(Modifier.height(2.dp))
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                "Income: ",
                                style = MaterialTheme.typography.labelMedium,
                                color = axisColor,
                            )
                            Text(
                                Formatters.idr(point.income),
                                style = MaterialTheme.typography.labelMedium,
                                color = incomeColor,
                                fontWeight = FontWeight.SemiBold,
                            )
                        }
                        Row(verticalAlignment = Alignment.CenterVertically) {
                            Text(
                                "Expense: ",
                                style = MaterialTheme.typography.labelMedium,
                                color = axisColor,
                            )
                            Text(
                                Formatters.idr(point.expense),
                                style = MaterialTheme.typography.labelMedium,
                                color = expenseColor,
                                fontWeight = FontWeight.SemiBold,
                            )
                        }
                    }
                }
            }
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
