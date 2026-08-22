package com.mymoney.app.data.repository

import com.mymoney.app.data.api.AuthApi
import com.mymoney.app.data.local.TokenStore
import com.mymoney.app.data.model.*
import javax.inject.Inject
import javax.inject.Singleton

/**
 * AuthRepository — handles login, register, logout, token state.
 * ViewModels call ONLY this, not the API directly (per CODING_RULES.md §3.2).
 */
@Singleton
class AuthRepository @Inject constructor(
    private val authApi: AuthApi,
    private val tokenStore: TokenStore,
) {
    val accessToken = tokenStore.accessToken

    suspend fun login(email: String, password: String): UserResponse {
        val tokens = authApi.login(LoginRequest(email, password))
        tokenStore.saveTokens(tokens.accessToken, tokens.refreshToken)
        return authApi.me()
    }

    suspend fun register(email: String, password: String, displayName: String): UserResponse {
        authApi.register(RegisterRequest(email, password, displayName))
        val tokens = authApi.login(LoginRequest(email, password))
        tokenStore.saveTokens(tokens.accessToken, tokens.refreshToken)
        return authApi.me()
    }

    suspend fun getMe(): UserResponse = authApi.me()

    suspend fun logout() = tokenStore.clearTokens()
}

// -------------------------------------------------------------------------
// TransactionRepository
// -------------------------------------------------------------------------
@Singleton
class TransactionRepository @Inject constructor(
    private val api: com.mymoney.app.data.api.TransactionsApi,
) {
    suspend fun list(
        cursor: String? = null,
        limit: Int = 20,
        categoryId: String? = null,
        type: String? = null,
        dateFrom: String? = null,
        dateTo: String? = null,
    ): CursorPage<TransactionResponse> = api.list(cursor, limit, categoryId, type, dateFrom, dateTo)

    suspend fun create(request: TransactionCreateRequest): TransactionResponse = api.create(request)

    suspend fun get(id: String): TransactionResponse = api.get(id)

    suspend fun update(id: String, request: TransactionUpdateRequest): TransactionResponse =
        api.update(id, request)

    suspend fun delete(id: String) = api.delete(id)
}

// -------------------------------------------------------------------------
// AccountRepository
// -------------------------------------------------------------------------
@Singleton
class AccountRepository @Inject constructor(
    private val api: com.mymoney.app.data.api.AccountsApi,
) {
    suspend fun list(): List<AccountResponse> = api.list()

    suspend fun create(request: AccountCreateRequest): AccountResponse = api.create(request)

    suspend fun get(id: String): AccountResponse = api.get(id)

    suspend fun deactivate(id: String, targetAccountId: String? = null) =
        api.deactivate(id, AccountDeactivateRequest(targetAccountId))
}

// -------------------------------------------------------------------------
// CategoryRepository
// -------------------------------------------------------------------------
@Singleton
class CategoryRepository @Inject constructor(
    private val api: com.mymoney.app.data.api.CategoriesApi,
) {
    suspend fun list(): List<CategoryResponse> = api.list()

    suspend fun create(name: String, type: String): CategoryResponse =
        api.create(CategoryCreateRequest(name, type))

    suspend fun delete(id: String) = api.delete(id)
}

// -------------------------------------------------------------------------
// ReportRepository
// -------------------------------------------------------------------------
@Singleton
class ReportRepository @Inject constructor(
    private val api: com.mymoney.app.data.api.ReportsApi,
) {
    suspend fun summary(dateFrom: String? = null, dateTo: String? = null): ReportSummary =
        api.summary(dateFrom, dateTo)

    suspend fun trend(dateFrom: String? = null, dateTo: String? = null): List<DailyTrend> =
        api.trend(dateFrom, dateTo)
}
