package id.my.mymoney.ui.receipt

import java.math.BigDecimal
import java.util.Locale

/** Hasil parse OCR nota: merchant (baris pertama) + item (nama, qty, harga). */
data class ParsedReceipt(
    val merchant: String,
    val items: List<ReceiptItem>,
)

/**
 * Parser sederhana untuk teks hasil OCR nota (umumnya berbahasa Indonesia).
 * Strategi:
 *  1. Baris non-numerik pertama yang bukan header umum dianggap nama merchant.
 *  2. Setiap baris yang mengandung angka dipisah menjadi qty×harga atau
 *     nama+harga; nama diambil dari kata non-angka.
 * Pola umum nota: "MIE GACOAN 1x 15000", "Es Teh 1 5000", "Total 75000".
 */
object ReceiptParser {

    private val HEADER_WORDS = setOf(
        "no", "item", "qty", "harga", "price", "jumlah", "total", "subtotal",
        "discount", "diskon", "pajak", "tax", "bayar", "kembalian", "change",
        "cash", "tunai", "kembali", "thanks", "terima", "kasih", "struk",
        "tanggal", "date", "waktu", "time", "member", "kasir", "cashier",
        "alamat", "address", "telp", "tel", "npwp", "invoice", "faktur", "nota",
        "makan", "minum", "pesanan", "order", "detail", "porsi", "jumlah item",
    )

    fun parse(raw: String): ParsedReceipt {
        val lines = raw.lines()
            .map { it.trim() }
            .filter { it.isNotEmpty() }

        var merchant = ""
        val items = mutableListOf<ReceiptItem>()

        for (line in lines) {
            val item = parseLine(line) ?: continue
            if (item.price.toBigDecimalOrNull() ?: BigDecimal.ZERO > BigDecimal.ZERO) {
                items.add(item)
            } else if (merchant.isBlank() && looksLikeMerchant(line)) {
                merchant = cleanMerchant(line)
            }
        }

        // Fallback merchant dari baris pertama yang bukan angka.
        if (merchant.isBlank()) {
            merchant = lines.firstOrNull { looksLikeMerchant(it) }?.let { cleanMerchant(it) } ?: ""
        }
        // Batasi nama merchant agar tidak terpotong aneh.
        if (merchant.length > 60) merchant = merchant.take(60)

        return ParsedReceipt(merchant = merchant, items = items)
    }

    private fun looksLikeMerchant(line: String): Boolean {
        val lower = line.lowercase(Locale.ROOT)
        if (line.any { it.isDigit() }) return false
        if (lower.length < 3) return false
        if (HEADER_WORDS.any { lower.contains(it) }) return false
        return true
    }

    private fun cleanMerchant(line: String): String =
        line.replace(Regex("""\s+"""), " ").trim()

    /** Parse satu baris: "Nama 2x 15000", "Nama 2 15000", "Nama 15000". */
    fun parseLine(line: String): ReceiptItem? {
        val trimmed = line.trim()
        if (trimmed.isEmpty()) return null

        // Deteksi harga: angka terakhir yang ≥ 2 digit.
        val numbers = Regex("""\d[\d.,]*""").findAll(trimmed).map { it.value }.toList()
        if (numbers.isEmpty()) return null

        // Ambil harga = angka terakhir (hilangkan ribuan separator).
        val priceStr = numbers.last().replace(".", "").replace(",", "").replace(" ", "")
        val price = priceStr.toBigDecimalOrNull() ?: return null
        if (price <= BigDecimal.ZERO) return null

        // Qty: angka dengan suffix "x" (2x) atau angka sebelum harga.
        var qty = BigDecimal.ONE
        var nameStart = 0
        val qtyMatch = Regex("""(\d+)\s*[xX×]""").find(trimmed)
        if (qtyMatch != null) {
            qty = qtyMatch.groupValues[1].toBigDecimalOrNull() ?: BigDecimal.ONE
            nameStart = qtyMatch.range.last + 1
        } else if (numbers.size >= 2) {
            // "Nama 2 15000" — angka kedua terakhir adalah qty.
            val secondLast = numbers[numbers.size - 2].replace(".", "").replace(",", "")
            secondLast.toBigDecimalOrNull()?.let { candidate ->
                if (candidate > BigDecimal.ZERO && candidate <= BigDecimal(1000)) {
                    qty = candidate
                }
            }
        }

        // Nama = teks sebelum angka harga, bersih dari qty & angka.
        val priceIndex = trimmed.lastIndexOf(numbers.last())
        var namePart = trimmed.substring(0, priceIndex).trim()
        namePart = namePart.replace(Regex("""\d+[xX×]"""), "").trim()
        namePart = namePart.replace(Regex("""\d+"""), "").trim()
        namePart = namePart.replace(Regex("""[.\-–—_|:]+$"""), "").trim()

        // Buang kata-kata header/umum dari nama.
        val cleaned = namePart
            .split(Regex("""\s+"""))
            .filterNot { word ->
                val w = word.lowercase(Locale.ROOT)
                w in HEADER_WORDS || w.length > 40
            }
            .joinToString(" ")
            .trim()

        if (cleaned.isBlank()) return null
        if (cleaned.length > 60) return null

        return ReceiptItem(name = cleaned, qty = qty.toPlainString(), price = price.toPlainString())
    }
}
