package id.my.mymoney.ui.theme

import androidx.compose.material3.Typography
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.font.Font
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.sp
import id.my.mymoney.R

// DESIGN.md §4 — Manrope untuk heading/body, IBM Plex Mono untuk nominal.
val Manrope = FontFamily(
    Font(R.font.manrope, FontWeight.Normal),
    Font(R.font.manrope, FontWeight.Medium),
    Font(R.font.manrope, FontWeight.SemiBold),
    Font(R.font.manrope, FontWeight.Bold),
)

val IbmPlexMono = FontFamily(
    Font(R.font.ibm_plex_mono_regular, FontWeight.Normal),
    Font(R.font.ibm_plex_mono_medium, FontWeight.Medium),
)

// Nominal uang (DESIGN.md §4): IBM Plex Mono Medium, ukuran mengikuti konteks.
val MoneyDisplay = TextStyle(
    fontFamily = IbmPlexMono, fontWeight = FontWeight.Medium, fontSize = 32.sp, lineHeight = 40.sp,
)
val MoneyLarge = TextStyle(
    fontFamily = IbmPlexMono, fontWeight = FontWeight.Medium, fontSize = 20.sp, lineHeight = 28.sp,
)
val MoneyMedium = TextStyle(
    fontFamily = IbmPlexMono, fontWeight = FontWeight.Medium, fontSize = 14.sp, lineHeight = 20.sp,
)
val MoneySmall = TextStyle(
    fontFamily = IbmPlexMono, fontWeight = FontWeight.Medium, fontSize = 12.sp, lineHeight = 16.sp,
)

// DESIGN.md §4 — skala tipografi (token MD3 disesuaikan).
val Typography = Typography(
    displaySmall = TextStyle(
        fontFamily = Manrope, fontWeight = FontWeight.SemiBold, fontSize = 32.sp, lineHeight = 40.sp, letterSpacing = 0.sp,
    ), // Saldo total di beranda
    headlineMedium = TextStyle(
        fontFamily = Manrope, fontWeight = FontWeight.SemiBold, fontSize = 22.sp, lineHeight = 28.sp, letterSpacing = 0.sp,
    ), // Judul halaman
    titleLarge = TextStyle(
        fontFamily = Manrope, fontWeight = FontWeight.SemiBold, fontSize = 22.sp, lineHeight = 28.sp, letterSpacing = 0.sp,
    ),
    titleMedium = TextStyle(
        fontFamily = Manrope, fontWeight = FontWeight.Medium, fontSize = 16.sp, lineHeight = 24.sp, letterSpacing = 0.15.sp,
    ), // Nama transaksi/akun
    titleSmall = TextStyle(
        fontFamily = Manrope, fontWeight = FontWeight.Medium, fontSize = 14.sp, lineHeight = 20.sp, letterSpacing = 0.1.sp,
    ),
    bodyLarge = TextStyle(
        fontFamily = Manrope, fontWeight = FontWeight.Normal, fontSize = 16.sp, lineHeight = 24.sp, letterSpacing = 0.5.sp,
    ),
    bodyMedium = TextStyle(
        fontFamily = Manrope, fontWeight = FontWeight.Normal, fontSize = 14.sp, lineHeight = 20.sp, letterSpacing = 0.25.sp,
    ),
    bodySmall = TextStyle(
        fontFamily = Manrope, fontWeight = FontWeight.Normal, fontSize = 12.sp, lineHeight = 16.sp, letterSpacing = 0.4.sp,
    ),
    labelLarge = TextStyle(
        fontFamily = Manrope, fontWeight = FontWeight.Medium, fontSize = 14.sp, lineHeight = 20.sp, letterSpacing = 0.1.sp,
    ),
    labelMedium = TextStyle(
        fontFamily = Manrope, fontWeight = FontWeight.Medium, fontSize = 12.sp, lineHeight = 16.sp, letterSpacing = 0.5.sp,
    ),
    labelSmall = TextStyle(
        fontFamily = Manrope, fontWeight = FontWeight.Medium, fontSize = 11.sp, lineHeight = 16.sp, letterSpacing = 0.5.sp,
    ),
)
