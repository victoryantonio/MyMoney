package id.my.mymoney

import android.app.Application
import android.content.Context
import id.my.mymoney.data.ApiClient
import id.my.mymoney.data.AuthRepository
import id.my.mymoney.data.AuthStateHolder
import id.my.mymoney.data.DataStoreThemeStore
import id.my.mymoney.data.DataStoreTokenStore
import id.my.mymoney.data.ThemeStore
import id.my.mymoney.data.TokenStore
import id.my.mymoney.data.api.ApiService

/** Manual DI container — keeps the dependency graph small and testable. */
class AppContainer(context: Context) {
    val authState: AuthStateHolder = AuthStateHolder()
    val tokenStore: TokenStore = DataStoreTokenStore(context)
    val themeStore: ThemeStore = DataStoreThemeStore(context)
    val api: ApiService = ApiClient.create(authState, tokenStore)
    val authRepository: AuthRepository = AuthRepository(api, tokenStore, authState)
}

class MyMoneyApp : Application() {
    val container: AppContainer by lazy { AppContainer(this) }
}
