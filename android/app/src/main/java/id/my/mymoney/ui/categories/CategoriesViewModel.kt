package id.my.mymoney.ui.categories

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import androidx.lifecycle.viewmodel.initializer
import androidx.lifecycle.viewmodel.viewModelFactory
import id.my.mymoney.MyMoneyApp
import id.my.mymoney.data.api.ApiService
import id.my.mymoney.data.model.CategoryCreateRequest
import id.my.mymoney.data.model.CategoryResponse
import id.my.mymoney.data.model.CategoryUpdateRequest
import id.my.mymoney.data.toUserMessage
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class CategoriesViewModel(private val api: ApiService) : ViewModel() {

    data class UiState(
        val categories: List<CategoryResponse> = emptyList(),
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
            runCatching { api.categories() }
                .onSuccess { _uiState.value = _uiState.value.copy(categories = it, loading = false) }
                .onFailure { _uiState.value = _uiState.value.copy(loading = false, error = it.toUserMessage()) }
        }
    }

    fun create(name: String, type: String, onDone: (Boolean, String?) -> Unit) {
        if (_uiState.value.busy) return
        _uiState.value = _uiState.value.copy(busy = true, error = null)
        viewModelScope.launch {
            val result = runCatching { api.createCategory(CategoryCreateRequest(name = name.trim(), type = type)) }
            _uiState.value = _uiState.value.copy(busy = false)
            result.onSuccess {
                load()
                onDone(true, null)
            }.onFailure { onDone(false, it.toUserMessage()) }
        }
    }

    fun update(cat: CategoryResponse, name: String, type: String, onDone: (Boolean, String?) -> Unit) {
        if (_uiState.value.busy) return
        _uiState.value = _uiState.value.copy(busy = true, error = null)
        viewModelScope.launch {
            val result = runCatching {
                api.updateCategory(cat.id, CategoryUpdateRequest(name = name.trim().ifBlank { null }, type = type))
            }
            _uiState.value = _uiState.value.copy(busy = false)
            result.onSuccess {
                load()
                onDone(true, null)
            }.onFailure { onDone(false, it.toUserMessage()) }
        }
    }

    fun delete(cat: CategoryResponse, onDone: (Boolean, String?) -> Unit) {
        if (_uiState.value.busy) return
        _uiState.value = _uiState.value.copy(busy = true, error = null)
        viewModelScope.launch {
            val result = runCatching { api.deleteCategory(cat.id) }
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
                CategoriesViewModel(app.container.api)
            }
        }
    }
}
