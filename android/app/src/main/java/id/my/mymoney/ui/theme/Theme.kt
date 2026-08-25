package id.my.mymoney.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.ui.unit.dp

// DESIGN.md §5 — corner radius konsisten: 12dp card, 8dp button.
val AppCardShape = RoundedCornerShape(12.dp)
val AppButtonShape = RoundedCornerShape(8.dp)

// DESIGN.md §3 — Jetpack Compose color scheme (dusty slate blue).
// Dynamic color (Material You) sengaja TIDAK dipakai: palet brand harus konsisten.
val MyMoneyLightColorScheme = lightColorScheme(
    primary = MyMoneyPrimaryLight,
    primaryContainer = MyMoneyPrimaryContainerLight,
    surface = MyMoneySurfaceLight,
    surfaceVariant = MyMoneySurfaceVariantLight,
    onSurface = MyMoneyOnSurfaceLight,
    onSurfaceVariant = MyMoneyOnSurfaceVariantLight,
    outline = MyMoneyOutlineLight,
)

val MyMoneyDarkColorScheme = darkColorScheme(
    primary = MyMoneyPrimaryDark,
    primaryContainer = MyMoneyPrimaryContainerDark,
    surface = MyMoneySurfaceDark,
    surfaceVariant = MyMoneySurfaceVariantDark,
    onSurface = MyMoneyOnSurfaceDark,
    onSurfaceVariant = MyMoneyOnSurfaceVariantDark,
    outline = MyMoneyOutlineDark,
)

@Composable
fun MyMoneyTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) MyMoneyDarkColorScheme else MyMoneyLightColorScheme
    val extended = MyMoneyExtendedColors(
        income = if (darkTheme) MyMoneyIncomeDark else MyMoneyIncomeLight,
        expense = if (darkTheme) MyMoneyExpenseDark else MyMoneyExpenseLight,
        net = if (darkTheme) MyMoneyPrimaryDark else MyMoneyPrimaryLight,
    )

    CompositionLocalProvider(LocalMyMoneyColors provides extended) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = Typography,
            content = content,
        )
    }
}
