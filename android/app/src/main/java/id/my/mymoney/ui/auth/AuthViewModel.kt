package id.my.mymoney.ui.auth

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import id.my.mymoney.MyMoneyApp
import id.my.mymoney.data.AuthRepository
import id.my.mymoney.data.AuthState
import id.my.mymoney.data.toUserMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class AuthViewModel(private val repo: AuthRepository) : ViewModel() {

    val authState: StateFlow<AuthState> = repo.authState

    private val _error = MutableStateFlow<String?>(null)
    val error: StateFlow<String?> = _error.asStateFlow()

    private val _busy = MutableStateFlow(false)
    val busy: StateFlow<Boolean> = _busy.asStateFlow()

    init {
        viewModelScope.launch { repo.bootstrap() }
    }

    fun login(email: String, password: String, onSuccess: () -> Unit = {}) {
        if (_busy.value) return
        _error.value = null
        _busy.value = true
        viewModelScope.launch {
            repo.login(email, password)
                .onSuccess { onSuccess() }
                .onFailure { _error.value = it.toUserMessage() }
            _busy.value = false
        }
    }

    fun register(displayName: String, email: String, password: String, onSuccess: () -> Unit = {}) {
        if (_busy.value) return
        _error.value = null
        _busy.value = true
        viewModelScope.launch {
            repo.register(displayName, email, password)
                .onSuccess { onSuccess() }
                .onFailure { _error.value = it.toUserMessage() }
            _busy.value = false
        }
    }

    fun logout() {
        viewModelScope.launch { repo.logout() }
    }

    companion object {
        val Factory = viewModelFactory {
            initializer {
                val app = this[ViewModelProvider.AndroidViewModelFactory.APPLICATION_KEY] as MyMoneyApp
                AuthViewModel(app.container.authRepository)
            }
        }
    }
}
