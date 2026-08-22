package com.mymoney.app.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp

// -------------------------------------------------------------------------
// Typography — per DESIGN.md §4
// Manrope: headings, body (geometris tapi hangat, tidak se-"corporate" Inter)
// IBM Plex Mono: nominal uang (tabular figures, monospace agar angka sejajar)
// -------------------------------------------------------------------------

// Note: Font files must be placed in res/font/ directory
// Download from Google Fonts: Manrope & IBM Plex Mono
// For build without assets: system fallback fonts are used here
// In production, replace with actual font resources

val ManropeFamily = FontFamily.Default   // Replace with Font(R.font.manrope_*) after adding .ttf
val IbmPlexMonoFamily = FontFamily.Monospace  // Replace with Font(R.font.ibm_plex_mono_*) after adding .ttf

val MyMoneyTypography = Typography(
    // Display — saldo total di beranda: 32sp, SemiBold (DESIGN.md §4)
    displayLarge = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.SemiBold,
        fontSize = 32.sp,
        lineHeight = 40.sp,
    ),
    displayMedium = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.SemiBold,
        fontSize = 28.sp,
        lineHeight = 36.sp,
    ),
    // Headline — judul halaman: 22sp, SemiBold
    headlineLarge = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.SemiBold,
        fontSize = 22.sp,
        lineHeight = 28.sp,
    ),
    headlineMedium = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.SemiBold,
        fontSize = 18.sp,
        lineHeight = 24.sp,
    ),
    // Title — nama transaksi/akun: 16sp, Medium
    titleLarge = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.Medium,
        fontSize = 16.sp,
        lineHeight = 24.sp,
    ),
    titleMedium = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.Medium,
        fontSize = 14.sp,
        lineHeight = 20.sp,
    ),
    // Body: 14sp, Regular
    bodyLarge = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.Normal,
        fontSize = 14.sp,
        lineHeight = 20.sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.Normal,
        fontSize = 13.sp,
        lineHeight = 18.sp,
    ),
    bodySmall = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
        lineHeight = 16.sp,
    ),
    labelLarge = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.Medium,
        fontSize = 14.sp,
    ),
    labelMedium = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.Normal,
        fontSize = 12.sp,
    ),
    labelSmall = TextStyle(
        fontFamily = ManropeFamily,
        fontWeight = FontWeight.Normal,
        fontSize = 11.sp,
    ),
)

// Nominal money text style — IBM Plex Mono, used anywhere an amount is displayed
// Per DESIGN.md: monospace makes numbers align vertically in lists
object MoneyTextStyle {
    val large = TextStyle(
        fontFamily = IbmPlexMonoFamily,
        fontWeight = FontWeight.Medium,
        fontSize = 20.sp,
    )
    val medium = TextStyle(
        fontFamily = IbmPlexMonoFamily,
        fontWeight = FontWeight.Medium,
        fontSize = 14.sp,
    )
    val display = TextStyle(
        fontFamily = IbmPlexMonoFamily,
        fontWeight = FontWeight.Medium,
        fontSize = 32.sp,
    )
}
