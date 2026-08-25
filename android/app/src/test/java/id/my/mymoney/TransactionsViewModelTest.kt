package id.my.mymoney

import id.my.mymoney.data.model.TransactionListResponse
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.ui.transactions.TransactionsViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class TransactionsViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() = Dispatchers.setMain(dispatcher)

    @After
    fun tearDown() = Dispatchers.resetMain()

    private fun tx(id: String): TransactionResponse = TransactionResponse(
        id = id,
        type = "expense",
        total_amount = "10000.00",
        category_id = "cat-1",
        account_id = "acc-1",
        merchant = "Merchant $id",
        source = "api",
        transaction_date = "2026-08-25T10:00:00+07:00",
        created_at = "2026-08-25T10:00:00+07:00",
        updated_at = "2026-08-25T10:00:00+07:00",
        items = emptyList(),
    )

    @Test
    fun `first page loads and clears loading`() = runTest(dispatcher) {
        val api = FakeApiService().apply {
            txPage = { TransactionListResponse(listOf(tx("1"), tx("2")), next_cursor = null, total_count = 2) }
        }
        val vm = TransactionsViewModel(api)
        advanceUntilIdle()

        val s = vm.uiState.value
        assertEquals(2, s.items.size)
        assertEquals(false, s.initialLoading)
        assertNull(s.error)
    }

    @Test
    fun `load more appends next page`() = runTest(dispatcher) {
        val api = FakeApiService().apply {
            txPage = { cursor ->
                if (cursor == null) {
                    TransactionListResponse(listOf(tx("1")), next_cursor = "cursor-1", total_count = 2)
                } else {
                    TransactionListResponse(listOf(tx("2")), next_cursor = null, total_count = 2)
                }
            }
        }
        val vm = TransactionsViewModel(api)
        advanceUntilIdle()
        assertEquals(1, vm.uiState.value.items.size)

        vm.loadMore()
        advanceUntilIdle()

        assertEquals(2, vm.uiState.value.items.size)
        assertEquals("2", vm.uiState.value.items.last().id)
    }

    @Test
    fun `load more does nothing without cursor`() = runTest(dispatcher) {
        val api = FakeApiService().apply {
            txPage = { TransactionListResponse(listOf(tx("1")), next_cursor = null, total_count = 1) }
        }
        val vm = TransactionsViewModel(api)
        advanceUntilIdle()

        vm.loadMore()
        advanceUntilIdle()

        assertEquals(1, vm.uiState.value.items.size)
    }

    @Test
    fun `error state is exposed when load fails`() = runTest(dispatcher) {
        val api = FakeApiService().apply { txShouldFail = true }
        val vm = TransactionsViewModel(api)
        advanceUntilIdle()

        assertTrue(vm.uiState.value.items.isEmpty())
        assertTrue(vm.uiState.value.error != null)
    }

    @Test
    fun `delete removes item from list`() = runTest(dispatcher) {
        val api = FakeApiService().apply {
            txPage = { TransactionListResponse(listOf(tx("1"), tx("2")), next_cursor = null, total_count = 2) }
        }
        val vm = TransactionsViewModel(api)
        advanceUntilIdle()
        var deletedOk = false

        vm.delete(vm.uiState.value.items.first()) { deletedOk = it }
        advanceUntilIdle()

        assertTrue(deletedOk)
        assertEquals(1, vm.uiState.value.items.size)
        assertEquals("2", vm.uiState.value.items.first().id)
        assertEquals(listOf("1"), api.deleted)
    }
}
