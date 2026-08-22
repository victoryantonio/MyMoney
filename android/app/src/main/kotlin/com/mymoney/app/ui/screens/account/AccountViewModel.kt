package com.mymoney.app.ui.screens.account

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.mymoney.app.data.model.AccountCreateRequest
import com.mymoney.app.data.model.AccountResponse
import com.mymoney.app.data.repository.AccountRepository
import dagger.hilt.android.lifecycle.HiltViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import javax.inject.Inject

data class AccountUiState(
    val isLoading: Boolean = false,
    val accounts: List<AccountResponse> = emptyList(),
    // When deactivating with balance — show bottom sheet to pick target account
    val deactivatingAccount: AccountResponse? = null,
    val error: String? = null,
    val message: String? = null,
)

@HiltViewModel
class AccountViewModel @Inject constructor(
    private val accountRepository: AccountRepository,
) : ViewModel() {

    private val _uiState = MutableStateFlow(AccountUiState(isLoading = true))
    val uiState: StateFlow<AccountUiState> = _uiState.asStateFlow()

    init { loadAccounts() }

    fun loadAccounts() {
        viewModelScope.launch {
            _uiState.value = AccountUiState(isLoading = true)
            try {
                _uiState.value = AccountUiState(accounts = accountRepository.list())
            } catch (e: Exception) {
                _uiState.value = AccountUiState(error = "Gagal memuat akun.")
            }
        }
    }

    fun createAccount(name: String, bankName: String?, initialBalance: Double) {
        viewModelScope.launch {
            try {
                accountRepository.create(AccountCreateRequest(name, bankName?.takeIf { it.isNotBlank() }, initialBalance))
                loadAccounts()
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(error = "Gagal membuat akun.")
            }
        }
    }

    /**
     * Per US-22: if account has remaining balance, show bottom sheet to pick target.
     * Backend validates and creates balancing transactions automatically.
     */
    fun requestDeactivate(account: AccountResponse) {
        if (account.currentBalance != 0.0) {
            _uiState.value = _uiState.value.copy(deactivatingAccount = account)
        } else {
            confirmDeactivate(account.id, null)
        }
    }

    fun confirmDeactivate(accountId: String, targetAccountId: String?) {
        viewModelScope.launch {
            _uiState.value = _uiState.value.copy(deactivatingAccount = null)
            try {
                accountRepository.deactivate(accountId, targetAccountId)
                loadAccounts()
                _uiState.value = _uiState.value.copy(message = "Akun dinonaktifkan.")
            } catch (e: Exception) {
                _uiState.value = _uiState.value.copy(error = e.message ?: "Gagal menonaktifkan akun.")
            }
        }
    }

    fun dismissDeactivate() {
        _uiState.value = _uiState.value.copy(deactivatingAccount = null)
    }

    fun clearMessages() {
        _uiState.value = _uiState.value.copy(error = null, message = null)
    }
}
