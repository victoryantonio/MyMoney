package com.mymoney.app.di

import com.jakewharton.retrofit2.converter.kotlinx.serialization.asConverterFactory
import com.mymoney.app.BuildConfig
import com.mymoney.app.data.api.*
import com.mymoney.app.data.local.TokenStore
import dagger.Module
import dagger.Provides
import dagger.hilt.InstallIn
import dagger.hilt.components.SingletonComponent
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import okhttp3.Authenticator
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.Response
import okhttp3.Route
import okhttp3.logging.HttpLoggingInterceptor
import retrofit2.Retrofit
import javax.inject.Qualifier
import javax.inject.Singleton

@Qualifier
@Retention(AnnotationRetention.BINARY)
annotation class AuthRetrofit // unauthenticated — for login/register/refresh only

private val json = Json {
    ignoreUnknownKeys = true
    coerceInputValues = true
}

@Module
@InstallIn(SingletonComponent::class)
object NetworkModule {

    @Provides
    @Singleton
    fun provideLoggingInterceptor(): HttpLoggingInterceptor =
        HttpLoggingInterceptor().apply {
            level = if (BuildConfig.DEBUG) {
                HttpLoggingInterceptor.Level.BODY
            } else {
                HttpLoggingInterceptor.Level.NONE
            }
        }

    /**
     * Authenticated OkHttpClient.
     * Adds Bearer token from TokenStore to every request.
     * Auto-refreshes token via Authenticator when 401 is received.
     */
    @Provides
    @Singleton
    fun provideOkHttpClient(
        loggingInterceptor: HttpLoggingInterceptor,
        tokenStore: TokenStore,
    ): OkHttpClient = OkHttpClient.Builder()
        .addInterceptor(loggingInterceptor)
        // Attach access token to every request
        .addInterceptor { chain ->
            val token = runBlocking { tokenStore.accessToken.first() }
            val request = if (token != null) {
                chain.request().newBuilder()
                    .addHeader("Authorization", "Bearer $token")
                    .build()
            } else {
                chain.request()
            }
            chain.proceed(request)
        }
        // Auto-refresh on 401
        .authenticator(TokenAuthenticator(tokenStore))
        .build()

    @Provides
    @Singleton
    @AuthRetrofit
    fun provideAuthOkHttpClient(loggingInterceptor: HttpLoggingInterceptor): OkHttpClient =
        OkHttpClient.Builder()
            .addInterceptor(loggingInterceptor)
            .build()

    @Provides
    @Singleton
    fun provideRetrofit(okHttpClient: OkHttpClient): Retrofit = Retrofit.Builder()
        .baseUrl(BuildConfig.BASE_URL + "/")
        .client(okHttpClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    @Provides
    @Singleton
    @AuthRetrofit
    fun provideAuthRetrofit(@AuthRetrofit okHttpClient: OkHttpClient): Retrofit = Retrofit.Builder()
        .baseUrl(BuildConfig.BASE_URL + "/")
        .client(okHttpClient)
        .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
        .build()

    // API instances
    @Provides @Singleton
    fun provideAuthApi(@AuthRetrofit retrofit: Retrofit): AuthApi =
        retrofit.create(AuthApi::class.java)

    @Provides @Singleton
    fun provideTransactionsApi(retrofit: Retrofit): TransactionsApi =
        retrofit.create(TransactionsApi::class.java)

    @Provides @Singleton
    fun provideAccountsApi(retrofit: Retrofit): AccountsApi =
        retrofit.create(AccountsApi::class.java)

    @Provides @Singleton
    fun provideCategoriesApi(retrofit: Retrofit): CategoriesApi =
        retrofit.create(CategoriesApi::class.java)

    @Provides @Singleton
    fun provideReportsApi(retrofit: Retrofit): ReportsApi =
        retrofit.create(ReportsApi::class.java)

    @Provides @Singleton
    fun provideReceiptsApi(retrofit: Retrofit): ReceiptsApi =
        retrofit.create(ReceiptsApi::class.java)
}

/**
 * OkHttp Authenticator — called automatically when server returns 401.
 * Refreshes access token using the stored refresh token.
 */
class TokenAuthenticator(private val tokenStore: TokenStore) : Authenticator {
    override fun authenticate(route: Route?, response: Response): Request? {
        // Prevent infinite loop if refresh also fails
        if (response.request.header("Authorization-Refresh") != null) return null

        val refreshToken = runBlocking { tokenStore.refreshToken.first() } ?: return null

        return try {
            // Call refresh endpoint directly (no interceptor loop)
            val refreshApi = Retrofit.Builder()
                .baseUrl(BuildConfig.BASE_URL + "/")
                .addConverterFactory(json.asConverterFactory("application/json".toMediaType()))
                .build()
                .create(AuthApi::class.java)

            val newTokens = runBlocking {
                refreshApi.refresh(
                    com.mymoney.app.data.model.RefreshTokenRequest(refreshToken)
                )
            }
            runBlocking { tokenStore.saveTokens(newTokens.accessToken, newTokens.refreshToken) }

            response.request.newBuilder()
                .removeHeader("Authorization")
                .addHeader("Authorization", "Bearer ${newTokens.accessToken}")
                .addHeader("Authorization-Refresh", "true") // prevent loop
                .build()
        } catch (e: Exception) {
            runBlocking { tokenStore.clearTokens() }
            null
        }
    }
}
