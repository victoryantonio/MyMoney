package id.my.mymoney.util

import java.math.BigDecimal
import java.text.NumberFormat
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import java.util.Locale

/** Formatting helpers shared across screens. */
object Formatters {

    private val idrFormat: NumberFormat =
        NumberFormat.getCurrencyInstance(Locale.forLanguageTag("id-ID"))

    private val dateFormatter: DateTimeFormatter =
        DateTimeFormatter.ofPattern("d MMM yyyy", Locale.ENGLISH)

    private val dateTimeFormatter: DateTimeFormatter =
        DateTimeFormatter.ofPattern("d MMM yyyy, HH:mm", Locale.ENGLISH)

    fun idr(amount: BigDecimal): String = idrFormat.format(amount)

    fun idrOrEmpty(raw: String?): String {
        val amount = raw?.let { runCatching { BigDecimal(it) }.getOrNull() }
            ?: return "—"
        return idr(amount)
    }

    /** "2026-08-25T10:30:00+07:00" → "25 Aug 2026". */
    fun date(iso: String?): String {
        if (iso.isNullOrBlank()) return "—"
        return runCatching { OffsetDateTime.parse(iso).format(dateFormatter) }
            .getOrElse { iso.take(10) }
    }

    /** "2026-08-25T10:30:00+07:00" → "25 Aug 2026, 10:30". */
    fun dateTime(iso: String?): String {
        if (iso.isNullOrBlank()) return "—"
        return runCatching { OffsetDateTime.parse(iso).format(dateTimeFormatter) }
            .getOrElse { iso.take(16).replace("T", " ") }
    }

    /** "150000.00" → "150.000" (grouped integer, no decimals). */
    fun grouped(raw: String): String =
        runCatching {
            val bd = BigDecimal(raw)
            NumberFormat.getNumberInstance(Locale.forLanguageTag("id-ID")).apply {
                maximumFractionDigits = 0
            }.format(bd)
        }.getOrDefault(raw)
}
