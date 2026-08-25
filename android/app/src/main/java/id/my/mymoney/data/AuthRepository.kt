package id.my.mymoney.data

import id.my.mymoney.data.api.ApiService
import id.my.mymoney.data.model.LoginRequest
import id.my.mymoney.data.model.RefreshRequest
import id.my.mymoney.data.model.RegisterRequest
import id.my.mymoney.data.model.UserResponse
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.first

sealed interface AuthState {
    data object Unknown : AuthState
    data object Loading : AuthState
    data object Unauthenticated : AuthState
    data class Authenticated(val user: UserResponse) : AuthState
}

/**
 * Central auth repository: login / register / refresh / logout / bootstrap.
 * Updates [AuthStateHolder] so OkHttp interceptors always see fresh tokens.
 */
class AuthRepository(
    private val api: ApiService,
    private val tokenStore: TokenStore,
    private val state: AuthStateHolder,
) {
    private val _authState = MutableStateFlow<AuthState>(AuthState.Unknown)
    val authState: StateFlow<AuthState> = _authState.asStateFlow()

    /**
     * Called once at app start: restore tokens from DataStore and validate
     * against GET /api/auth/me (silent refresh if the access token expired).
     */
    suspend fun bootstrap() {
        val (access, refresh) = tokenStore.load()
        if (access == null) {
            _authState.value = AuthState.Unauthenticated
            return
        }
        _authState.value = AuthState.Loading
        state.update(access, refresh)
        try {
            val user = api.me()
            _authState.value = AuthState.Authenticated(user)
        } catch (e: Exception) {
            // Access token expired — try silent refresh, otherwise logout.
            val refreshed = refreshAccessToken()
            if (refreshed) {
                try {
                    val user = api.me()
                    _authState.value = AuthState.Authenticated(user)
                } catch (e2: Exception) {
                    logout()
                }
            } else {
                logout()
            }
        }
    }

    suspend fun login(email: String, password: String): Result<UserResponse> {
        _authState.value = AuthState.Loading
        return runCatching {
            val tokens = api.login(LoginRequest(email = email.trim(), password = password))
            state.update(tokens.access_token, tokens.refresh_token)
            tokenStore.save(tokens.access_token, tokens.refresh_token)
            val user = api.me()
            _authState.value = AuthState.Authenticated(user)
            user
        }.onFailure { _authState.value = AuthState.Unauthenticated }
    }

    suspend fun register(displayName: String, email: String, password: String): Result<UserResponse> {
        _authState.value = AuthState.Loading
        return runCatching {
            val user = api.register(
                RegisterRequest(email = email.trim(), password = password, display_name = displayName.trim())
            )
            // Auto-login after successful registration.
            val tokens = api.login(LoginRequest(email = email.trim(), password = password))
            state.update(tokens.access_token, tokens.refresh_token)
            tokenStore.save(tokens.access_token, tokens.refresh_token)
            _authState.value = AuthState.Authenticated(user)
            user
        }.onFailure { _authState.value = AuthState.Unauthenticated }
    }

    /** Tries to exchange the refresh token for a new access token. Returns success. */
    suspend fun refreshAccessToken(): Boolean {
        val refresh = state.refreshToken ?: return false
        return runCatching {
            val res = api.refresh(RefreshRequest(refresh_token = refresh))
            state.update(res.access_token, refresh)
            tokenStore.save(res.access_token, refresh)
            true
        }.getOrDefault(false)
    }

    suspend fun logout() {
        state.clear()
        tokenStore.clear()
        _authState.value = AuthState.Unauthenticated
    }

    suspend fun currentUser(): UserResponse? {
        val s = _authState.value
        return (s as? AuthState.Authenticated)?.user
    }
}
