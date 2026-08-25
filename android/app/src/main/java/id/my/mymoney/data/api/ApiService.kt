package id.my.mymoney.data.api

import id.my.mymoney.data.model.AccountCreateRequest
import id.my.mymoney.data.model.AccountResponse
import id.my.mymoney.data.model.AccountUpdateRequest
import id.my.mymoney.data.model.CategoryCreateRequest
import id.my.mymoney.data.model.CategoryResponse
import id.my.mymoney.data.model.CategoryUpdateRequest
import id.my.mymoney.data.model.LoginRequest
import id.my.mymoney.data.model.RefreshRequest
import id.my.mymoney.data.model.RefreshResponse
import id.my.mymoney.data.model.RegisterRequest
import id.my.mymoney.data.model.ReportSummaryResponse
import id.my.mymoney.data.model.TokenResponse
import id.my.mymoney.data.model.TransactionCreateRequest
import id.my.mymoney.data.model.TransactionListResponse
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.data.model.TransactionUpdateRequest
import id.my.mymoney.data.model.UserResponse
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.POST
import retrofit2.http.PUT
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit interface mirroring the FastAPI backend exactly:
 * auth, transactions, accounts, categories, reports/summary.
 */
interface ApiService {

    // ── Auth ────────────────────────────────────────────────────────────
    @POST("api/auth/register")
    suspend fun register(@Body body: RegisterRequest): UserResponse

    @POST("api/auth/login")
    suspend fun login(@Body body: LoginRequest): TokenResponse

    @POST("api/auth/refresh")
    suspend fun refresh(@Body body: RefreshRequest): RefreshResponse

    @GET("api/auth/me")
    suspend fun me(): UserResponse

    // ── Transactions (keyset pagination via cursor) ─────────────────────
    @GET("api/transactions")
    suspend fun transactions(
        @Query("cursor") cursor: String? = null,
        @Query("type") type: String? = null,
        @Query("category_id") categoryId: String? = null,
        @Query("account_id") accountId: String? = null,
    ): TransactionListResponse

    @POST("api/transactions")
    suspend fun createTransaction(@Body body: TransactionCreateRequest): TransactionResponse

    @GET("api/transactions/{id}")
    suspend fun transaction(@Path("id") id: String): TransactionResponse

    @PUT("api/transactions/{id}")
    suspend fun updateTransaction(@Path("id") id: String, @Body body: TransactionUpdateRequest): TransactionResponse

    @DELETE("api/transactions/{id}")
    suspend fun deleteTransaction(@Path("id") id: String): Response<Unit>

    // ── Categories ──────────────────────────────────────────────────────
    @GET("api/categories")
    suspend fun categories(): List<CategoryResponse>

    @POST("api/categories")
    suspend fun createCategory(@Body body: CategoryCreateRequest): CategoryResponse

    @PUT("api/categories/{id}")
    suspend fun updateCategory(@Path("id") id: String, @Body body: CategoryUpdateRequest): CategoryResponse

    @DELETE("api/categories/{id}")
    suspend fun deleteCategory(@Path("id") id: String): Response<Unit>

    // ── Accounts ────────────────────────────────────────────────────────
    @GET("api/accounts")
    suspend fun accounts(): List<AccountResponse>

    @POST("api/accounts")
    suspend fun createAccount(@Body body: AccountCreateRequest): AccountResponse

    @PUT("api/accounts/{id}")
    suspend fun updateAccount(@Path("id") id: String, @Body body: AccountUpdateRequest): AccountResponse

    @DELETE("api/accounts/{id}")
    suspend fun deleteAccount(@Path("id") id: String): Response<Unit>

    // ── Reports ─────────────────────────────────────────────────────────
    @GET("api/reports/summary")
    suspend fun reportSummary(
        @Query("period") period: String? = null,
        @Query("start") start: String? = null,
        @Query("end") end: String? = null,
    ): ReportSummaryResponse
}
