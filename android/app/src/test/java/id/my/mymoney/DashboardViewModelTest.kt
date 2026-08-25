package id.my.mymoney

import id.my.mymoney.data.model.CategoryTotal
import id.my.mymoney.data.model.ReportSummaryResponse
import id.my.mymoney.ui.dashboard.DashboardViewModel
import id.my.mymoney.ui.dashboard.ReportPeriod
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
}
