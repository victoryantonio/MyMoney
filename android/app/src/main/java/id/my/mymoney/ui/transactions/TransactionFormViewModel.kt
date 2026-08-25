package id.my.mymoney.ui.transactions

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import id.my.mymoney.MyMoneyApp
import id.my.mymoney.data.api.ApiService
import id.my.mymoney.data.model.AccountResponse
import id.my.mymoney.data.model.CategoryResponse
import id.my.mymoney.data.model.TransactionCreateRequest
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.data.model.TransactionUpdateRequest
import id.my.mymoney.data.toUserMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.math.BigDecimal
import java.time.OffsetDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

class TransactionFormViewModel(private val api: ApiService) : ViewModel() {

    data class UiState(
        val categories: List<CategoryResponse> = emptyList(),
        val accounts: List<AccountResponse> = emptyList(),
        val editing: TransactionResponse? = null,
        val loading: Boolean = false,
        val saving: Boolean = false,
        val error: String? = null,
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    fun loadOptions(onLoaded: (() -> Unit)? = null) {
        _uiState.value = _uiState.value.copy(loading = true)
        viewModelScope.launch {
            runCatching {
                val cats = api.categories()
                val accs = api.accounts()
                cats to accs
            }.onSuccess {
                _uiState.value = _uiState.value.copy(
                    categories = it.first.filter { c -> c.is_active },
                    accounts = it.second.filter { a -> a.is_active },
                    loading = false,
                )
                onLoaded?.invoke()
            }.onFailure {
                _uiState.value = _uiState.value.copy(loading = false, error = it.toUserMessage())
            }
        }
    }

    fun loadTransaction(txId: String, onLoaded: (TransactionResponse) -> Unit) {
        viewModelScope.launch {
            runCatching { api.transaction(txId) }
                .onSuccess {
                    _uiState.value = _uiState.value.copy(editing = it)
                    onLoaded(it)
                }
                .onFailure { _uiState.value = _uiState.value.copy(error = it.toUserMessage()) }
        }
    }

    fun create(
        type: String,
        totalAmount: BigDecimal,
        categoryId: String,
        accountId: String,
        merchant: String?,
        note: String?,
        transactionDate: OffsetDateTime,
        onDone: (Boolean, String?) -> Unit,
    ) {
        if (_uiState.value.saving) return
        _uiState.value = _uiState.value.copy(saving = true, error = null)
        viewModelScope.launch {
            val request = TransactionCreateRequest(
                type = type,
                total_amount = totalAmount.toPlainString(),
                category_id = categoryId,
                account_id = accountId,
                merchant = merchant?.takeIf { it.isNotBlank() },
                note = note?.takeIf { it.isNotBlank() },
                transaction_date = transactionDate.format(DateTimeFormatter.ISO_OFFSET_DATE_TIME),
            )
            val result = runCatching { api.createTransaction(request) }
            _uiState.value = _uiState.value.copy(saving = false)
            result.onSuccess { onDone(true, null) }
                .onFailure { onDone(false, it.toUserMessage()) }
        }
    }

    fun update(
        tx: TransactionResponse,
        type: String,
        totalAmount: BigDecimal,
        categoryId: String,
        accountId: String,
        merchant: String?,
        note: String?,
        transactionDate: OffsetDateTime,
        onDone: (Boolean, String?) -> Unit,
    ) {
        if (_uiState.value.saving) return
        _uiState.value = _uiState.value.copy(saving = true, error = null)
        viewModelScope.launch {
            val request = TransactionUpdateRequest(
                type = type,
                total_amount = totalAmount.toPlainString(),
                category_id = categoryId,
                account_id = accountId,
                merchant = merchant?.takeIf { it.isNotBlank() },
                note = note?.takeIf { it.isNotBlank() },
                transaction_date = transactionDate.format(DateTimeFormatter.ISO_OFFSET_DATE_TIME),
            )
            val result = runCatching { api.updateTransaction(tx.id, request) }
            _uiState.value = _uiState.value.copy(saving = false)
            result.onSuccess { onDone(true, null) }
                .onFailure { onDone(false, it.toUserMessage()) }
        }
    }

    companion object {
        val Factory = viewModelFactory {
            initializer {
                val app = this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY] as MyMoneyApp
                TransactionFormViewModel(app.container.api)
            }
        }
    }
}
