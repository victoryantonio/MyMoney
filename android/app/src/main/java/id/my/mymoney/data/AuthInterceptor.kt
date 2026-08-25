package id.my.mymoney.data

import okhttp3.Interceptor
import okhttp3.Response

/** Injects `Authorization: Bearer <access_token>` on every request when logged in. */
class AuthInterceptor(private val state: AuthStateHolder) : Interceptor {
    override fun intercept(chain: Interceptor.Chain): Response {
        val token = state.accessToken
        val request = if (token != null) {
            chain.request().newBuilder()
                .header("Authorization", "Bearer $token")
                .build()
        } else {
            chain.request()
        }
        return chain.proceed(request)
    }
}
