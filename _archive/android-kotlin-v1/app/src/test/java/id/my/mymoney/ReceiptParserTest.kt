package id.my.mymoney

import id.my.mymoney.ui.receipt.ReceiptParser
import java.math.BigDecimal
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** Unit test parser OCR nota (Phase 6: Mixue + separator ribuan + dd-MM-yyyy). */
class ReceiptParserTest {

    // Kasus dari user: Mixue, Ice Cream Tofee Hazelnut Latte (M), 2 x 21.000
    @Test
    fun `parse nota Mixue dengan separator ribuan dan tanggal`() {
        val raw = """
            Mixue
            Tanggal: 25-08-2026
            Ice Cream Tofee Hazelnut Latte (M)
            2 x 21.000
            Total 42.000
        """.trimIndent()

        val result = ReceiptParser.parse(raw)

        assertEquals("Mixue", result.merchant)
        assertEquals("25-08-2026", result.date)
        assertEquals(1, result.items.size)

        val item = result.items.first()
        assertEquals("Ice Cream Tofee Hazelnut Latte (M)", item.name)
        assertEquals("2", item.qty)
        assertEquals("21.000", item.price)
        // lineTotal = 2 x 21000
        assertEquals(
            BigDecimal("42000"),
            ReceiptParser.parsePriceToDecimal(item.price)?.times(item.qty.toBigDecimal()),
        )
    }

    @Test
    fun `parsePriceToDecimal menghilangkan separator dan prefix Rp`() {
        assertEquals(BigDecimal("21000"), ReceiptParser.parsePriceToDecimal("21.000"))
        assertEquals(BigDecimal("21000"), ReceiptParser.parsePriceToDecimal("Rp21.000"))
        assertEquals(BigDecimal("21000"), ReceiptParser.parsePriceToDecimal("21,000"))
        assertEquals(BigDecimal("15000"), ReceiptParser.parsePriceToDecimal("15000"))
        assertEquals(BigDecimal("250000"), ReceiptParser.parsePriceToDecimal("Rp 250.000"))
    }

    @Test
    fun `formatPrice menambah separator ribuan`() {
        assertEquals("21.000", ReceiptParser.formatPrice(BigDecimal("21000")))
        assertEquals("1.500.000", ReceiptParser.formatPrice(BigDecimal("1500000")))
    }

    @Test
    fun `parse harga di baris nama dengan qty mark x`() {
        val item = ReceiptParser.parseLine("Es Teh 2x 5000")
        assertEquals("Es Teh", item?.name)
        assertEquals("2", item?.qty)
        assertEquals("5.000", item?.price)
    }

    @Test
    fun `parse harga di baris nama dengan qty terpisah`() {
        val item = ReceiptParser.parseLine("Ayam Geprek 2 25000")
        assertEquals("Ayam Geprek", item?.name)
        assertEquals("2", item?.qty)
        assertEquals("25.000", item?.price)
    }

    @Test
    fun `baris qty x harga tanpa nama attach ke item terakhir`() {
        val raw = """
            Kopi Susu
            1 x 18000
        """.trimIndent()

        val result = ReceiptParser.parse(raw)

        assertEquals(1, result.items.size)
        assertEquals("Kopi Susu", result.items.first().name)
        assertEquals("1", result.items.first().qty)
        assertEquals("18.000", result.items.first().price)
    }

    @Test
    fun `tanggal berbagai format dinormalisasi dd-MM-yyyy`() {
        assertEquals("25-08-2026", ReceiptParser.parse("Nota\n25/08/2026\nTotal 1000").date)
        assertEquals("25-08-2026", ReceiptParser.parse("Nota\n25.08.2026\nTotal 1000").date)
        assertEquals("03-12-2026", ReceiptParser.parse("Nota\n03/12/2026\nTotal 1000").date)
        assertNull(ReceiptParser.parse("Nota\nTotal 1000").date)
    }

    @Test
    fun `tanggal tidak valid tidak menjadi date`() {
        // bulan 13 tidak valid
        assertNull(ReceiptParser.parse("Nota\n13-13-2026\nTotal 1000").date)
    }

    @Test
    fun `nama item mempertahankan tanda kurung`() {
        val raw = """
            Mixue
            Ice Cream Tofee Hazelnut Latte (M)
            2 x 21.000
        """.trimIndent()

        val item = ReceiptParser.parse(raw).items.first()
        assertEquals("Ice Cream Tofee Hazelnut Latte (M)", item.name)
    }

    @Test
    fun `baris total dan header tidak menjadi item`() {
        val raw = """
            Mixue
            Tanggal: 25-08-2026
            Item Qty Harga
            Ice Cream Tofee Hazelnut Latte (M)
            2 x 21.000
            Total 42.000
            Bayar: 50.000
            Kembalian 8.000
        """.trimIndent()

        val result = ReceiptParser.parse(raw)

        assertEquals(1, result.items.size)
        assertEquals("Ice Cream Tofee Hazelnut Latte (M)", result.items.first().name)
        assertTrue(result.items.none { it.name.contains("Total") || it.name.contains("Bayar") })
    }

    @Test
    fun `merchant fallback dari baris non-numerik pertama`() {
        val raw = """
            Tanggal: 25-08-2026
            Mixue
            Ice Cream Tofee Hazelnut Latte (M)
            2 x 21.000
        """.trimIndent()

        val result = ReceiptParser.parse(raw)
        assertEquals("Mixue", result.merchant)
        assertEquals("25-08-2026", result.date)
        assertEquals(1, result.items.size)
        assertEquals("Ice Cream Tofee Hazelnut Latte (M)", result.items.first().name)
    }

    @Test
    fun `parse kosong menghasilkan merchant dan items kosong`() {
        val result = ReceiptParser.parse("")
        assertEquals("", result.merchant)
        assertTrue(result.items.isEmpty())
        assertNull(result.date)
    }
}
