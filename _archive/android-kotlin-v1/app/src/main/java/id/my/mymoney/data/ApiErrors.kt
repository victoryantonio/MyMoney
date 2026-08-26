package id.my.mymoney.data

import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import retrofit2.HttpException
import java.io.IOException

/**
 * Converts an exception thrown by Retrofit into a user-friendly message.
 * FastAPI error bodies look like `{"detail": "..."}` — we extract that.
 */
fun Throwable.toUserMessage(): String = when (this) {
    is HttpException -> {
        val detail = runCatching {
            val body = response()?.errorBody()?.string() ?: return@runCatching null
            val root: JsonObject = errorJson.parseToJsonElement(body).jsonObject
            root["detail"]?.jsonPrimitive?.content
        }.getOrNull()
        detail ?: "Server error (${code()})"
    }
    is IOException -> "Network error — check your connection"
    is kotlinx.serialization.SerializationException -> "Unexpected server response"
    else -> message ?: "Something went wrong"
}

private val errorJson: Json = Json { ignoreUnknownKeys = true }
