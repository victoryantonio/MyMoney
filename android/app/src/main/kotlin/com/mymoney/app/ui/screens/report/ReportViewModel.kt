package com.mymoney.app.ui.screens.report

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mymoney.app.data.model.DailyTrend
import com.mymoney.app.data.model.ReportSummary
import com.mymoney.app.data.repository.ReportRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class ReportUiState(
    val isLoading: Boolean = false,
    val summary: ReportSummary? = null,
    val trend: List<DailyTrend> = emptyList(),
    val error: String? = null,
)

@HiltViewModel
class ReportViewModel @Inject constructor(
    private val reportRepository: ReportRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(ReportUiState(isLoading = true))
    val uiState: StateFlow<ReportUiState> = _uiState.asStateFlow()

    init {
        loadReport()
    }

    fun loadReport(dateFrom: String? = null, dateTo: String? = null) {
        viewModelScope.launch {
            _uiState.value = ReportUiState(isLoading = true)
            try {
                val summary = reportRepository.summary(dateFrom, dateTo)
                val trend = reportRepository.trend(dateFrom, dateTo)
                _uiState.value = ReportUiState(summary = summary, trend = trend)
            } catch (e: Exception) {
                _uiState.value = ReportUiState(error = "Gagal memuat laporan.")
            }
        }
    }
}
