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
import id.my.mymoney.data.model.PendingReceiptData
import kotlinx.coroutines.flow.MutableStateFlow

/** Manual DI container — keeps the dependency graph small and testable. */
class AppContainer(context: Context) {
    val authState: AuthStateHolder = AuthStateHolder()
    val tokenStore: TokenStore = DataStoreTokenStore(context)
    val themeStore: ThemeStore = DataStoreThemeStore(context)
    val api: ApiService = ApiClient.create(authState, tokenStore)
    val authRepository: AuthRepository = AuthRepository(api, tokenStore, authState)

    /**
     * Hasil OCR kamera yang menunggu form New Transaction dibuka.
     * Ditulis oleh ReceiptViewModel (alur kamera), dibaca & dikosongkan oleh
     * TransactionFormViewModel — sehingga tombol "+" dan kamera membuka
     * SATU form New Transaction yang sama (multi-item).
     */
    val pendingReceipt: MutableStateFlow<PendingReceiptData?> = MutableStateFlow(null)
}

class MyMoneyApp : Application() {
    val container: AppContainer by lazy { AppContainer(this) }
}
