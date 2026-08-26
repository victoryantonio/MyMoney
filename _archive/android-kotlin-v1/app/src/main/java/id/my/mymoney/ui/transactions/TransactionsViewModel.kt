package id.my.mymoney.ui.transactions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import id.my.mymoney.MyMoneyApp
import id.my.mymoney.data.api.ApiService
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.data.toUserMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class TransactionsViewModel(private val api: ApiService) : ViewModel() {

    data class UiState(
        val items: List<TransactionResponse> = emptyList(),
        val nextCursor: String? = null,
        val totalCount: Int = 0,
        val initialLoading: Boolean = true,
        val loadingMore: Boolean = false,
        val refreshing: Boolean = false,
        val error: String? = null,
        val deleting: Boolean = false,
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        loadFirstPage()
    }

    fun loadFirstPage() {
        _uiState.value = UiState(initialLoading = true)
        viewModelScope.launch {
            runCatching { api.transactions(cursor = null) }
                .onSuccess {
                    _uiState.value = UiState(
                        items = it.items,
                        nextCursor = it.next_cursor,
                        totalCount = it.total_count,
                        initialLoading = false,
                    )
                }
                .onFailure {
                    _uiState.value = _uiState.value.copy(initialLoading = false, error = it.toUserMessage())
                }
        }
    }

    fun loadMore() {
        val s = _uiState.value
        val cursor = s.nextCursor ?: return
        if (s.loadingMore || s.initialLoading) return
        _uiState.value = s.copy(loadingMore = true, error = null)
        viewModelScope.launch {
            runCatching { api.transactions(cursor = cursor) }
                .onSuccess {
                    _uiState.value = _uiState.value.copy(
                        items = _uiState.value.items + it.items,
                        nextCursor = it.next_cursor,
                        totalCount = it.total_count,
                        loadingMore = false,
                    )
                }
                .onFailure {
                    _uiState.value = _uiState.value.copy(loadingMore = false, error = it.toUserMessage())
                }
        }
    }

    fun refresh() {
        val cursor = _uiState.value.nextCursor
        _uiState.value = _uiState.value.copy(refreshing = true, error = null)
        viewModelScope.launch {
            runCatching { api.transactions(cursor = cursor) }
                .onSuccess {
                    _uiState.value = UiState(
                        items = it.items,
                        nextCursor = it.next_cursor,
                        totalCount = it.total_count,
                        initialLoading = false,
                        refreshing = false,
                    )
                }
                .onFailure {
                    _uiState.value = _uiState.value.copy(refreshing = false, error = it.toUserMessage())
                }
        }
    }

    fun delete(tx: TransactionResponse, onDone: (Boolean) -> Unit = {}) {
        if (_uiState.value.deleting) return
        _uiState.value = _uiState.value.copy(deleting = true, error = null)
        viewModelScope.launch {
            val ok = runCatching { api.deleteTransaction(tx.id) }.isSuccess
            if (ok) {
                _uiState.value = _uiState.value.copy(
                    items = _uiState.value.items.filterNot { it.id == tx.id },
                    deleting = false,
                )
            } else {
                _uiState.value = _uiState.value.copy(deleting = false, error = "Failed to delete transaction")
            }
            onDone(ok)
        }
    }

    companion object {
        val Factory = viewModelFactory {
            initializer {
                val app = this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY] as MyMoneyApp
                TransactionsViewModel(app.container.api)
            }
        }
    }
}
