package id.my.mymoney.data.model

import kotlinx.serialization.Serializable

// ── Transaction items ───────────────────────────────────────────────────────

@Serializable
data class TransactionItemCreate(
    val name: String,
    @Serializable(with = FlexibleStringSerializer::class) val qty: String,
    @Serializable(with = FlexibleStringSerializer::class) val price: String,
)

@Serializable
data class TransactionItemResponse(
    val id: String,
    val name: String,
    @Serializable(with = FlexibleStringSerializer::class) val qty: String,
    @Serializable(with = FlexibleStringSerializer::class) val price: String,
)

// ── Requests ────────────────────────────────────────────────────────────────

@Serializable
data class TransactionCreateRequest(
    val type: String, // "income" | "expense"
    @Serializable(with = FlexibleStringSerializer::class) val total_amount: String,
    val category_id: String,
    val account_id: String,
    val merchant: String? = null,
    val note: String? = null,
    val transaction_date: String, // ISO-8601 with offset
    val items: List<TransactionItemCreate> = emptyList(),
)

/** All fields optional — PATCH semantics. */
@Serializable
data class TransactionUpdateRequest(
    val type: String? = null,
    @Serializable(with = FlexibleStringSerializer::class) val total_amount: String? = null,
    val category_id: String? = null,
    val account_id: String? = null,
    val merchant: String? = null,
    val note: String? = null,
    val transaction_date: String? = null,
    val items: List<TransactionItemCreate>? = null,
)

// ── Responses ───────────────────────────────────────────────────────────────

@Serializable
data class TransactionResponse(
    val id: String,
    val type: String, // "income" | "expense"
    @Serializable(with = FlexibleStringSerializer::class) val total_amount: String,
    val category_id: String,
    val account_id: String,
    val merchant: String? = null,
    val source: String = "api",
    val note: String? = null,
    val confidence: String? = null,
    val receipt_image_url: String? = null,
    val transaction_date: String,
    val created_at: String,
    val updated_at: String,
    val items: List<TransactionItemResponse> = emptyList(),
) {
    val totalAmountDecimal: java.math.BigDecimal
        get() = runCatching { java.math.BigDecimal(total_amount) }.getOrDefault(java.math.BigDecimal.ZERO)

    val isExpense: Boolean get() = type == "expense"
}

@Serializable
data class TransactionListResponse(
    val items: List<TransactionResponse> = emptyList(),
    val next_cursor: String? = null,
    val total_count: Int = 0,
)
