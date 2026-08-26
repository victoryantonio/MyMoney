package id.my.mymoney

import id.my.mymoney.data.api.ApiService
import id.my.mymoney.data.model.AccountCreateRequest
import id.my.mymoney.data.model.AccountDeactivateRequest
import id.my.mymoney.data.model.AccountResponse
import id.my.mymoney.data.model.AccountUpdateRequest
import id.my.mymoney.data.model.CategoryCreateRequest
import id.my.mymoney.data.model.CategoryResponse
import id.my.mymoney.data.model.CategoryUpdateRequest
import id.my.mymoney.data.model.ForgotPasswordRequest
import id.my.mymoney.data.model.GenericMessageResponse
import id.my.mymoney.data.model.LoginRequest
import id.my.mymoney.data.model.RefreshRequest
import id.my.mymoney.data.model.RefreshResponse
import id.my.mymoney.data.model.RegisterRequest
import id.my.mymoney.data.model.ReportSummaryResponse
import id.my.mymoney.data.model.ReportTrendResponse
import id.my.mymoney.data.model.ResetPasswordRequest
import id.my.mymoney.data.model.TokenResponse
import id.my.mymoney.data.model.TransactionCreateRequest
import id.my.mymoney.data.model.TransactionListResponse
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.data.model.TransactionUpdateRequest
import id.my.mymoney.data.model.UserResponse
import retrofit2.Response
import java.io.IOException

/**
 * In-memory fake of the Retrofit [ApiService] for unit tests.
 * Each endpoint can be made to fail to exercise error paths.
 */
class FakeApiService : ApiService {

    // Auth
    var loginShouldFail: Boolean = false
    var registerShouldFail: Boolean = false
    var meShouldFail: Boolean = false
    var meFailuresRemaining: Int = 0
    var refreshShouldFail: Boolean = false
    var meUser: UserResponse = UserResponse(
        id = "user-1",
        email = "a@b.com",
        display_name = "Alice",
        timezone = "Asia/Jakarta",
        is_active = true,
    )
    var refreshCalls: Int = 0

    // Transactions
    var txShouldFail: Boolean = false
    var txPage: (String?) -> TransactionListResponse = { TransactionListResponse(emptyList(), null, 0) }
    val created: MutableList<TransactionCreateRequest> = mutableListOf()
    val updated: MutableList<Pair<String, TransactionUpdateRequest>> = mutableListOf()
    val deleted: MutableList<String> = mutableListOf()

    // Categories / accounts
    var categoriesList: List<CategoryResponse> = emptyList()
    var accountsList: List<AccountResponse> = emptyList()

    // Reports
    var reportShouldFail: Boolean = false
    var report: ReportSummaryResponse = ReportSummaryResponse(
        start_date = "2026-08-01T00:00:00+07:00",
        end_date = "2026-09-01T00:00:00+07:00",
        total_income = "1000000.00",
        total_expense = "400000.00",
        net = "600000.00",
        categories = emptyList(),
    )
    var reportPeriods: MutableList<String?> = mutableListOf()

    // ── Auth ────────────────────────────────────────────────────────────
    override suspend fun register(body: RegisterRequest): UserResponse {
        if (registerShouldFail) throw IOException("network")
        return meUser.copy(email = body.email, display_name = body.display_name)
    }

    override suspend fun login(body: LoginRequest): TokenResponse {
        if (loginShouldFail) throw IOException("network")
        return TokenResponse(access_token = "access-1", refresh_token = "refresh-1")
    }

    override suspend fun refresh(body: RefreshRequest): RefreshResponse {
        refreshCalls++
        if (refreshShouldFail) throw IOException("refresh failed")
        return RefreshResponse(access_token = "access-2")
    }

    override suspend fun me(): UserResponse {
        if (meShouldFail || meFailuresRemaining > 0) {
            if (meFailuresRemaining > 0) meFailuresRemaining--
            throw IOException("unauthorized")
        }
        return meUser
    }

    // ── Transactions ────────────────────────────────────────────────────
    override suspend fun transactions(
        cursor: String?,
        type: String?,
        categoryId: String?,
        accountId: String?,
    ): TransactionListResponse {
        if (txShouldFail) throw IOException("network")
        return txPage(cursor)
    }

    override suspend fun createTransaction(body: TransactionCreateRequest): TransactionResponse {
        if (txShouldFail) throw IOException("network")
        created += body
        return sampleTransaction()
    }

    override suspend fun transaction(id: String): TransactionResponse {
        if (txShouldFail) throw IOException("network")
        return sampleTransaction(id = id)
    }

    override suspend fun updateTransaction(id: String, body: TransactionUpdateRequest): TransactionResponse {
        if (txShouldFail) throw IOException("network")
        updated += id to body
        return sampleTransaction(id = id)
    }

