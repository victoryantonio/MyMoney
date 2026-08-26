package id.my.mymoney.data.model

import kotlinx.serialization.Serializable

@Serializable
data class AccountResponse(
    val id: String,
    val account_name: String,
    val bank_name: String? = null,
    @Serializable(with = FlexibleStringSerializer::class) val initial_balance: String,
    @Serializable(with = FlexibleStringSerializer::class) val current_balance: String,
    @Serializable(with = FlexibleStringSerializer::class) val net_balance: String = "0",
    val is_active: Boolean = true,
    val created_at: String,
) {
    val currentBalanceDecimal: java.math.BigDecimal
        get() = runCatching { java.math.BigDecimal(current_balance) }
            .getOrDefault(java.math.BigDecimal.ZERO)

    val netBalanceDecimal: java.math.BigDecimal
        get() = runCatching { java.math.BigDecimal(net_balance) }
            .getOrDefault(java.math.BigDecimal.ZERO)
}

@Serializable
data class AccountCreateRequest(
    val account_name: String,
    val bank_name: String? = null,
    @Serializable(with = FlexibleStringSerializer::class) val initial_balance: String = "0",
)

/** All fields optional — PATCH semantics. */
@Serializable
data class AccountUpdateRequest(
    val account_name: String? = null,
    val bank_name: String? = null,
)

/**
 * Deactivation request (ARCHITECTURE.md §4.4). Accounts are NEVER deleted —
 * only deactivated. `target_account_id` is required by the backend when the
 * source still has a non-zero balance (money is moved via balancing txs).
 */
@Serializable
data class AccountDeactivateRequest(
    val target_account_id: String? = null,
)
