package com.mymoney.app.data.api

import com.mymoney.app.data.model.*
import retrofit2.http.*

// -------------------------------------------------------------------------
// Auth API
// -------------------------------------------------------------------------
interface AuthApi {
    @POST("api/v1/auth/register")
    suspend fun register(@Body body: RegisterRequest): UserResponse

    @POST("api/v1/auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @POST("api/v1/auth/refresh")
    suspend fun refresh(@Body body: RefreshTokenRequest): TokenResponse

    @GET("api/v1/auth/me")
    suspend fun me(): UserResponse
}

// -------------------------------------------------------------------------
// Transactions API
// -------------------------------------------------------------------------
interface TransactionsApi {
    @GET("api/v1/transactions")
    suspend fun list(
        @Query("cursor") cursor: String? = null,
        @Query("limit") limit: Int = 20,
        @Query("category_id") categoryId: String? = null,
        @Query("type") type: String? = null,
        @Query("date_from") dateFrom: String? = null,
        @Query("date_to") dateTo: String? = null,
    ): CursorPage<TransactionResponse>

    @POST("api/v1/transactions")
    suspend fun create(@Body body: TransactionCreateRequest): TransactionResponse

    @GET("api/v1/transactions/{id}")
    suspend fun get(@Path("id") id: String): TransactionResponse

    @PATCH("api/v1/transactions/{id}")
    suspend fun update(
        @Path("id") id: String,
        @Body body: TransactionUpdateRequest,
    ): TransactionResponse

    @DELETE("api/v1/transactions/{id}")
    suspend fun delete(@Path("id") id: String)
}

// -------------------------------------------------------------------------
// Accounts API
// -------------------------------------------------------------------------
interface AccountsApi {
    @GET("api/v1/accounts")
    suspend fun list(): List<AccountResponse>

    @POST("api/v1/accounts")
    suspend fun create(@Body body: AccountCreateRequest): AccountResponse

    @GET("api/v1/accounts/{id}")
    suspend fun get(@Path("id") id: String): AccountResponse

    @POST("api/v1/accounts/{id}/deactivate")
    suspend fun deactivate(
        @Path("id") id: String,
        @Body body: AccountDeactivateRequest,
    )
}

// -------------------------------------------------------------------------
// Categories API
// -------------------------------------------------------------------------
interface CategoriesApi {
    @GET("api/v1/categories")
    suspend fun list(): List<CategoryResponse>

    @POST("api/v1/categories")
    suspend fun create(@Body body: CategoryCreateRequest): CategoryResponse

    @DELETE("api/v1/categories/{id}")
    suspend fun delete(@Path("id") id: String)
}

// -------------------------------------------------------------------------
// Reports API
// -------------------------------------------------------------------------
interface ReportsApi {
    @GET("api/v1/reports/summary")
    suspend fun summary(
        @Query("date_from") dateFrom: String? = null,
        @Query("date_to") dateTo: String? = null,
    ): ReportSummary

    @GET("api/v1/reports/trend")
    suspend fun trend(
        @Query("date_from") dateFrom: String? = null,
        @Query("date_to") dateTo: String? = null,
    ): List<DailyTrend>
}

// -------------------------------------------------------------------------
// Receipts API
// -------------------------------------------------------------------------
interface ReceiptsApi {
    @Multipart
    @POST("api/v1/receipts/parse")
    suspend fun parseReceipt(
        @Part file: okhttp3.MultipartBody.Part
    ): ReceiptParseResponse
}
