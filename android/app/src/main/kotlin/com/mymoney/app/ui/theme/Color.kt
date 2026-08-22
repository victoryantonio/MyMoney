package com.mymoney.app.ui.theme

import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.ui.graphics.Color

// -------------------------------------------------------------------------
// Custom color tokens — per DESIGN.md §3
// Intentionally NOT using the generic purple/blue MD3 defaults.
// Basis: warm neutral + terracotta/clay + sage green
// -------------------------------------------------------------------------

// Light mode tokens
val Surface = Color(0xFFFBF7F2)           // krem hangat — bukan putih steril
val SurfaceVariant = Color(0xFFF0E9E0)    // card, container sekunder
val OnSurface = Color(0xFF2B2622)         // teks utama — coklat gelap hangat
val OnSurfaceVariant = Color(0xFF6B6259)  // teks sekunder, caption
val Primary = Color(0xFFB4552F)           // terracotta/clay — CTA utama
val PrimaryContainer = Color(0xFFF4DCC9)  // background elemen primary lembut
val Outline = Color(0xFFDCD2C4)           // border, divider

// Dark mode tokens
val SurfaceDark = Color(0xFF1E1B18)
val SurfaceVariantDark = Color(0xFF2A2521)
val OnSurfaceDark = Color(0xFFEDE6DD)
val OnSurfaceVariantDark = Color(0xFFB5AA9C)
val PrimaryDark = Color(0xFFE08A5C)       // terracotta lebih terang untuk kontras
val PrimaryContainerDark = Color(0xFF5C3620)
val OutlineDark = Color(0xFF443E37)

// Extended tokens (income/expense) — MD3 tidak punya token bawaan untuk ini
val Income = Color(0xFF5B7A5E)            // sage green — indikator pemasukan
val Expense = Color(0xFFA8503C)           // rust/brick — indikator pengeluaran
val IncomeDark = Color(0xFF8FAF8E)
val ExpenseDark = Color(0xFFD18871)

// -------------------------------------------------------------------------
// Color schemes
// -------------------------------------------------------------------------
val MyMoneyLightColorScheme = lightColorScheme(
    primary = Primary,
    primaryContainer = PrimaryContainer,
    onPrimary = Color.White,
    onPrimaryContainer = Color(0xFF3A1500),
    surface = Surface,
    surfaceVariant = SurfaceVariant,
    onSurface = OnSurface,
    onSurfaceVariant = OnSurfaceVariant,
    outline = Outline,
    background = Surface,
    onBackground = OnSurface,
    secondary = Color(0xFF5B7A5E),
    secondaryContainer = Color(0xFFD4EACE),
    onSecondary = Color.White,
    error = Expense,
    onError = Color.White,
)

val MyMoneyDarkColorScheme = darkColorScheme(
    primary = PrimaryDark,
    primaryContainer = PrimaryContainerDark,
    onPrimary = Color(0xFF3A1500),
    onPrimaryContainer = Color(0xFFF4DCC9),
    surface = SurfaceDark,
    surfaceVariant = SurfaceVariantDark,
    onSurface = OnSurfaceDark,
    onSurfaceVariant = OnSurfaceVariantDark,
    outline = OutlineDark,
    background = SurfaceDark,
    onBackground = OnSurfaceDark,
    secondary = IncomeDark,
    secondaryContainer = Color(0xFF3A5E3D),
    onSecondary = Color(0xFF1A3D1E),
    error = ExpenseDark,
    onError = Color(0xFF3A0A00),
)

// Extended colors data class — injected via CompositionLocal
data class MyMoneyExtendedColors(
    val income: Color,
    val expense: Color,
    val incomeContainer: Color,
    val expenseContainer: Color,
)

val LightExtendedColors = MyMoneyExtendedColors(
    income = Income,
    expense = Expense,
    incomeContainer = Color(0xFFD4EACE),
    expenseContainer = Color(0xFFF8DDD7),
)

val DarkExtendedColors = MyMoneyExtendedColors(
    income = IncomeDark,
    expense = ExpenseDark,
    incomeContainer = Color(0xFF1F3D22),
    expenseContainer = Color(0xFF4A1A12),
)
