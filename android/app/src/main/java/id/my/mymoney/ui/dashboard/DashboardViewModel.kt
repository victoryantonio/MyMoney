package id.my.mymoney.ui.dashboard

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import id.my.mymoney.MyMoneyApp
import id.my.mymoney.data.api.ApiService
import id.my.mymoney.data.model.ReportSummaryResponse
import id.my.mymoney.data.toUserMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/** Period options mirroring backend `period` query arg. */
enum class ReportPeriod(val apiValue: String, val label: String) {
    TODAY("today", "Today"),
    WEEK("week", "This Week"),
    MONTH("month", "This Month"),
    LAST_MONTH("last-month", "Last Month"),
}

class DashboardViewModel(private val api: ApiService) : ViewModel() {

    data class UiState(
        val period: ReportPeriod = ReportPeriod.MONTH,
        val summary: ReportSummaryResponse? = null,
        val loading: Boolean = false,
        val error: String? = null,
    )

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

    fun refresh() = load()

    private fun load() {
        val period = _uiState.value.period
        _uiState.value = _uiState.value.copy(loading = true, error = null)
        viewModelScope.launch {
            runCatching { api.reportSummary(period = period.apiValue) }
                .onSuccess { _uiState.value = _uiState.value.copy(summary = it, loading = false) }
                .onFailure { _uiState.value = _uiState.value.copy(loading = false, error = it.toUserMessage()) }
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