    override suspend fun deleteTransaction(id: String): Response<Unit> {
        if (txShouldFail) throw IOException("network")
        deleted += id
        return Response.success(Unit)
    }

    private fun sampleTransaction(id: String = "tx-1"): TransactionResponse = TransactionResponse(
        id = id,
        type = "expense",
        total_amount = "25000.00",
        category_id = "cat-1",
        account_id = "acc-1",
        merchant = "Kopi",
        source = "api",
        transaction_date = "2026-08-25T10:00:00+07:00",
        created_at = "2026-08-25T10:00:00+07:00",
        updated_at = "2026-08-25T10:00:00+07:00",
        items = emptyList(),
    )

    // ── Categories ──────────────────────────────────────────────────────
    override suspend fun categories(): List<CategoryResponse> = categoriesList

    override suspend fun createCategory(body: CategoryCreateRequest): CategoryResponse {
        if (txShouldFail) throw IOException("network")
        return CategoryResponse(id = "cat-new", name = body.name, type = body.type)
    }

    override suspend fun updateCategory(id: String, body: CategoryUpdateRequest): CategoryResponse {
        if (txShouldFail) throw IOException("network")
        return CategoryResponse(id = id, name = body.name ?: "x", type = body.type ?: "expense")
    }

    override suspend fun deleteCategory(id: String): Response<Unit> {
        if (txShouldFail) throw IOException("network")
        return Response.success(Unit)
    }

    // ── Accounts ────────────────────────────────────────────────────────
    var accountShouldFail: Boolean = false
    var deactivateCalls: MutableList<Pair<String, AccountDeactivateRequest>> = mutableListOf()
    var forgotCalls: MutableList<String> = mutableListOf()
    var resetCalls: Int = 0

    override suspend fun accounts(includeInactive: Boolean): List<AccountResponse> = accountsList

    override suspend fun createAccount(body: AccountCreateRequest): AccountResponse {
        if (txShouldFail) throw IOException("network")
        return AccountResponse(
            id = "acc-new",
            account_name = body.account_name,
            bank_name = body.bank_name,
            initial_balance = body.initial_balance,
            current_balance = body.initial_balance,
            created_at = "2026-08-25T10:00:00+07:00",
        )
    }

    override suspend fun account(id: String): AccountResponse {
        if (accountShouldFail) throw IOException("network")
        return accountsList.firstOrNull { it.id == id }
            ?: AccountResponse(
                id = id,
                account_name = "Kas",
                bank_name = null,
                initial_balance = "0",
                current_balance = "0",
                created_at = "2026-08-25T10:00:00+07:00",
            )
    }

    override suspend fun updateAccount(id: String, body: AccountUpdateRequest): AccountResponse {
        if (txShouldFail) throw IOException("network")
        return AccountResponse(
            id = id,
            account_name = body.account_name ?: "x",
            bank_name = body.bank_name,
            initial_balance = "0",
            current_balance = "0",
            created_at = "2026-08-25T10:00:00+07:00",
        )
    }

    override suspend fun deactivateAccount(id: String, body: AccountDeactivateRequest): AccountResponse {
        if (txShouldFail) throw IOException("network")
        deactivateCalls += id to body
        return AccountResponse(
            id = id,
            account_name = "Kas",
            bank_name = null,
            initial_balance = "0",
            current_balance = "0",
            created_at = "2026-08-25T10:00:00+07:00",
            is_active = false,
        )
    }

    // ── Auth: forgot / reset password ──────────────────────────────────
    override suspend fun forgotPassword(body: ForgotPasswordRequest): GenericMessageResponse {
        forgotCalls += body.email
        return GenericMessageResponse("If that email is registered, we've sent a password reset link to it.")
    }

    override suspend fun resetPassword(body: ResetPasswordRequest): GenericMessageResponse {
        resetCalls++
        return GenericMessageResponse("Password has been reset. You can now log in.")
    }

    // ── Reports ─────────────────────────────────────────────────────────
    override suspend fun reportSummary(period: String?, start: String?, end: String?): ReportSummaryResponse {
        reportPeriods += period
        if (reportShouldFail) throw IOException("network")
        return report
    }

    var reportTrendShouldFail: Boolean = false
    var reportTrendResponse: ReportTrendResponse = ReportTrendResponse(
        start_date = "2026-08-01T00:00:00+07:00",
        end_date = "2026-08-31T00:00:00+07:00",
        points = emptyList(),
    )
    val trendPeriods: MutableList<String?> = mutableListOf()

    override suspend fun reportTrend(period: String?, start: String?, end: String?): ReportTrendResponse {
        trendPeriods += period
        if (reportTrendShouldFail) throw IOException("network")
        return reportTrendResponse
    }
}
