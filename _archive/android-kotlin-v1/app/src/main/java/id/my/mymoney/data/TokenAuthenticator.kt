package id.my.mymoney.data

import id.my.mymoney.data.model.RefreshRequest
import id.my.mymoney.data.model.RefreshResponse
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.encodeToString
import okhttp3.Authenticator
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import okhttp3.Response
import okhttp3.Route
import java.util.concurrent.TimeUnit

/**
 * On a 401 response, exchanges the refresh token for a new access token and
 * retries the original request. If the refresh itself fails, the session is
 * cleared (forces the user back to the login screen) and no retry happens.
 *
 * The refresh call uses a raw OkHttp request (not Retrofit) to avoid a
 * circular dependency with the authenticated client.
 */
class TokenAuthenticator(
    private val state: AuthStateHolder,
    private val tokenStore: TokenStore,
    private val baseUrl: String,
    private val json: Json,
) : Authenticator {

    private val lock = Any()

    override fun authenticate(route: Route?, response: Response): Request? {
        val refresh = state.refreshToken ?: return null

        synchronized(lock) {
            // Another concurrent request may have already refreshed the token.
            val currentAccess = state.accessToken
            val usedToken = response.request.header("Authorization")?.removePrefix("Bearer ")
            if (currentAccess != null && usedToken != null && usedToken != currentAccess) {
                return retryWith(response, currentAccess)
            }

            val refreshed: RefreshResponse? = runBlocking {
                runCatching {
                    val payload = json.encodeToString(
                        RefreshRequest.serializer(),
                        RefreshRequest(refresh_token = refresh)
                    )
                    val request = Request.Builder()
                        .url(baseUrl.trimEnd('/') + "/api/auth/refresh")
                        .post(payload.toRequestBody("application/json".toMediaType()))
                        .build()
                    val client = OkHttpClient.Builder()
                        .connectTimeout(15, TimeUnit.SECONDS)
                        .readTimeout(15, TimeUnit.SECONDS)
                        .build()
                    client.newCall(request).execute().use { resp ->
                        if (!resp.isSuccessful) return@runCatching null
                        val raw = resp.body?.string() ?: return@runCatching null
                        json.decodeFromString(RefreshResponse.serializer(), raw)
                    }
                }.getOrNull()
            }

            if (refreshed != null) {
                state.update(refreshed.access_token, refresh)
                runBlocking { tokenStore.save(refreshed.access_token, refresh) }
                return retryWith(response, refreshed.access_token)
            }

            // Refresh failed → invalidate the session.
            state.clear()
            runBlocking { tokenStore.clear() }
            return null
        }
    }

    private fun retryWith(response: Response, token: String): Request =
        response.request.newBuilder()
            .header("Authorization", "Bearer $token")
            .build()
}
