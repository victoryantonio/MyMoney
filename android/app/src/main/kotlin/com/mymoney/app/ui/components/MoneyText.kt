package com.mymoney.app.ui.components

import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.TextStyle
import com.mymoney.app.ui.theme.MoneyTextStyle
import java.text.NumberFormat
import java.util.Locale

private val rupiahFormat = NumberFormat.getNumberInstance(Locale("id", "ID")).apply {
    maximumFractionDigits = 0
}

/**
 * MoneyText — always uses IBM Plex Mono (tabular figures) for proper alignment.
 * Per DESIGN.md §4: monospace makes amounts align vertically in transaction lists.
 * Format: Rp 1.500.000 (Indonesian locale)
 */
@Composable
fun MoneyText(
    amount: Double,
    style: TextStyle = MoneyTextStyle.medium,
    color: Color = Color.Unspecified,
) {
    val formatted = "Rp ${rupiahFormat.format(amount)}"
    Text(
        text = formatted,
        style = style,
        color = color,
    )
}
