package id.my.mymoney.data

import id.my.mymoney.BuildConfig
import id.my.mymoney.data.api.ApiService
import kotlinx.serialization.json.Json
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import retrofit2.Retrofit
import retrofit2.converter.kotlinx.serialization.asConverterFactory
import java.util.concurrent.TimeUnit

/** Builds the shared Retrofit client wired with auth interceptor + silent refresh. */
object ApiClient {

    /** Trailing-slash base URL as required by Retrofit. */
    val BASE_URL: String = BuildConfig.API_BASE_URL.trimEnd('/') + "/"

    val json: Json = Json {
        ignoreUnknownKeys = true
        coerceInputValues = true
        explicitNulls = false
    }

    fun create(state: AuthStateHolder, tokenStore: TokenStore): ApiService {
        val client = OkHttpClient.Builder()
            .addInterceptor(AuthInterceptor(state))
            .authenticator(TokenAuthenticator(state, tokenStore, BASE_URL, json))
            .connectTimeout(30, TimeUnit.SECONDS)
            .readTimeout(30, TimeUnit.SECONDS)
            .writeTimeout(30, TimeUnit.SECONDS)
            .build()

        val retrofit = Retrofit.Builder()
            .baseUrl(BASE_URL)
            .client(client)
            .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
            .build()

        return retrofit.create(ApiService::class.java)
    }
}
