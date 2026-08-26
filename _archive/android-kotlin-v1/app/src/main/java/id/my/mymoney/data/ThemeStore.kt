package id.my.mymoney.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import androidx.datastore.preferences.preferencesDataStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/** Theme preference (DESIGN.md §3): follow system by default, overridable in Profile. */
enum class ThemeMode(val stored: String) {
    SYSTEM("system"),
    LIGHT("light"),
    DARK("dark"),
}

/** Persistence contract for the theme mode — implemented with DataStore, faked in tests. */
interface ThemeStore {
    val themeMode: Flow<ThemeMode>
    suspend fun setThemeMode(mode: ThemeMode)
}

private val Context.themeDataStore by preferencesDataStore(name = "theme")

class DataStoreThemeStore(private val context: Context) : ThemeStore {

    private object Keys {
        val MODE = stringPreferencesKey("theme_mode")
    }

    override val themeMode: Flow<ThemeMode> = context.themeDataStore.data.map { prefs ->
        ThemeMode.entries.firstOrNull { it.stored == prefs[Keys.MODE] } ?: ThemeMode.SYSTEM
    }

    override suspend fun setThemeMode(mode: ThemeMode) {
        context.themeDataStore.edit { prefs -> prefs[Keys.MODE] = mode.stored }
    }
}
