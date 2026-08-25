package id.my.mymoney.ui.accounts

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import id.my.mymoney.MyMoneyApp
import id.my.mymoney.data.api.ApiService
import id.my.mymoney.data.model.AccountDeactivateRequest
import id.my.mymoney.data.model.AccountResponse
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.data.toUserMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Account detail (TASK 4.1): loads the account + its transaction history
 * (filtered by account_id) and exposes deactivation (ARCHITECTURE.md §4.4).
 */
class AccountDetailViewModel(private val api: ApiService) : ViewModel() {

    data class UiState(
        val account: AccountResponse? = null,
        val transactions: List<TransactionResponse> = emptyList(),
        val activeAccounts: List<AccountResponse> = emptyList(),
        val loading: Boolean = true,
        val error: String? = null,
        val busy: Boolean = false,
    )

    private val _uiState = MutableStateFlow(UiState())
    val uiState: StateFlow<UiState> = _uiState.asStateFlow()

    fun load(accountId: String) {
        _uiState.value = _uiState.value.copy(loading = true, error = null)
        viewModelScope.launch {
            val result = runCatching {
                val acc = api.account(accountId)
                val txs = api.transactions(accountId = accountId)
                // Active accounts for the transfer dropdown (excludes self in UI).
                // 4.4: urut alfabetis konsisten dengan dropdown akun lain.
                val active = api.accounts(includeInactive = false)
                    .sortedBy { it.account_name.lowercase() }
                Triple(acc, txs.items, active)
            }
            result.onSuccess { (acc, txs, active) ->
                _uiState.value = _uiState.value.copy(
                    account = acc,
                    transactions = txs,
                    activeAccounts = active,
                    loading = false,
                )
            }.onFailure {
                _uiState.value = _uiState.value.copy(loading = false, error = it.toUserMessage())
            }
        }
    }

    fun refresh(accountId: String) = load(accountId)

    fun update(
        acc: AccountResponse,
        name: String,
        bank: String?,
        onDone: (Boolean, String?) -> Unit,
    ) {
        if (_uiState.value.busy) return
        _uiState.value = _uiState.value.copy(busy = true, error = null)
        viewModelScope.launch {
            val result = runCatching {
                api.updateAccount(
                    acc.id,
                    id.my.mymoney.data.model.AccountUpdateRequest(
                        account_name = name.trim().ifBlank { null },
                        bank_name = bank?.takeIf { it.isNotBlank() },
                    )
                )
            }
            _uiState.value = _uiState.value.copy(busy = false)
            result.onSuccess {
                load(acc.id)
                onDone(true, null)
            }.onFailure { onDone(false, it.toUserMessage()) }
        }
    }

    /** Deactivate. `targetId` required by backend when balance != 0 (transfer). */
    fun deactivate(
        acc: AccountResponse,
        targetId: String?,
        onDone: (Boolean, String?) -> Unit,
    ) {
        if (_uiState.value.busy) return
        _uiState.value = _uiState.value.copy(busy = true, error = null)
        viewModelScope.launch {
            val result = runCatching {
                api.deactivateAccount(acc.id, AccountDeactivateRequest(target_account_id = targetId))
            }
            _uiState.value = _uiState.value.copy(busy = false)
            result.onSuccess {
                load(acc.id)
                onDone(true, null)
            }.onFailure { onDone(false, it.toUserMessage()) }
        }
    }

    companion object {
        val Factory = viewModelFactory {
            initializer {
                val app = this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY] as MyMoneyApp
                AccountDetailViewModel(app.container.api)
            }
        }
    }
}
