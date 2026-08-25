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
import id.my.mymoney.data.model.PendingReceiptData
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

/**
 * Keyword yang menandakan nota adalah pemasukan (income). Default = expense
 * (user bisa toggle manual di form) — TASK 3: OCR classification.
 */
private val INCOME_KEYWORDS = listOf(
    "gaji", "salary", "income", "pendapatan", "pemasukan", "transfer masuk",
    "dana masuk", "topup", "top up", "credit", "uang masuk", "bonus", "dividen",
)

class ReceiptViewModel(
    private val api: ApiService,
    private val pendingReceipt: MutableStateFlow<PendingReceiptData?>,
) : ViewModel() {

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

    /**
     * Jalankan ML Kit OCR lalu parse baris nota jadi items. Setelah itu
     * klasifikasi otomatis (TASK 3): type (default expense, income bila ada
     * keyword), kategori & akun dicocokkan dengan nama yang muncul di teks.
     * Hasilnya ditulis ke [pendingReceipt] agar form New Transaction mengisinya.
     */
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
                val type = if (INCOME_KEYWORDS.any { raw.lowercase().contains(it) }) "income" else "expense"
                _uiState.value = _uiState.value.copy(
                    items = parsed.items,
                    merchant = parsed.merchant,
                    ocrText = raw,
                    type = type,
                    processing = false,
                )
                writePendingReceipt(raw, type)
            }.onFailure {
                _uiState.value = _uiState.value.copy(processing = false, error = it.toUserMessage())
            }
        }
    }

    /** Klasifikasi kategori/akun + simpan hasil OCR untuk form New Transaction. */
    private fun writePendingReceipt(raw: String, type: String) {
        val s = _uiState.value
        val lower = raw.lowercase()
        val category = s.categories.firstOrNull { lower.contains(it.name.lowercase()) }
        val account = s.accounts.firstOrNull { lower.contains(it.account_name.lowercase()) }
        pendingReceipt.value = PendingReceiptData(
            type = type,
            merchant = s.merchant,
            items = s.items.map { TransactionItemCreate(name = it.name, qty = it.qty, price = it.price) },
            suggestedCategoryId = category?.id,
            suggestedAccountId = account?.id,
        )
    }

    fun setError(message: String?) {
        _uiState.value = _uiState.value.copy(error = message)
    }

    companion object {
        val Factory = viewModelFactory {
            initializer {
                val app = this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY] as MyMoneyApp
                ReceiptViewModel(app.container.api, app.container.pendingReceipt)
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
