package id.my.mymoney.ui.auth

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle

@Composable
fun AuthScreen(viewModel: AuthViewModel, onAuthenticated: () -> Unit) {
    val authState by viewModel.authState.collectAsStateWithLifecycle()
    val busy by viewModel.busy.collectAsStateWithLifecycle()
    val error by viewModel.error.collectAsStateWithLifecycle()

    if (authState is id.my.mymoney.data.AuthState.Authenticated) {
        onAuthenticated()
        return
    }

    var tab by rememberSaveable { mutableIntStateOf(0) }
    var displayName by rememberSaveable { mutableStateOf("") }
    var email by rememberSaveable { mutableStateOf("") }
    var password by rememberSaveable { mutableStateOf("") }
    var localError by remember { mutableStateOf<String?>(null) }
    var passwordVisible by rememberSaveable { mutableStateOf(false) }
    val emailFocus = remember { FocusRequester() }
    val passwordFocus = remember { FocusRequester() }
    val focusManager = LocalFocusManager.current

    fun submit() {
        if (busy) return
        localError = null
        if (email.isBlank() || password.isBlank()) {
            localError = "Email and password are required"
            return
        }
        if (tab == 1) {
            if (displayName.isBlank()) {
                localError = "Display name is required"
                return
            }
            if (password.length < 8 || !password.any { it.isLetter() } || !password.any { it.isDigit() }) {
                localError = "Password must be 8+ chars with at least one letter and one digit"
                return
            }
            viewModel.register(displayName, email, password) { onAuthenticated() }
        } else {
            viewModel.login(email, password) { onAuthenticated() }
        }
    }

    Column(
        modifier = Modifier
            .fillMaxSize()
            .verticalScroll(rememberScrollState())
            .padding(24.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.Center,
    ) {
        Text("MyMoney", style = MaterialTheme.typography.headlineLarge)
        Text(
            "Track your income & expenses",
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        Spacer(Modifier.height(24.dp))

        TabRow(selectedTabIndex = tab) {
            Tab(selected = tab == 0, onClick = { tab = 0; localError = null }, text = { Text("Login") })
            Tab(selected = tab == 1, onClick = { tab = 1; localError = null }, text = { Text("Register") })
        }
        Spacer(Modifier.height(16.dp))

        if (tab == 1) {
            OutlinedTextField(
                value = displayName,
                onValueChange = { displayName = it },
                label = { Text("Display name") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Text,
                    imeAction = ImeAction.Next,
                ),
                keyboardActions = KeyboardActions(onNext = { emailFocus.requestFocus() }),
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))
        }

        OutlinedTextField(
            value = email,
            onValueChange = { email = it },
            label = { Text("Email") },
            singleLine = true,
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Email,
                imeAction = ImeAction.Next,
            ),
            keyboardActions = KeyboardActions(onNext = { passwordFocus.requestFocus() }),
            modifier = Modifier.fillMaxWidth().focusRequester(emailFocus),
        )
        Spacer(Modifier.height(12.dp))

        OutlinedTextField(
            value = password,
            onValueChange = { password = it },
            label = { Text("Password") },
            singleLine = true,
            visualTransformation = if (passwordVisible) VisualTransformation.None else PasswordVisualTransformation(),
            keyboardOptions = KeyboardOptions(
                keyboardType = KeyboardType.Password,
                imeAction = ImeAction.Done,
            ),
            keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus(); submit() }),
            trailingIcon = {
                IconButton(onClick = { passwordVisible = !passwordVisible }) {
                    Icon(
                        Icons.Outlined.VisibilityOff,
                        contentDescription = if (passwordVisible) "Hide password" else "Show password",
                        tint = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            },
            modifier = Modifier.fillMaxWidth().focusRequester(passwordFocus),
        )
        Spacer(Modifier.height(20.dp))

        val message = localError ?: error
        if (message != null) {
            Text(
                message,
                color = MaterialTheme.colorScheme.error,
                style = MaterialTheme.typography.bodySmall,
                modifier = Modifier.padding(bottom = 8.dp),
            )
        }

        Button(
            onClick = { submit() },
            enabled = !busy,
            modifier = Modifier.fillMaxWidth(),
        ) {
            if (busy) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    CircularProgressIndicator(modifier = Modifier.height(18.dp), strokeWidth = 2.dp)
                    Spacer(Modifier.padding(start = 8.dp))
                    Text(if (tab == 1) "Creating account…" else "Logging in…")
                }
            } else {
                Text(if (tab == 1) "Create account" else "Login")
            }
        }
    }
}
