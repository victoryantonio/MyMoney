package id.my.mymoney.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.flow.map

/** Persistence contract for the JWT pair — implemented with DataStore, faked in tests. */
interface TokenStore {
    /** Returns (accessToken, refreshToken). */
    suspend fun load(): Pair<String?, String?>
    suspend fun save(accessToken: String, refreshToken: String?)
    suspend fun clear()
    fun hasTokens(): Flow<Boolean>
}

private val Context.authDataStore by preferencesDataStore(name = "auth_tokens")

class DataStoreTokenStore(private val context: Context) : TokenStore {

    private object Keys {
        val ACCESS = stringPreferencesKey("access_token")
        val REFRESH = stringPreferencesKey("refresh_token")
    }

    override suspend fun load(): Pair<String?, String?> {
        val prefs = context.authDataStore.data.first()
        return prefs[Keys.ACCESS] to prefs[Keys.REFRESH]
    }

    override suspend fun save(accessToken: String, refreshToken: String?) {
        context.authDataStore.edit { prefs ->
            prefs[Keys.ACCESS] = accessToken
            if (refreshToken != null) prefs[Keys.REFRESH] = refreshToken
        }
    }

    override suspend fun clear() {
        context.authDataStore.edit { prefs ->
            prefs.remove(Keys.ACCESS)
            prefs.remove(Keys.REFRESH)
        }
    }

    override fun hasTokens(): Flow<Boolean> =
        context.authDataStore.data.map { it[Keys.ACCESS] != null }
}
