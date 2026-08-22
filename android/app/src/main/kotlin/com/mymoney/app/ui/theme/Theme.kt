package com.mymoney.app.ui.theme

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Shapes
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.unit.dp
import androidx.compose.foundation.shape.RoundedCornerShape

// -------------------------------------------------------------------------
// CompositionLocal for extended colors (income/expense)
// -------------------------------------------------------------------------
val LocalExtendedColors = staticCompositionLocalOf {
    LightExtendedColors
}

// Access income/expense colors from any composable:
// val colors = LocalExtendedColors.current
// Text(color = colors.income) or Text(color = colors.expense)

// -------------------------------------------------------------------------
// Shapes — per DESIGN.md §5
// Card: 12dp (not pill-shape 24dp+ generic)
// Button: 8dp
// -------------------------------------------------------------------------
val MyMoneyShapes = Shapes(
    extraSmall = RoundedCornerShape(4.dp),
    small = RoundedCornerShape(8.dp),     // buttons
    medium = RoundedCornerShape(12.dp),   // cards
    large = RoundedCornerShape(16.dp),    // bottom sheets, dialogs
    extraLarge = RoundedCornerShape(24.dp),
)

// -------------------------------------------------------------------------
// MyMoneyTheme — root composable, wraps MaterialTheme with custom design system
// -------------------------------------------------------------------------
@Composable
fun MyMoneyTheme(
    darkTheme: Boolean = isSystemInDarkTheme(),
    content: @Composable () -> Unit,
) {
    val colorScheme = if (darkTheme) MyMoneyDarkColorScheme else MyMoneyLightColorScheme
    val extendedColors = if (darkTheme) DarkExtendedColors else LightExtendedColors

    CompositionLocalProvider(LocalExtendedColors provides extendedColors) {
        MaterialTheme(
            colorScheme = colorScheme,
            typography = MyMoneyTypography,
            shapes = MyMoneyShapes,
            content = content,
        )
    }
}
