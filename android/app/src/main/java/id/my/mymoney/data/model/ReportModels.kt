package id.my.mymoney.data.model

import kotlinx.serialization.Serializable

@Serializable
data class CategoryTotal(
    val name: String,
    val type: String, // "income" | "expense"
    @Serializable(with = FlexibleStringSerializer::class) val total: String,
) {
    val totalDecimal: java.math.BigDecimal
        get() = runCatching { java.math.BigDecimal(total) }.getOrDefault(java.math.BigDecimal.ZERO)
}

@Serializable
data class ReportSummaryResponse(
    val start_date: String,
    val end_date: String,
    @Serializable(with = FlexibleStringSerializer::class) val total_income: String,
    @Serializable(with = FlexibleStringSerializer::class) val total_expense: String,
    @Serializable(with = FlexibleStringSerializer::class) val net: String,
    val categories: List<CategoryTotal> = emptyList(),
) {
    val income: java.math.BigDecimal
        get() = runCatching { java.math.BigDecimal(total_income) }.getOrDefault(java.math.BigDecimal.ZERO)
    val expense: java.math.BigDecimal
        get() = runCatching { java.math.BigDecimal(total_expense) }.getOrDefault(java.math.BigDecimal.ZERO)
    val netDecimal: java.math.BigDecimal
        get() = runCatching { java.math.BigDecimal(net) }.getOrDefault(java.math.BigDecimal.ZERO)
}

/** Satu hari pada grafik tren arus kas: tanggal + total income & expense. */
@Serializable
data class TrendPoint(
    val date: String, // ISO yyyy-MM-dd
    @Serializable(with = FlexibleStringSerializer::class) val income: String,
    @Serializable(with = FlexibleStringSerializer::class) val expense: String,
) {
    val incomeDecimal: java.math.BigDecimal
        get() = runCatching { java.math.BigDecimal(income) }.getOrDefault(java.math.BigDecimal.ZERO)
    val expenseDecimal: java.math.BigDecimal
        get() = runCatching { java.math.BigDecimal(expense) }.getOrDefault(java.math.BigDecimal.ZERO)
}

/** Seri harian income/expense untuk grafik garis (dashboard). */
@Serializable
data class ReportTrendResponse(
    val start_date: String,
    val end_date: String,
    val points: List<TrendPoint> = emptyList(),
)
