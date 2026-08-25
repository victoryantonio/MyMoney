package id.my.mymoney.data.model

import kotlinx.serialization.Serializable

@Serializable
data class CategoryResponse(
    val id: String,
    val name: String,
    val type: String, // "income" | "expense"
    val is_default: Boolean = false,
    val is_active: Boolean = true,
    val user_id: String? = null,
)

@Serializable
data class CategoryCreateRequest(
    val name: String,
    val type: String,
)

/** All fields optional — PATCH semantics. */
@Serializable
data class CategoryUpdateRequest(
    val name: String? = null,
    val type: String? = null,
)
