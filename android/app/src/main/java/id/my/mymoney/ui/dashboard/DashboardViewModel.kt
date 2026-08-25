package id.my.mymoney.ui.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import id.my.mymoney.MyMoneyApp
import id.my.mymoney.data.api.ApiService
import id.my.mymoney.data.model.AccountResponse
import id.my.mymoney.data.model.CategoryResponse
import id.my.mymoney.data.model.ReportSummaryResponse
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.data.toUserMessage
import java.math.BigDecimal
import java.time.LocalDate
import kotlinx.coroutines.async
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Period options mirroring backend `period` query arg. */
enum class ReportPeriod(val apiValue: String, val label: String) {
    TODAY("today", "Today"),
    WEEK("week", "This Week"),
    MONTH("month", "This Month"),
    CUSTOM("custom", "Custom"),
}

class DashboardViewModel(private val api: ApiService) : ViewModel() {

    data class UiState(
        val period: ReportPeriod = ReportPeriod.MONTH,
        val customStart: LocalDate? = null,
        val customEnd: LocalDate? = null,
        val summary: ReportSummaryResponse? = null,
        val accounts: List<AccountResponse> = emptyList(),
        val categories: List<CategoryResponse> = emptyList(),
        val recentTransactions: List<TransactionResponse> = emptyList(),
        val loading: Boolean = false,
        val error: String? = null,
    ) {
        /** Saldo total gabungan akun aktif (DESIGN.md §8.1). */
        val totalBalance: BigDecimal
            get() = accounts
                .filter { it.is_active }
                .fold(BigDecimal.ZERO) { acc, account -> acc + account.currentBalanceDecimal }
    }

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun selectPeriod(period: ReportPeriod) {
        if (_uiState.value.period == period && _uiState.value.summary != null) return
        _uiState.value = _uiState.value.copy(period = period, error = null)
        load()
    }

    /** Periode kustom: from/to (end exclusive di backend). */
    fun selectCustomPeriod(start: LocalDate, end: LocalDate) {
        _uiState.value = _uiState.value.copy(
            period = ReportPeriod.CUSTOM,
            customStart = start,
            customEnd = end,
            error = null,
        )
        load()
    }

    fun refresh() = load()

    /**
     * Report summary adalah sumber utama — kegagalannya menampilkan error screen.
     * Accounts/categories/transactions bersifat sekunder: gagal = degrade (list kosong),
     * tidak memblokir layar.
     */
    private fun load() {
        val state = _uiState.value
        val period = state.period
        val start = if (period == ReportPeriod.CUSTOM) state.customStart?.toString() else null
        val end = if (period == ReportPeriod.CUSTOM) state.customEnd?.toString() else null
        _uiState.value = _uiState.value.copy(loading = true, error = null)
        viewModelScope.launch {
            val summaryDeferred = async {
                runCatching { api.reportSummary(period = period.apiValue, start = start, end = end) }
            }
            val accountsDeferred = async { runCatching { api.accounts() } }
            val categoriesDeferred = async { runCatching { api.categories() } }
            val txDeferred = async { runCatching { api.transactions() } }

            val summaryRes = summaryDeferred.await()
            val accountsRes = accountsDeferred.await()
            val categoriesRes = categoriesDeferred.await()
            val txRes = txDeferred.await()

            _uiState.value = _uiState.value.copy(
                summary = summaryRes.getOrNull(),
                accounts = accountsRes.getOrDefault(emptyList()),
                categories = categoriesRes.getOrDefault(emptyList()),
                recentTransactions = txRes.getOrNull()?.items.orEmpty(),
                loading = false,
                error = summaryRes.exceptionOrNull()?.toUserMessage(),
            )
        }
    }

    companion object {
        val Factory = viewModelFactory {
            initializer {
                val app = this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY] as MyMoneyApp
                DashboardViewModel(app.container.api)
            }
        }
    }
}
