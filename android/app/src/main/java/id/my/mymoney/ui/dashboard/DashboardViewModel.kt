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
import id.my.mymoney.data.model.ReportTrendResponse
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.data.model.TrendPoint
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
        val trend: ReportTrendResponse? = null,
        val accounts: List<AccountResponse> = emptyList(),
        val categories: List<CategoryResponse> = emptyList(),
        val recentTransactions: List<TransactionResponse> = emptyList(),
        /** Semua halaman transaksi (cursor loop) — dipakai filter akun client-side. */
        val allTransactions: List<TransactionResponse> = emptyList(),
        /** Akun terpilih untuk filter. KOSONG = semua akun (default). */
        val selectedAccountIds: Set<String> = emptySet(),
        val loading: Boolean = false,
        val error: String? = null,
    ) {
        /** Saldo total gabungan akun aktif (DESIGN.md §8.1). */
        val totalBalance: BigDecimal
            get() = accounts
                .filter { it.is_active }
                .fold(BigDecimal.ZERO) { acc, account -> acc + account.currentBalanceDecimal }

        /** null = semua akun; non-null = subset akun yang difilter. */
        val activeAccountFilter: Set<String>?
            get() = if (selectedAccountIds.isEmpty()) null else selectedAccountIds

        private fun periodStart(): LocalDate {
            val today = LocalDate.now()
            return when (period) {
                ReportPeriod.TODAY -> today
                ReportPeriod.WEEK -> today.minusDays((today.dayOfWeek.value - 1).toLong())
                ReportPeriod.MONTH -> today.withDayOfMonth(1)
                ReportPeriod.CUSTOM -> customStart ?: today.minusDays(30)
            }
        }

        private fun periodEnd(): LocalDate {
            val today = LocalDate.now()
            return when (period) {
                ReportPeriod.TODAY -> today
                ReportPeriod.WEEK -> today
                ReportPeriod.MONTH -> today
                ReportPeriod.CUSTOM -> customEnd ?: today
            }
        }

        /** Transaksi pada periode saat ini + akun terpilih (client-side filter). */
        val filteredTransactions: List<TransactionResponse>
            get() {
                val active = activeAccountFilter ?: return emptyList()
                val start = periodStart()
                val end = periodEnd()
                return allTransactions.filter { tx ->
                    tx.account_id in active && runCatching {
                        val date = LocalDate.parse(tx.transaction_date.take(10))
                        !date.isBefore(start) && !date.isAfter(end)
                    }.getOrDefault(true)
                }
            }

        /** Income akun terpilih dalam periode (untuk donut saat filter aktif). */
        val filteredIncome: BigDecimal
            get() = filteredTransactions
                .filter { !it.isExpense }
                .fold(BigDecimal.ZERO) { acc, tx -> acc + tx.totalAmountDecimal }

        /** Expense akun terpilih dalam periode (untuk donut saat filter aktif). */
        val filteredExpense: BigDecimal
            get() = filteredTransactions
                .filter { it.isExpense }
                .fold(BigDecimal.ZERO) { acc, tx -> acc + tx.totalAmountDecimal }

        /**
         * Tren harian client-side saat filter akun aktif: bucket per tanggal
         * (satu pass agregasi — tanpa N+1), diurutkan naik.
         */
        val filteredTrendPoints: List<TrendPoint>
            get() {
                val active = activeAccountFilter ?: return emptyList()
                val start = periodStart()
                val end = periodEnd()
                val buckets = LinkedHashMap<LocalDate, Pair<BigDecimal, BigDecimal>>()
                allTransactions.forEach { tx ->
                    if (tx.account_id !in active) return@forEach
                    val date = runCatching {
                        LocalDate.parse(tx.transaction_date.take(10))
                    }.getOrNull() ?: return@forEach
                    if (date.isBefore(start) || date.isAfter(end)) return@forEach
                    val (inc, exp) = buckets[date] ?: (BigDecimal.ZERO to BigDecimal.ZERO)
                    if (tx.isExpense) {
                        buckets[date] = inc to (exp + tx.totalAmountDecimal)
                    } else {
                        buckets[date] = (inc + tx.totalAmountDecimal) to exp
                    }
                }
                return buckets.toSortedMap().map { (date, pair) ->
                    TrendPoint(
                        date = date.toString(),
                        income = pair.first.toPlainString(),
                        expense = pair.second.toPlainString(),
                    )
                }
            }
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

    /** Pilih/nonaktifkan satu akun; menutup akun lain mengosongkan set = semua. */
    fun toggleAccount(accountId: String) {
        val state = _uiState.value
        val current = state.selectedAccountIds
        val updated = when {
            // Dari "semua" → pilih semua kecuali yang ditoggle (deselect satu).
            current.isEmpty() -> state.accounts.map { it.id }.toSet() - accountId
            accountId in current -> current - accountId
            else -> current + accountId
        }
        _uiState.value = state.copy(selectedAccountIds = updated)
    }

    /** Kembali ke semua akun. */
    fun selectAllAccounts() {
        _uiState.value = _uiState.value.copy(selectedAccountIds = emptySet())
    }

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
            val trendDeferred = async {
                runCatching { api.reportTrend(period = period.apiValue, start = start, end = end) }
            }
            val accountsDeferred = async { runCatching { api.accounts() } }
            val categoriesDeferred = async { runCatching { api.categories() } }
            // Ambil SEMUA halaman transaksi sekali (cursor loop) — dipakai untuk
            // filter akun client-side + recent transactions. Bukan N+1: satu loop
            // berurutan, bukan query per-akun.
            val txDeferred = async { runCatching { fetchAllTransactions() } }

            val summaryRes = summaryDeferred.await()
            val trendRes = trendDeferred.await()
            val accountsRes = accountsDeferred.await()
            val categoriesRes = categoriesDeferred.await()
            val txRes = txDeferred.await()

            _uiState.value = _uiState.value.copy(
                summary = summaryRes.getOrNull(),
                trend = trendRes.getOrNull(),
                accounts = accountsRes.getOrDefault(emptyList()),
                categories = categoriesRes.getOrDefault(emptyList()),
                allTransactions = txRes.getOrDefault(emptyList()),
                recentTransactions = txRes.getOrNull().orEmpty().take(20),
                loading = false,
                error = summaryRes.exceptionOrNull()?.toUserMessage(),
            )
        }
    }

    /** Keyset pagination loop — baca semua halaman transaksi (terbaru → lama). */
    private suspend fun fetchAllTransactions(): List<TransactionResponse> {
        val all = mutableListOf<TransactionResponse>()
        var cursor: String? = null
        do {
            val page = api.transactions(cursor = cursor)
            all += page.items
            cursor = page.next_cursor
        } while (cursor != null && all.size < 2000) // guard tak terbatas
        return all
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
