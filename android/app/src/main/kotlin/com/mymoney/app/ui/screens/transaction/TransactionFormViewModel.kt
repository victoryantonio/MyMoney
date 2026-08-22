package com.mymoney.app.ui.screens.transaction

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mymoney.app.data.model.*
import com.mymoney.app.data.repository.AccountRepository
import com.mymoney.app.data.repository.CategoryRepository
import com.mymoney.app.data.repository.TransactionRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.time.LocalDateTime
import java.time.format.DateTimeFormatter
import javax.inject.Inject
import com.mymoney.app.data.api.ReceiptsApi
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody
import android.content.Context
import android.net.Uri

data class TransactionFormState(
    val isLoading: Boolean = false,
    val categories: List<CategoryResponse> = emptyList(),
    val accounts: List<AccountResponse> = emptyList(),
    val isSaved: Boolean = false,
    val error: String? = null,
    val isScanning: Boolean = false,
    val parsedReceipt: ReceiptParseResponse? = null,
)

@HiltViewModel
class TransactionFormViewModel @Inject constructor(
    private val transactionRepository: TransactionRepository,
    private val categoryRepository: CategoryRepository,
    private val accountRepository: AccountRepository,
    private val receiptsApi: ReceiptsApi,
) : ViewModel() {

    private val _state = MutableStateFlow(TransactionFormState(isLoading = true))
    val state: StateFlow<TransactionFormState> = _state.asStateFlow()

    init {
        loadOptions()
    }

    private fun loadOptions() {
        viewModelScope.launch {
            try {
                val categories = categoryRepository.list()
                val accounts = accountRepository.list().filter { it.isActive }
                _state.value = TransactionFormState(categories = categories, accounts = accounts)
            } catch (e: Exception) {
                _state.value = TransactionFormState(error = "Gagal memuat data formulir.")
            }
        }
    }

    fun saveTransaction(
        type: String,
        amount: Double,
        categoryId: String,
        accountId: String,
        merchant: String?,
        note: String?,
        dateTime: String,
        items: List<TransactionItemRequest> = emptyList(),
    ) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isLoading = true)
            try {
                transactionRepository.create(
                    TransactionCreateRequest(
                        type = type,
                        totalAmount = amount,
                        categoryId = categoryId,
                        accountId = accountId,
                        merchant = merchant?.takeIf { it.isNotBlank() },
                        note = note?.takeIf { it.isNotBlank() },
                        transactionDate = dateTime,
                        items = items,
                    )
                )
                _state.value = _state.value.copy(isLoading = false, isSaved = true)
            } catch (e: Exception) {
                _state.value = _state.value.copy(isLoading = false, error = "Gagal menyimpan transaksi.")
            }
        }
    }

    fun clearError() { _state.value = _state.value.copy(error = null) }
    fun clearParsedReceipt() { _state.value = _state.value.copy(parsedReceipt = null) }

    fun scanReceipt(uri: Uri, context: Context) {
        viewModelScope.launch {
            _state.value = _state.value.copy(isScanning = true, error = null)
            try {
                val bytes = context.contentResolver.openInputStream(uri)?.use { it.readBytes() }
                    ?: throw Exception("Gagal membaca foto nota")
                
                val requestBody = bytes.toRequestBody("image/*".toMediaTypeOrNull())
                val part = MultipartBody.Part.createFormData("file", "receipt.jpg", requestBody)
                
                val response = receiptsApi.parseReceipt(part)
                _state.value = _state.value.copy(isScanning = false, parsedReceipt = response)
            } catch (e: Exception) {
                _state.value = _state.value.copy(isScanning = false, error = "Gagal memproses nota: ${e.message}")
            }
        }
    }
}
