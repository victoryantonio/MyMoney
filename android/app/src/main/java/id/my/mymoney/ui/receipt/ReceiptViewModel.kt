package id.my.mymoney.ui.receipt

import android.graphics.Bitmap
import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import com.google.android.gms.tasks.Task
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.latin.TextRecognizerOptions
import id.my.mymoney.MyMoneyApp
import id.my.mymoney.data.api.ApiService
import id.my.mymoney.data.model.AccountResponse
import id.my.mymoney.data.model.CategoryResponse
import id.my.mymoney.data.model.TransactionCreateRequest
import id.my.mymoney.data.model.TransactionItemCreate
import id.my.mymoney.data.toUserMessage
import java.math.BigDecimal
import kotlin.coroutines.resume
import kotlin.coroutines.resumeWithException
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext

/** Satu baris item hasil parse nota (bisa diedit manual). */
data class ReceiptItem(
    val name: String,
    val qty: String,
    val price: String,
) {
    val lineTotal: BigDecimal
        get() = runCatching {
            (qty.toBigDecimalOrNull() ?: BigDecimal.ONE) * (price.toBigDecimalOrNull() ?: BigDecimal.ZERO)
        }.getOrDefault(BigDecimal.ZERO)
}

class ReceiptViewModel(private val api: ApiService) : ViewModel() {

    data class UiState(
        val items: List<ReceiptItem> = emptyList(),
        val merchant: String = "",
        val type: String = "expense",
        val categories: List<CategoryResponse> = emptyList(),
        val accounts: List<AccountResponse> = emptyList(),
        val ocrText: String = "",
        val processing: Boolean = false,
        val saving: Boolean = false,
        val error: String? = null,
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    fun loadOptions() {
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
                )
            }.onFailure {
                _uiState.value = _uiState.value.copy(error = it.toUserMessage())
            }
        }
    }

    /** Jalankan ML Kit OCR lalu parse baris nota jadi items. */
    fun processBitmap(bitmap: Bitmap) {
        if (_uiState.value.processing) return
        _uiState.value = _uiState.value.copy(processing = true, error = null)
        viewModelScope.launch {
            val result = runCatching {
                withContext(Dispatchers.Default) {
                    val recognizer = TextRecognition.getClient(TextRecognizerOptions.DEFAULT_OPTIONS)
                    val image = InputImage.fromBitmap(bitmap, 0)
                    val text = recognizer.process(image).await()
                    text.text
                }
            }
            result.onSuccess { raw ->
                val parsed = ReceiptParser.parse(raw)
                _uiState.value = _uiState.value.copy(
                    items = parsed.items,
                    merchant = parsed.merchant,
                    ocrText = raw,
                    processing = false,
                )
            }.onFailure {
                _uiState.value = _uiState.value.copy(processing = false, error = it.toUserMessage())
            }
        }
    }

    fun setMerchant(value: String) {
        _uiState.value = _uiState.value.copy(merchant = value)
    }

    fun setType(value: String) {
        _uiState.value = _uiState.value.copy(type = value)
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

    fun setError(message: String?) {
        _uiState.value = _uiState.value.copy(error = message)
    }

    val total: BigDecimal
        get() = _uiState.value.items.fold(BigDecimal.ZERO) { acc, item -> acc + item.lineTotal }

    /**
     * Simpan SEMUA baris item sebagai SATU transaksi (contoh: nota Mi Gacoan
     * = satu transaksi dengan banyak line item). Total = jumlah qty×price.
     */
    fun save(
        categoryId: String,
        accountId: String,
        note: String?,
        onDone: (Boolean, String?) -> Unit,
    ) {
        if (_uiState.value.saving) return
        val items = _uiState.value.items.filter {
            it.name.isNotBlank() && (it.price.toBigDecimalOrNull() ?: BigDecimal.ZERO) > BigDecimal.ZERO
        }
        if (items.isEmpty()) {
            onDone(false, "Tambahkan minimal satu item dengan harga valid")
            return
        }
        val totalAmount = items.fold(BigDecimal.ZERO) { acc, item -> acc + item.lineTotal }
        if (totalAmount <= BigDecimal.ZERO) {
            onDone(false, "Total harus lebih dari 0")
            return
        }
        _uiState.value = _uiState.value.copy(saving = true, error = null)
        viewModelScope.launch {
            val request = TransactionCreateRequest(
                type = _uiState.value.type,
                total_amount = totalAmount.toPlainString(),
                category_id = categoryId,
                account_id = accountId,
                merchant = _uiState.value.merchant.takeIf { it.isNotBlank() },
                note = note?.takeIf { it.isNotBlank() },
                transaction_date = java.time.OffsetDateTime.now()
                    .format(java.time.format.DateTimeFormatter.ISO_OFFSET_DATE_TIME),
                items = items.map {
                    TransactionItemCreate(name = it.name, qty = it.qty, price = it.price)
                },
            )
            val result = runCatching { api.createTransaction(request) }
            _uiState.value = _uiState.value.copy(saving = false)
            result.onSuccess { onDone(true, null) }
                .onFailure { onDone(false, it.toUserMessage()) }
        }
    }

    companion object {
        val Factory = viewModelFactory {
            initializer {
                val app = this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY] as MyMoneyApp
                ReceiptViewModel(app.container.api)
            }
        }
    }
}

/** Await helper untuk ML Kit Task (play-services-tasks). */
private suspend fun <T> Task<T>.await(): T =
    kotlinx.coroutines.suspendCancellableCoroutine { cont ->
        addOnSuccessListener { result -> cont.resume(result) }
        addOnFailureListener { e -> cont.resumeWithException(e) }
        addOnCanceledListener { cont.cancel() }
    }
