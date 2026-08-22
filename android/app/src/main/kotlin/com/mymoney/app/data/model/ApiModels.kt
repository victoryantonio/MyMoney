package com.mymoney.app.data.model

import kotlinx.serialization.SerialName
import kotlinx.serialization.Serializable

// -------------------------------------------------------------------------
// DTOs — mirrors backend Pydantic schemas exactly
// -------------------------------------------------------------------------

@Serializable
data class TokenResponse(
    @SerialName("access_token") val accessToken: String,
    @SerialName("refresh_token") val refreshToken: String,
    @SerialName("token_type") val tokenType: String = "bearer",
)

@Serializable
data class UserResponse(
    val id: String,
    val email: String,
    @SerialName("display_name") val displayName: String,
    @SerialName("is_active") val isActive: Boolean,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class LoginRequest(
    val email: String,
    val password: String,
)

@Serializable
data class RegisterRequest(
    val email: String,
    val password: String,
    @SerialName("display_name") val displayName: String,
)

@Serializable
data class RefreshTokenRequest(
    @SerialName("refresh_token") val refreshToken: String,
)

// -------------------------------------------------------------------------
// Category
// -------------------------------------------------------------------------
@Serializable
data class CategoryResponse(
    val id: String,
    val name: String,
    val type: String,       // "income" | "expense"
    @SerialName("is_default") val isDefault: Boolean,
    @SerialName("user_id") val userId: String?,
)

@Serializable
data class CategoryCreateRequest(
    val name: String,
    val type: String,
)

// -------------------------------------------------------------------------
// Account
// -------------------------------------------------------------------------
@Serializable
data class AccountResponse(
    val id: String,
    @SerialName("account_name") val accountName: String,
    @SerialName("bank_name") val bankName: String?,
    @SerialName("initial_balance") val initialBalance: Double,
    @SerialName("current_balance") val currentBalance: Double,
    @SerialName("is_active") val isActive: Boolean,
    @SerialName("created_at") val createdAt: String,
)

@Serializable
data class AccountCreateRequest(
    @SerialName("account_name") val accountName: String,
    @SerialName("bank_name") val bankName: String? = null,
    @SerialName("initial_balance") val initialBalance: Double = 0.0,
)

@Serializable
data class AccountDeactivateRequest(
    @SerialName("target_account_id") val targetAccountId: String? = null,
)

// -------------------------------------------------------------------------
// Transaction
// -------------------------------------------------------------------------
@Serializable
data class TransactionItemResponse(
    val id: String,
    val name: String,
    val qty: Double,
    val price: Double,
)

@Serializable
data class TransactionItemRequest(
    val name: String,
    val qty: Double,
    val price: Double,
)

@Serializable
data class TransactionResponse(
    val id: String,
    val type: String,           // "income" | "expense"
    @SerialName("total_amount") val totalAmount: Double,
    @SerialName("category_id") val categoryId: String,
    val category: CategoryResponse,
    @SerialName("account_id") val accountId: String,
    val merchant: String?,
    val source: String,
    val note: String?,
    val confidence: String?,
    @SerialName("receipt_image_url") val receiptImageUrl: String?,
    @SerialName("transaction_date") val transactionDate: String,
    @SerialName("created_at") val createdAt: String,
    @SerialName("updated_at") val updatedAt: String,
    val items: List<TransactionItemResponse>,
)

@Serializable
data class TransactionCreateRequest(
    val type: String,
    @SerialName("total_amount") val totalAmount: Double,
    @SerialName("category_id") val categoryId: String,
    @SerialName("account_id") val accountId: String,
    val merchant: String? = null,
    val note: String? = null,
    @SerialName("transaction_date") val transactionDate: String,
    val items: List<TransactionItemRequest> = emptyList(),
)

@Serializable
data class TransactionUpdateRequest(
    val type: String? = null,
    @SerialName("total_amount") val totalAmount: Double? = null,
    @SerialName("category_id") val categoryId: String? = null,
    @SerialName("account_id") val accountId: String? = null,
    val merchant: String? = null,
    val note: String? = null,
    @SerialName("transaction_date") val transactionDate: String? = null,
    val items: List<TransactionItemRequest>? = null,
)

// -------------------------------------------------------------------------
// Pagination
// -------------------------------------------------------------------------
@Serializable
data class CursorPage<T>(
    val data: List<T>,
    @SerialName("next_cursor") val nextCursor: String?,
    @SerialName("has_more") val hasMore: Boolean,
)

// -------------------------------------------------------------------------
// Report
// -------------------------------------------------------------------------
@Serializable
data class CategoryTotal(
    val category: String,
    val total: Double,
)

@Serializable
data class ReportSummary(
    val period: Map<String, String>,
    @SerialName("total_income") val totalIncome: Double,
    @SerialName("total_expense") val totalExpense: Double,
    val balance: Double,
    @SerialName("income_by_category") val incomeByCategory: List<CategoryTotal>,
    @SerialName("expense_by_category") val expenseByCategory: List<CategoryTotal>,
)

@Serializable
data class DailyTrend(
    val date: String,
    val income: Double,
    val expense: Double,
)

// -------------------------------------------------------------------------
// Receipts
// -------------------------------------------------------------------------
@Serializable
data class ReceiptParsedData(
    val merchant: String?,
    val date: String?,
    val total: Double,
    val items: List<TransactionItemRequest>,
    val confidence: String,
)

@Serializable
data class ReceiptParseResponse(
    val parsed: ReceiptParsedData,
    @SerialName("receipt_image_path") val receiptImagePath: String,
    @SerialName("review_required") val reviewRequired: Boolean,
)
