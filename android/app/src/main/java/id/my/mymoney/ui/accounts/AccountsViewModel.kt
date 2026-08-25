package id.my.mymoney.ui.accounts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import id.my.mymoney.MyMoneyApp
import id.my.mymoney.data.api.ApiService
import id.my.mymoney.data.model.AccountCreateRequest
import id.my.mymoney.data.model.AccountDeactivateRequest
import id.my.mymoney.data.model.AccountResponse
import id.my.mymoney.data.model.AccountUpdateRequest
import id.my.mymoney.data.toUserMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.math.BigDecimal

class AccountsViewModel(private val api: ApiService) : ViewModel() {

    data class UiState(
        val accounts: List<AccountResponse> = emptyList(),
        val loading: Boolean = true,
        val error: String? = null,
        val busy: Boolean = false,
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    init {
        load()
    }

    fun load() {
        _uiState.value = _uiState.value.copy(loading = true, error = null)
        viewModelScope.launch {
            runCatching { api.accounts() }
                .onSuccess { _uiState.value = _uiState.value.copy(accounts = it, loading = false) }
                .onFailure { _uiState.value = _uiState.value.copy(loading = false, error = it.toUserMessage()) }
        }
    }

    fun create(name: String, bank: String?, initialBalance: BigDecimal, onDone: (Boolean, String?) -> Unit) {
        if (_uiState.value.busy) return
        _uiState.value = _uiState.value.copy(busy = true, error = null)
        viewModelScope.launch {
            val result = runCatching {
                api.createAccount(
                    AccountCreateRequest(
                        account_name = name.trim(),
                        bank_name = bank?.takeIf { it.isNotBlank() },
                        initial_balance = initialBalance.toPlainString(),
                    )
                )
            }
            _uiState.value = _uiState.value.copy(busy = false)
            result.onSuccess {
                load()
                onDone(true, null)
            }.onFailure { onDone(false, it.toUserMessage()) }
        }
    }

    fun update(acc: AccountResponse, name: String, bank: String?, onDone: (Boolean, String?) -> Unit) {
        if (_uiState.value.busy) return
        _uiState.value = _uiState.value.copy(busy = true, error = null)
        viewModelScope.launch {
            val result = runCatching {
                api.updateAccount(
                    acc.id,
                    AccountUpdateRequest(
                        account_name = name.trim().ifBlank { null },
                        bank_name = bank?.takeIf { it.isNotBlank() },
                    )
                )
            }
            _uiState.value = _uiState.value.copy(busy = false)
            result.onSuccess {
                load()
                onDone(true, null)
            }.onFailure { onDone(false, it.toUserMessage()) }
        }
    }

    /**
     * Deactivate an account (ARCHITECTURE.md §4.4). Accounts are never deleted.
     * `targetAccountId` is required when the account still has a balance — the
     * leftover funds are transferred there via balancing transactions.
     */
    fun deactivate(acc: AccountResponse, targetAccountId: String?, onDone: (Boolean, String?) -> Unit) {
        if (_uiState.value.busy) return
        _uiState.value = _uiState.value.copy(busy = true, error = null)
        viewModelScope.launch {
            val result = runCatching {
                api.deactivateAccount(
                    acc.id,
                    AccountDeactivateRequest(target_account_id = targetAccountId),
                )
            }
            _uiState.value = _uiState.value.copy(busy = false)
            result.onSuccess {
                load()
                onDone(true, null)
            }.onFailure { onDone(false, it.toUserMessage()) }
        }
    }

    companion object {
        val Factory = viewModelFactory {
            initializer {
                val app = this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY] as MyMoneyApp
                AccountsViewModel(app.container.api)
            }
        }
    }
}
