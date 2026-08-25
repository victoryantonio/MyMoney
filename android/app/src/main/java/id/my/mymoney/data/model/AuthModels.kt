package id.my.mymoney.data.model

import kotlinx.serialization.KSerializer
import kotlinx.serialization.Serializable
import kotlinx.serialization.descriptors.PrimitiveKind
import kotlinx.serialization.descriptors.PrimitiveSerialDescriptor
import kotlinx.serialization.descriptors.SerialDescriptor
import kotlinx.serialization.encoding.Decoder
import kotlinx.serialization.encoding.Encoder
import kotlinx.serialization.json.JsonDecoder
import kotlinx.serialization.json.JsonPrimitive

/**
 * Backend (pydantic v2) serializes `Decimal` as a JSON **string** ("150000.00"),
 * but to stay robust against either representation this serializer accepts
 * both a JSON string and a raw JSON number, always producing a String.
 */
object FlexibleStringSerializer : KSerializer<String> {
    override val descriptor: SerialDescriptor =
        PrimitiveSerialDescriptor("FlexibleString", PrimitiveKind.STRING)

    override fun deserialize(decoder: Decoder): String = when (decoder) {
        is JsonDecoder -> {
            val el = decoder.decodeJsonElement()
            when (el) {
                is JsonPrimitive -> el.content
                else -> el.toString()
            }
        }
        else -> decoder.decodeString()
    }

    override fun serialize(encoder: Encoder, value: String) = encoder.encodeString(value)
}

// ── Auth ────────────────────────────────────────────────────────────────────

@Serializable
data class LoginRequest(
    val email: String,
    val password: String,
)

@Serializable
data class RegisterRequest(
    val email: String,
    val password: String,
    val display_name: String,
    val timezone: String = "Asia/Jakarta",
)

@Serializable
data class RefreshRequest(
    val refresh_token: String,
)

/** Response of POST /api/auth/login. */
@Serializable
data class TokenResponse(
    val access_token: String,
    val refresh_token: String,
    val token_type: String = "bearer",
)

/** Response of POST /api/auth/refresh — access token only. */
@Serializable
data class RefreshResponse(
    val access_token: String,
    val token_type: String = "bearer",
)

@Serializable
data class UserResponse(
    val id: String,
    val email: String,
    val display_name: String,
    val timezone: String,
    val is_active: Boolean,
    val created_at: String? = null,
)
