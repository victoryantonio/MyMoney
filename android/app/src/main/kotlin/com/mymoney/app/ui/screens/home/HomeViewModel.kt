package com.mymoney.app.ui.screens.home

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mymoney.app.data.model.AccountResponse
import com.mymoney.app.data.model.ReportSummary
import com.mymoney.app.data.repository.AccountRepository
import com.mymoney.app.data.repository.ReportRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HomeUiState(
    val isLoading: Boolean = false,
    val accounts: List<AccountResponse> = emptyList(),
    val summary: ReportSummary? = null,
    val error: String? = null,
)

@HiltViewModel
class HomeViewModel @Inject constructor(
    private val accountRepository: AccountRepository,
    private val reportRepository: ReportRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(HomeUiState(isLoading = true))
    val uiState: StateFlow<HomeUiState> = _uiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
        viewModelScope.launch {
            _uiState.value = HomeUiState(isLoading = true)
            try {
                val accounts = accountRepository.list()
                val summary = reportRepository.summary()
                _uiState.value = HomeUiState(accounts = accounts, summary = summary)
            } catch (e: Exception) {
                _uiState.value = HomeUiState(error = "Gagal memuat data.")
            }
        }
    }
}
