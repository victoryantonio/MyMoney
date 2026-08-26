package id.my.mymoney

import id.my.mymoney.data.AuthRepository
import id.my.mymoney.data.AuthState
import id.my.mymoney.data.AuthStateHolder
import id.my.mymoney.data.TokenStore
import id.my.mymoney.ui.auth.AuthViewModel
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class AuthViewModelTest {

    private val dispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(dispatcher)
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    private fun vm(api: FakeApiService): AuthViewModel {
        val store = object : TokenStore {
            override suspend fun load(): Pair<String?, String?> = null to null
            override suspend fun save(accessToken: String, refreshToken: String?) {}
            override suspend fun clear() {}
            override fun hasTokens(): kotlinx.coroutines.flow.Flow<Boolean> =
                kotlinx.coroutines.flow.flowOf(false)
        }
        val repo = AuthRepository(api, store, AuthStateHolder())
        return AuthViewModel(repo)
    }

    @Test
    fun `login success calls onSuccess`() = runTest(dispatcher) {
        val viewModel = vm(FakeApiService())
        var success = false

        viewModel.login("a@b.com", "pass1234") { success = true }
        advanceUntilIdle()

        assertTrue(success)
        assertTrue(viewModel.authState.value is AuthState.Authenticated)
        assertNull(viewModel.error.value)
    }

    @Test
    fun `login failure surfaces user message`() = runTest(dispatcher) {
        val viewModel = vm(FakeApiService().apply { loginShouldFail = true })

        viewModel.login("a@b.com", "wrong")
        advanceUntilIdle()

        assertNotNull(viewModel.error.value)
        assertTrue(viewModel.authState.value is AuthState.Unauthenticated)
    }

    @Test
    fun `register failure surfaces error and stays unauthenticated`() = runTest(dispatcher) {
        val viewModel = vm(FakeApiService().apply { registerShouldFail = true })

        viewModel.register("Bob", "b@c.com", "strongpass1")
        advanceUntilIdle()

        assertNotNull(viewModel.error.value)
        assertTrue(viewModel.authState.value is AuthState.Unauthenticated)
    }

    @Test
    fun `busy flag guards double submits`() = runTest(dispatcher) {
        val viewModel = vm(FakeApiService())
        var calls = 0
        val slowApi = FakeApiService()
        val viewModel2 = vm(slowApi)

        viewModel2.login("a@b.com", "pass1234") { calls++ }
        viewModel2.login("a@b.com", "pass1234") { calls++ } // ignored while busy
        advanceUntilIdle()

        assertEquals(1, calls)
    }

    @Test
    fun `logout returns to unauthenticated`() = runTest(dispatcher) {
        val viewModel = vm(FakeApiService())
        viewModel.login("a@b.com", "pass1234")
        advanceUntilIdle()
        assertTrue(viewModel.authState.value is AuthState.Authenticated)

        viewModel.logout()
        advanceUntilIdle()

        assertTrue(viewModel.authState.value is AuthState.Unauthenticated)
    }
}
