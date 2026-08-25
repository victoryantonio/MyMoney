package id.my.mymoney.data

/** Holds the JWT pair in memory (volatile, read synchronously by OkHttp interceptors). */
class AuthStateHolder {
    @Volatile
    var accessToken: String? = null

    @Volatile
    var refreshToken: String? = null

    fun update(access: String, refresh: String?) {
        accessToken = access
        refreshToken = refresh
    }

    fun clear() {
        accessToken = null
        refreshToken = null
    }
}
