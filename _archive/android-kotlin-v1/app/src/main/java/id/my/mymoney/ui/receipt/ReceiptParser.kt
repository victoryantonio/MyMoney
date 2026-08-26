package id.my.mymoney.ui.receipt

import java.math.BigDecimal
import java.text.NumberFormat
import java.util.Locale

/** Hasil parse OCR nota: merchant + item (nama, qty, harga) + tanggal (dd-MM-yyyy). */
data class ParsedReceipt(
    val merchant: String,
    val items: List<ReceiptItem>,
    val date: String? = null, // normalisasi "dd-MM-yyyy" bila tercetak di nota
)

/**
 * Parser sederhana untuk teks hasil OCR nota (umumnya berbahasa Indonesia).
 * Strategi:
 *  1. Tanggal dd-mm-yyyy (atau dd/mm/yyyy) diekstrak dan di-normalisasi.
 *  2. Baris non-numerik pertama yang bukan header umum dianggap nama merchant.
 *  3. Setiap baris yang mengandung angka dipisah menjadi qty×harga atau
 *     nama+harga; nama diambil dari kata non-angka.
 *  4. Baris "2 x 21000" / "2x21000" TANPA nama akan di-attach ke item terakhir
 *     (format umum nota: nama item di baris atas, qty×harga di baris bawah).
 *  5. Harga ditampilkan dengan separator ribuan ("21.000") — nilai numerik
 *     murni ("21000") tetap dihitung via [parsePriceToDecimal].
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

    private val DATE_PATTERN = Regex("""\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b""")
    private val QTY_ONLY_PATTERN = Regex("""^\s*\d+\s*[xX×]\s*[\d.,]+\s*$""")
    private val NUMBER_PATTERN = Regex("""\d[\d.,]*""")
    private val QTY_MARK_PATTERN = Regex("""(\d+)\s*[xX×]""")

    fun parse(raw: String): ParsedReceipt {
        val lines = raw.lines()
            .map { it.trim() }
            .filter { it.isNotEmpty() }

        var date: String? = null
        // Index baris non-numerik yang diikuti langsung baris "qty x harga" (nama item).
        val itemNameLines = mutableSetOf<Int>()

        // Pass 1: tanggal + pasangan nama-item (baris atas) dengan qty×harga (baris bawah).
        for (i in lines.indices) {
            val line = lines[i]
            extractDate(line)?.let { if (date == null) date = it }
            if (QTY_ONLY_PATTERN.matches(line) && i > 0 && looksLikeMerchant(lines[i - 1])) {
                itemNameLines.add(i - 1)
            }
        }

        var merchant = ""
        val items = mutableListOf<ReceiptItem>()
        var pendingName: String? = null

        // Pass 2: susun item & merchant.
        for (i in lines.indices) {
            val line = lines[i]
            if (extractDate(line) != null) continue

            val item = parseLine(line)
            val price = item?.price?.toBigDecimalOrNull() ?: BigDecimal.ZERO
            if (item != null && price > BigDecimal.ZERO) {
                if (item.name.isNotBlank()) {
                    items.add(item)
                } else if (pendingName != null) {
                    // "2 x 21000" tanpa nama → gabung dengan nama item di baris atas.
                    items.add(ReceiptItem(name = pendingName, qty = item.qty, price = item.price))
                } else if (items.isNotEmpty()) {
                    // Fallback: attach ke item terakhir.
                    val last = items.removeAt(items.size - 1)
                    items.add(last.copy(qty = item.qty, price = item.price))
                }
                pendingName = null
                continue
            }

            // Baris non-numerik.
            if (looksLikeMerchant(line)) {
                if (i in itemNameLines) {
                    pendingName = cleanMerchant(line)
                } else if (merchant.isBlank()) {
                    merchant = cleanMerchant(line)
                } else {
                    // Baris nama tambahan setelah merchant (tanpa qty×harga) — 
                    // jadikan pendingName agar baris harga berikutnya bisa attach.
                    pendingName = cleanMerchant(line)
                }
            }
        }

        // Fallback merchant dari baris pertama yang bukan angka & bukan nama item.
        if (merchant.isBlank()) {
            merchant = lines.firstOrNull { line ->
                looksLikeMerchant(line) && lines.indexOf(line) !in itemNameLines
            }?.let { cleanMerchant(it) } ?: ""
        }
        // Batasi nama merchant agar tidak terpotong aneh.
        if (merchant.length > 60) merchant = merchant.take(60)

        return ParsedReceipt(merchant = merchant, items = items, date = date)
    }

    /** Ekstrak tanggal "25-08-2026" / "25/08/2026" → "25-08-2026" (validasi bulan/hari). */
    private fun extractDate(line: String): String? {
        val match = DATE_PATTERN.find(line) ?: return null
        val day = match.groupValues[1].toIntOrNull() ?: return null
        val month = match.groupValues[2].toIntOrNull() ?: return null
        val year = match.groupValues[3].toIntOrNull() ?: return null
        if (month !in 1..12 || day !in 1..31) return null
        return "%02d-%02d-%04d".format(Locale.ROOT, day, month, year)
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

    /** "21000" → "21.000" (separator ribuan, tampilan). */
    fun formatPrice(value: BigDecimal): String =
        NumberFormat.getNumberInstance(Locale.forLanguageTag("id-ID")).format(value)

    /**
     * "21.000" / "Rp21.000" / "21,000" → 21000 (untuk kalkulasi & kirim API).
     * Menghilangkan separator ribuan dan prefix mata uang.
     */
    fun parsePriceToDecimal(raw: String): BigDecimal? {
        val cleaned = raw
            .replace("Rp", "", ignoreCase = true)
            .replace(" ", "")
            .replace(".", "")
            .replace(",", "")
        return cleaned.toBigDecimalOrNull()
    }

    /** Parse satu baris: "Nama 2x 15000", "Nama 2 15000", "Nama 15000", "2 x 21000". */
    fun parseLine(line: String): ReceiptItem? {
        val trimmed = line.trim()
        if (trimmed.isEmpty()) return null

        // Deteksi harga: angka terakhir yang ≥ 2 digit.
        val numbers = NUMBER_PATTERN.findAll(trimmed).map { it.value }.toList()
        if (numbers.isEmpty()) return null

        // Ambil harga = angka terakhir (hilangkan ribuan separator).
        val priceStr = numbers.last().replace(".", "").replace(",", "").replace(" ", "")
        val price = priceStr.toBigDecimalOrNull() ?: return null
        if (price <= BigDecimal.ZERO) return null

        // Qty: angka dengan suffix "x" (2x) atau angka sebelum harga.
        var qty = BigDecimal.ONE
        val qtyMatch = QTY_MARK_PATTERN.find(trimmed)
        if (qtyMatch != null) {
            qty = qtyMatch.groupValues[1].toBigDecimalOrNull() ?: BigDecimal.ONE
        } else if (numbers.size >= 2) {
            // "Nama 2 15000" — angka kedua terakhir adalah qty.
            val secondLast = numbers[numbers.size - 2].replace(".", "").replace(",", "")
            secondLast.toBigDecimalOrNull()?.let { candidate ->
                if (candidate > BigDecimal.ZERO && candidate <= BigDecimal(1000)) {
                    qty = candidate
                }
            }
        }

        // Nama = teks sebelum qty-mark (atau sebelum harga), bersih dari angka.
        var namePart: String
        if (qtyMatch != null) {
            namePart = trimmed.substring(0, qtyMatch.range.first).trim()
        } else {
            val priceIndex = trimmed.lastIndexOf(numbers.last())
            namePart = trimmed.substring(0, priceIndex).trim()
        }
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

        val displayPrice = formatPrice(price)

        // Baris hanya "qty × price" tanpa nama → attach ke item terakhir di parse().
        if (cleaned.isBlank()) {
            if (QTY_ONLY_PATTERN.matches(trimmed)) {
                return ReceiptItem(name = "", qty = qty.toPlainString(), price = displayPrice)
            }
            return null
        }
        if (cleaned.length > 60) return null

        return ReceiptItem(name = cleaned, qty = qty.toPlainString(), price = displayPrice)
    }
}
