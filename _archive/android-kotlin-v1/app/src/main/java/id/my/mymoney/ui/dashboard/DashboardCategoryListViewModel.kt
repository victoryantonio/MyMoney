package id.my.mymoney.ui.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import id.my.mymoney.MyMoneyApp
import id.my.mymoney.data.api.ApiService
import id.my.mymoney.data.model.CategoryResponse
import id.my.mymoney.data.model.ReportSummaryResponse
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.data.toUserMessage
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Daftar kategori + transaksi per tipe (income/expense) — layar yang dibuka
 * saat card Income/Expense di Dashboard diketuk (DESIGN.md §8.5).
 */
class DashboardCategoryListViewModel(
    private val api: ApiService,
    private val type: String,
) : ViewModel() {

    data class UiState(
        val type: String = "expense",
        val summary: ReportSummaryResponse? = null,
        val categories: List<CategoryResponse> = emptyList(),
        val transactions: List<TransactionResponse> = emptyList(),
        val loading: Boolean = false,
        val error: String? = null,
    )

    private val _uiState = MutableStateFlow(UiState(type = type))
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun refresh() = load()

    private fun load() {
        _uiState.value = _uiState.value.copy(loading = true, error = null)
        viewModelScope.launch {
            val summaryDeferred = async { runCatching { api.reportSummary(period = "month") } }
            val catsDeferred = async { runCatching { api.categories() } }
            val txDeferred = async {
                runCatching { api.transactions(type = type.takeIf { it == "income" || it == "expense" }) }
            }

            val summaryRes = summaryDeferred.await()
            val catsRes = catsDeferred.await()
            val txRes = txDeferred.await()

            _uiState.value = _uiState.value.copy(
                summary = summaryRes.getOrNull(),
                categories = catsRes.getOrDefault(emptyList()),
                transactions = txRes.getOrNull()?.items.orEmpty(),
                loading = false,
                error = summaryRes.exceptionOrNull()?.toUserMessage(),
            )
        }
    }

    companion object {
        fun factory(type: String) = viewModelFactory {
            initializer {
                val app = this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY] as MyMoneyApp
                DashboardCategoryListViewModel(app.container.api, type)
            }
        }
    }
}
