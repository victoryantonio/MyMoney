package id.my.mymoney.ui.auth

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.AccountBalanceWallet
import androidx.compose.material.icons.outlined.VisibilityOff
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Surface
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.input.PasswordVisualTransformation
import androidx.compose.ui.text.input.VisualTransformation
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import id.my.mymoney.data.toUserMessage

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
    var showForgot by remember { mutableStateOf(false) }
    var forgotBusy by remember { mutableStateOf(false) }
    var forgotResult by remember { mutableStateOf<Result<String>?>(null) }
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

    fun submitForgot(email: String) {
        if (forgotBusy) return
        forgotBusy = true
        forgotResult = null
        viewModel.forgotPassword(email) { result ->
            forgotBusy = false
            forgotResult = result
        }
    }

    // Surface penuh agar latar mengikuti tema (dark mode konsisten — TASK 5).
    Surface(
        modifier = Modifier.fillMaxSize(),
        color = MaterialTheme.colorScheme.surface,
    ) {
        Column(
            modifier = Modifier
                .fillMaxSize()
                .verticalScroll(rememberScrollState())
                .padding(24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
        ) {
            Box(
                modifier = Modifier
                    .size(72.dp)
                    .clip(CircleShape)
                    .background(MaterialTheme.colorScheme.primaryContainer),
                contentAlignment = Alignment.Center,
            ) {
                Icon(
                    Icons.Filled.AccountBalanceWallet,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.primary,
                    modifier = Modifier.size(36.dp),
                )
            }
        Spacer(Modifier.height(16.dp))
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
        if (tab == 0) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
            ) {
                TextButton(
                    onClick = {
                        showForgot = true
                        forgotResult = null
                    },
                ) { Text("Forgot password?") }
            }
        }
        Spacer(Modifier.height(12.dp))

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

    if (showForgot) {
        ForgotPasswordDialog(
            busy = forgotBusy,
            result = forgotResult,
            onDismiss = { showForgot = false },
            onSubmit = { email -> submitForgot(email) },
        )
    }
}

/**
 * Forgot-password dialog (TASK 1). Anti-enumeration: on success we show the
 * backend's GENERIC message — identical whether or not the email is
 * registered (backend always returns the same 200 for known/unknown
 * addresses).
 */
@Composable
private fun ForgotPasswordDialog(
    busy: Boolean,
    result: Result<String>?,
    onDismiss: () -> Unit,
    onSubmit: (String) -> Unit,
) {
    var email by remember { mutableStateOf("") }
    val success = result?.getOrNull()
    val failure = result?.exceptionOrNull()?.toUserMessage()

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Reset password") },
        text = {
            Column {
                if (success != null) {
                    Text(success, style = MaterialTheme.typography.bodyMedium)
                } else {
                    OutlinedTextField(
                        value = email,
                        onValueChange = { email = it },
                        label = { Text("Email") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Email,
                            imeAction = ImeAction.Done,
                        ),
                        keyboardActions = KeyboardActions(onDone = {
                            if (email.isNotBlank() && !busy) onSubmit(email.trim())
                        }),
                        modifier = Modifier.fillMaxWidth(),
                    )
                    if (failure != null) {
                        Spacer(Modifier.height(8.dp))
                        Text(
                            failure,
                            color = MaterialTheme.colorScheme.error,
                            style = MaterialTheme.typography.bodySmall,
                        )
                    }
                }
            }
        },
        confirmButton = {
            if (success != null) {
                TextButton(onClick = onDismiss) { Text("OK") }
            } else {
                TextButton(
                    onClick = { onSubmit(email.trim()) },
                    enabled = email.isNotBlank() && !busy,
                ) { Text("Send reset link") }
            }
        },
        dismissButton = {
            if (success == null) {
                TextButton(onClick = onDismiss) { Text("Cancel") }
            }
        },
    )
}
