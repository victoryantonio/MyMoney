package id.my.mymoney

import id.my.mymoney.data.AuthRepository
import id.my.mymoney.data.AuthState
import id.my.mymoney.data.AuthStateHolder
import id.my.mymoney.data.TokenStore
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.runTest
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

private class InMemoryTokenStore : TokenStore {
    private var access: String? = null
    private var refresh: String? = null
    private val _has = MutableStateFlow(false)

    override suspend fun load(): Pair<String?, String?> = access to refresh
    override suspend fun save(accessToken: String, refreshToken: String?) {
        access = accessToken
        refresh = refreshToken
        _has.value = true
    }

    override suspend fun clear() {
        access = null
        refresh = null
        _has.value = false
    }

    override fun hasTokens(): Flow<Boolean> = _has
}

class AuthRepositoryTest {

    private fun repo(api: FakeApiService, store: TokenStore = InMemoryTokenStore()) =
        AuthRepository(api, store, AuthStateHolder())

    @Test
    fun `login success sets authenticated state and persists tokens`() = runTest {
        val api = FakeApiService()
        val store = InMemoryTokenStore()
        val r = repo(api, store)

        val result = r.login("a@b.com", "secret123")

        assertTrue(result.isSuccess)
        assertTrue(r.authState.value is AuthState.Authenticated)
        val (access, refresh) = store.load()
        assertEquals("access-1", access)
        assertEquals("refresh-1", refresh)
    }

    @Test
    fun `login failure returns error and stays unauthenticated`() = runTest {
        val api = FakeApiService().apply { loginShouldFail = true }
        val r = repo(api)

        val result = r.login("a@b.com", "wrong")

        assertTrue(result.isFailure)
        assertTrue(r.authState.value is AuthState.Unauthenticated)
        val (access, refresh) = InMemoryTokenStore().load()
        assertNull(access)
        assertNull(refresh)
    }

    @Test
    fun `bootstrap with stored token authenticates via me`() = runTest {
        val api = FakeApiService()
        val store = InMemoryTokenStore().apply { save("access-1", "refresh-1") }
        val r = repo(api, store)

        r.bootstrap()

        val s = r.authState.value
        assertTrue(s is AuthState.Authenticated)
        assertEquals("Alice", (s as AuthState.Authenticated).user.display_name)
    }

    @Test
    fun `bootstrap refreshes when me fails and then authenticates`() = runTest {
        // First me() call fails (expired access token), second succeeds after refresh.
        val api = FakeApiService().apply { meFailuresRemaining = 1 }
        val store = InMemoryTokenStore().apply { save("expired-access", "refresh-1") }
        val r = repo(api, store)

        r.bootstrap()

        assertTrue(r.authState.value is AuthState.Authenticated)
        assertTrue(api.refreshCalls >= 1)
        val (access, _) = store.load()
        assertEquals("access-2", access)
    }

    @Test
    fun `bootstrap with no token is unauthenticated`() = runTest {
        val r = repo(FakeApiService())

        r.bootstrap()

        assertTrue(r.authState.value is AuthState.Unauthenticated)
    }

    @Test
    fun `refresh failure during bootstrap logs out`() = runTest {
        val api = FakeApiService().apply {
            meShouldFail = true
            refreshShouldFail = true
        }
        val store = InMemoryTokenStore().apply { save("expired", "bad-refresh") }
        val r = repo(api, store)

        r.bootstrap()

        assertTrue(r.authState.value is AuthState.Unauthenticated)
        val (access, refresh) = store.load()
        assertNull(access)
        assertNull(refresh)
    }

    @Test
    fun `logout clears state and tokens`() = runTest {
        val api = FakeApiService()
        val store = InMemoryTokenStore().apply { save("access-1", "refresh-1") }
        val r = repo(api, store)
        r.bootstrap()

        r.logout()

        assertTrue(r.authState.value is AuthState.Unauthenticated)
        val (access, refresh) = store.load()
        assertNull(access)
        assertNull(refresh)
    }

    @Test
    fun `register success auto-logs-in`() = runTest {
        val api = FakeApiService()
        val store = InMemoryTokenStore()
        val r = repo(api, store)

        val result = r.register("Bob", "b@c.com", "password123")

        assertTrue(result.isSuccess)
        assertTrue(r.authState.value is AuthState.Authenticated)
        assertEquals("Bob", (r.authState.value as AuthState.Authenticated).user.display_name)
    }
}
