package id.my.mymoney.ui.theme

import androidx.compose.runtime.Composable
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.graphics.Color

// ── DESIGN.md §3 — Light mode ───────────────────────────────────────────────
val MyMoneyPrimaryLight = Color(0xFF3B5B8C)
val MyMoneyPrimaryContainerLight = Color(0xFFD0DCF0)
val MyMoneySurfaceLight = Color(0xFFF5F7FA)
val MyMoneySurfaceVariantLight = Color(0xFFE8EDF5)
val MyMoneyOnSurfaceLight = Color(0xFF1A2233)
val MyMoneyOnSurfaceVariantLight = Color(0xFF556070)
val MyMoneyOutlineLight = Color(0xFFD0D8E8)
val MyMoneyIncomeLight = Color(0xFF3D7A5F)
val MyMoneyExpenseLight = Color(0xFFA8503C)

// ── DESIGN.md §3 — Dark mode ───────────────────────────────────────────────
val MyMoneyPrimaryDark = Color(0xFF7B9ED4)
val MyMoneyPrimaryContainerDark = Color(0xFF243554)
val MyMoneySurfaceDark = Color(0xFF131B27)
val MyMoneySurfaceVariantDark = Color(0xFF1C2738)
val MyMoneyOnSurfaceDark = Color(0xFFE2E8F5)
val MyMoneyOnSurfaceVariantDark = Color(0xFFA0ABBE)
val MyMoneyOutlineDark = Color(0xFF2C3D57)
val MyMoneyIncomeDark = Color(0xFF6AAF8E)
val MyMoneyExpenseDark = Color(0xFFD18871)

// ── Extended tokens (MD3 punya warna income/expense bawaan) ────────────────
// DESIGN.md §9: income/expense sebagai custom token terpisah dari color scheme.
data class MyMoneyExtendedColors(
    val income: Color,
    val expense: Color,
    val net: Color, // Net = primary (tidak ada token khusus net di DESIGN.md)
)

val LocalMyMoneyColors = staticCompositionLocalOf {
    MyMoneyExtendedColors(
        income = MyMoneyIncomeLight,
        expense = MyMoneyExpenseLight,
        net = MyMoneyPrimaryLight,
    )
}

// Semantic aliases — theme-aware (ikuti light/dark). Dipakai lintas layar.
val IncomeGreen: Color @Composable get() = LocalMyMoneyColors.current.income
val ExpenseRed: Color @Composable get() = LocalMyMoneyColors.current.expense
val NetBlue: Color @Composable get() = LocalMyMoneyColors.current.net
