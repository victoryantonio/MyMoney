package id.my.mymoney

import id.my.mymoney.data.model.AccountResponse
import id.my.mymoney.data.model.CategoryResponse
import id.my.mymoney.data.model.CategoryTotal
import id.my.mymoney.data.model.ReportSummaryResponse
import id.my.mymoney.data.model.TransactionListResponse
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.ui.dashboard.DashboardViewModel
import id.my.mymoney.ui.dashboard.ReportPeriod
import java.math.BigDecimal
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DashboardViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    private fun summary(): ReportSummaryResponse = ReportSummaryResponse(
        start_date = "2026-08-01T00:00:00+07:00",
        end_date = "2026-09-01T00:00:00+07:00",
        total_income = "1000000.00",
        total_expense = "400000.00",
        net = "600000.00",
        categories = listOf(
            CategoryTotal(name = "Food", type = "expense", total = "250000.00"),
            CategoryTotal(name = "Transport", type = "expense", total = "150000.00"),
        ),
    )

    @Test
    fun `loads summary on init`() = runTest(dispatcher) {
        val api = FakeApiService().apply { report = summary() }
        val vm = DashboardViewModel(api)
        advanceUntilIdle()

        val s = vm.uiState.value
        assertNotNull(s.summary)
        assertEquals(ReportPeriod.MONTH, s.period)
        assertEquals("1000000.00", s.summary!!.total_income)
        assertEquals(2, s.summary!!.categories.size)
    }

    @Test
    fun `selecting period calls api with correct value`() = runTest(dispatcher) {
        val api = FakeApiService().apply { report = summary() }
        val vm = DashboardViewModel(api)
        advanceUntilIdle()
        api.reportPeriods.clear()

        vm.selectPeriod(ReportPeriod.LAST_MONTH)
        advanceUntilIdle()

        assertEquals("last-month", api.reportPeriods.last())
        assertEquals(ReportPeriod.LAST_MONTH, vm.uiState.value.period)
    }

    @Test
    fun `error state when report fails`() = runTest(dispatcher) {
        val api = FakeApiService().apply { reportShouldFail = true }
        val vm = DashboardViewModel(api)
        advanceUntilIdle()

        assertTrue(vm.uiState.value.error != null)
        assertNull(vm.uiState.value.summary)
    }

    @Test
    fun `loading flag clears after success`() = runTest(dispatcher) {
        val api = FakeApiService().apply { report = summary() }
        val vm = DashboardViewModel(api)
        advanceUntilIdle()

        assertEquals(false, vm.uiState.value.loading)
        assertEquals(false, vm.uiState.value.error != null)
    }

    private fun account(id: String, name: String, balance: String, active: Boolean = true) = AccountResponse(
        id = id,
        account_name = name,
        bank_name = "BCA",
        initial_balance = "0",
        current_balance = balance,
        is_active = active,
        created_at = "2026-08-25T10:00:00+07:00",
    )

    private fun tx(id: String, type: String, amount: String) = TransactionResponse(
        id = id,
        type = type,
        total_amount = amount,
        category_id = "cat-1",
        account_id = "acc-1",
        merchant = if (type == "expense") "Kopi" else "Gaji",
        source = "api",
        transaction_date = "2026-08-25T10:00:00+07:00",
        created_at = "2026-08-25T10:00:00+07:00",
        updated_at = "2026-08-25T10:00:00+07:00",
        items = emptyList(),
    )

    @Test
    fun `loads accounts and computes total balance from active accounts`() = runTest(dispatcher) {
        val api = FakeApiService().apply {
            report = summary()
            accountsList = listOf(
                account("acc-1", "Cash", "1500000.00"),
                account("acc-2", "Bank", "2500000.00"),
                account("acc-3", "Closed", "9999999.00", active = false),
            )
        }
        val vm = DashboardViewModel(api)
        advanceUntilIdle()

        val s = vm.uiState.value
        assertEquals(3, s.accounts.size)
        assertEquals(BigDecimal("4000000.00"), s.totalBalance)
    }

    @Test
    fun `loads recent transactions on init`() = runTest(dispatcher) {
        val api = FakeApiService().apply {
            report = summary()
            txPage = {
                TransactionListResponse(
                    items = listOf(tx("tx-1", "expense", "25000.00"), tx("tx-2", "income", "5000000.00")),
                    next_cursor = null,
                    total_count = 2,
                )
            }
        }
        val vm = DashboardViewModel(api)
        advanceUntilIdle()

        val s = vm.uiState.value
        assertEquals(2, s.recentTransactions.size)
        assertEquals("Kopi", s.recentTransactions.first().merchant)
        assertTrue(s.recentTransactions.first().isExpense)
    }

    @Test
    fun `secondary endpoints failing degrades gracefully without blocking screen`() = runTest(dispatcher) {
        val api = FakeApiService().apply {
            report = summary()
            accountsList = listOf(account("acc-1", "Cash", "1000000.00"))
            txPage = {
                TransactionListResponse(listOf(tx("tx-1", "expense", "25000.00")), null, 1)
            }
        }
        // Simulasikan gagal hanya di accounts (list kosong + error) dan tx.
        api.accountsList = emptyList()
        api.txPage = { throw java.io.IOException("tx down") }

        val vm = DashboardViewModel(api)
        advanceUntilIdle()

        val s = vm.uiState.value
        assertNotNull(s.summary) // Sumber utama tetap tampil
        assertNull(s.error) // Kegagalan sekunder tidak memblokir layar
        assertTrue(s.accounts.isEmpty())
        assertTrue(s.recentTransactions.isEmpty())
    }
}
