package com.mymoney.app.ui.screens.history

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mymoney.app.data.model.TransactionResponse
import com.mymoney.app.data.repository.TransactionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class HistoryUiState(
    val isLoading: Boolean = false,
    val isLoadingMore: Boolean = false,
    val transactions: List<TransactionResponse> = emptyList(),
    val nextCursor: String? = null,
    val hasMore: Boolean = false,
    val error: String? = null,
)

@HiltViewModel
class HistoryViewModel @Inject constructor(
    private val transactionRepository: TransactionRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(HistoryUiState(isLoading = true))
    val uiState: StateFlow<HistoryUiState> = _uiState.asStateFlow()

    init {
        loadTransactions()
    }

    fun loadTransactions() {
        viewModelScope.launch {
            _uiState.value = HistoryUiState(isLoading = true)
            try {
                val page = transactionRepository.list(limit = 20)
                _uiState.value = HistoryUiState(
                    transactions = page.data,
                    nextCursor = page.nextCursor,
                    hasMore = page.hasMore,
                )
            } catch (e: Exception) {
                _uiState.value = HistoryUiState(error = "Gagal memuat transaksi.")
            }
        }
    }

    fun loadMore() {
        val cursor = _uiState.value.nextCursor ?: return
        if (_uiState.value.isLoadingMore) return

        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(isLoadingMore = true)
            try {
                val page = transactionRepository.list(cursor = cursor, limit = 20)
                _uiState.value = _uiState.value.copy(
                    transactions = _uiState.value.transactions + page.data,
                    nextCursor = page.nextCursor,
                    hasMore = page.hasMore,
                    isLoadingMore = false,
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(isLoadingMore = false, error = "Gagal memuat lebih banyak.")
            }
        }
    }

    fun deleteTransaction(id: String) {
        viewModelScope.launch {
            try {
                transactionRepository.delete(id)
                // Remove locally for instant UI update
                _uiState.value = _uiState.value.copy(
                    transactions = _uiState.value.transactions.filter { it.id != id }
                )
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(error = "Gagal menghapus transaksi.")
            }
        }
    }
}
