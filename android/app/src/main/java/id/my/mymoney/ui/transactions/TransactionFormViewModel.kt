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
import id.my.mymoney.data.model.PendingReceiptData
import id.my.mymoney.data.model.TransactionCreateRequest
import id.my.mymoney.data.model.TransactionItemCreate
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.data.model.TransactionUpdateRequest
import id.my.mymoney.data.toUserMessage
import id.my.mymoney.ui.receipt.ReceiptItem
import java.math.BigDecimal
import java.time.OffsetDateTime
import java.time.format.DateTimeFormatter
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Satu-satunya form transaksi (DESIGN.md §8.2): multi-item, dipakai oleh
 * tombol "+", edit, maupun kamera (via [pendingReceipt] dari alur OCR).
 * Konsep = form New from Receipt lama, kini menjadi "New Transaction".
 */
class TransactionFormViewModel(
    private val api: ApiService,
    private val pendingReceipt: MutableStateFlow<PendingReceiptData?>,
) : ViewModel() {

    data class UiState(
        val categories: List<CategoryResponse> = emptyList(),
        val accounts: List<AccountResponse> = emptyList(),
        val editing: TransactionResponse? = null,
        val items: List<ReceiptItem> = emptyList(),
        val merchant: String = "",
        val type: String = "expense",
        val loading: Boolean = false,
        val saving: Boolean = false,
        val error: String? = null,
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    fun loadOptions(onLoaded: (() -> Unit)? = null) {
        if (_uiState.value.loading) return
        _uiState.value = _uiState.value.copy(loading = true)
        viewModelScope.launch {
            runCatching {
                val cats = api.categories()
                val accs = api.accounts()
                cats to accs
            }.onSuccess {
                _uiState.value = _uiState.value.copy(
                    categories = it.first.filter { c -> c.is_active },
                    // 4.4: dropdown akun = is_active saja, urut alfabetis konsisten.
                    accounts = it.second.filter { a -> a.is_active }
                        .sortedBy { a -> a.account_name.lowercase() },
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
                    _uiState.value = _uiState.value.copy(
                        editing = it,
                        type = it.type,
                        merchant = it.merchant ?: "",
                        items = it.items.map { item ->
                            ReceiptItem(name = item.name, qty = item.qty, price = item.price)
                        },
                    )
                    onLoaded(it)
                }
                .onFailure { _uiState.value = _uiState.value.copy(error = it.toUserMessage()) }
        }
    }

    /**
     * Ambil hasil OCR kamera (jika ada) untuk mengisi form New Transaction.
     * Mengosongkan pendingReceipt agar tidak bocor ke form berikutnya.
     */
    fun applyPendingReceipt(onPrefill: ((PendingReceiptData) -> Unit)? = null) {
        val pending = pendingReceipt.value ?: return
        pendingReceipt.value = null
        _uiState.value = _uiState.value.copy(
            type = pending.type,
            merchant = pending.merchant,
            items = pending.items.map { ReceiptItem(name = it.name, qty = it.qty, price = it.price) },
        )
        onPrefill?.invoke(pending)
    }

    fun setType(value: String) {
        _uiState.value = _uiState.value.copy(type = value)
    }

    fun setMerchant(value: String) {
        _uiState.value = _uiState.value.copy(merchant = value)
    }

    fun updateItem(index: Int, item: ReceiptItem) {
        val items = _uiState.value.items.toMutableList()
        if (index in items.indices) items[index] = item
        _uiState.value = _uiState.value.copy(items = items)
    }

    fun removeItem(index: Int) {
        val items = _uiState.value.items.toMutableList()
        if (index in items.indices) items.removeAt(index)
        _uiState.value = _uiState.value.copy(items = items)
    }

    fun addItem() {
        _uiState.value = _uiState.value.copy(
            items = _uiState.value.items + ReceiptItem(name = "", qty = "1", price = "0"),
        )
    }

    val total: BigDecimal
        get() = _uiState.value.items.fold(BigDecimal.ZERO) { acc, item -> acc + item.lineTotal }

    fun create(
        type: String,
        totalAmount: BigDecimal,
        categoryId: String,
        accountId: String,
        merchant: String?,
        note: String?,
        transactionDate: OffsetDateTime,
        items: List<ReceiptItem>,
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
                items = items.map { item ->
                    TransactionItemCreate(name = item.name, qty = item.qty, price = item.price)
                },
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
        items: List<ReceiptItem>,
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
                items = items.map { item ->
                    TransactionItemCreate(name = item.name, qty = item.qty, price = item.price)
                },
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
                TransactionFormViewModel(app.container.api, app.container.pendingReceipt)
            }
        }
    }
}
