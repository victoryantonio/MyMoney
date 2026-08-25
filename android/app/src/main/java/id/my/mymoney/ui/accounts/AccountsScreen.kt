package id.my.mymoney.ui.accounts

import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material.icons.outlined.PowerSettingsNew
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.data.model.AccountResponse
import id.my.mymoney.ui.components.EmptyState
import id.my.mymoney.ui.components.ErrorView
import id.my.mymoney.ui.components.LoadingView
import id.my.mymoney.ui.components.MyMoneyButton
import id.my.mymoney.ui.components.MyMoneyCard
import id.my.mymoney.ui.theme.MoneyLarge
import id.my.mymoney.util.Formatters
import java.math.BigDecimal

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AccountsScreen(viewModel: AccountsViewModel = viewModel(factory = AccountsViewModel.Factory)) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var editing by remember { mutableStateOf<AccountResponse?>(null) }
    var deactivating by remember { mutableStateOf<AccountResponse?>(null) }
    var showCreate by remember { mutableStateOf(false) }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Accounts") }) },
        floatingActionButton = {
            FloatingActionButton(onClick = { showCreate = true }) {
                Icon(Icons.Filled.Add, contentDescription = "Add account")
            }
        },
    ) { innerPadding ->
        when {
            state.loading -> LoadingView()
            state.error != null && state.accounts.isEmpty() ->
                ErrorView(state.error, onRetry = { viewModel.load() })
            state.accounts.isEmpty() -> EmptyState("No accounts yet. Tap + to add your first account.")
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(innerPadding),
                    contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(state.accounts, key = { it.id }) { acc ->
                        AccountRow(
                            acc = acc,
                            onEdit = { editing = acc },
                            onDeactivate = { deactivating = acc },
                        )
                    }
                }
            }
        }
    }

    if (showCreate) {
        AccountEditDialog(
            title = "New account",
            initialName = "",
            initialBank = "",
            showBalance = true,
            onDismiss = { showCreate = false },
            onSave = { name, bank, balance ->
                viewModel.create(name, bank, balance) { ok, _ -> if (ok) showCreate = false }
            },
        )
    }

    editing?.let { acc ->
        AccountEditDialog(
            title = "Edit account",
            initialName = acc.account_name,
            initialBank = acc.bank_name ?: "",
            showBalance = false,
            onDismiss = { editing = null },
            onSave = { name, bank, _ ->
                viewModel.update(acc, name, bank) { ok, _ -> if (ok) editing = null }
            },
        )
    }

    deactivating?.let { acc ->
        DeactivateAccountSheet(
            acc = acc,
            activeAccounts = state.accounts.filter { it.id != acc.id },
            busy = state.busy,
            onConfirm = { targetId ->
                viewModel.deactivate(acc, targetId) { ok, _ -> if (ok) deactivating = null }
            },
            onDismiss = { deactivating = null },
        )
    }
}

/**
 * Bottom sheet untuk nonaktifkan akun (ARCHITECTURE.md §4.4).
 * Akun TIDAK PERNAH dihapus — hanya is_active = FALSE.
 * Saldo != 0 → wajib pilih akun tujuan; saldo dipindah via transaksi penyeimbang.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DeactivateAccountSheet(
    acc: AccountResponse,
    activeAccounts: List<AccountResponse>,
    busy: Boolean,
    onConfirm: (String?) -> Unit,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    val balance = acc.currentBalanceDecimal()
    var targetId by remember { mutableStateOf<String?>(null) }

    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = sheetState) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .padding(bottom = 32.dp),
        ) {
            Text(
                "Deactivate account",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.SemiBold,
            )
            Spacer(Modifier.height(8.dp))
            Text(
                "\"${acc.account_name}\" will be deactivated. It won't appear as a payment option for new transactions, but its full history is kept.",
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(16.dp))

            Text(
                "Current balance",
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Text(Formatters.idr(balance), style = MoneyLarge, color = MaterialTheme.colorScheme.onSurface)

            if (balance != BigDecimal.ZERO) {
                Spacer(Modifier.height(16.dp))
                Text(
                    "Move balance to",
                    style = MaterialTheme.typography.labelLarge,
                    fontWeight = FontWeight.Medium,
                )
                Spacer(Modifier.height(8.dp))
                if (activeAccounts.isEmpty()) {
                    Text(
                        "No other active account available. Create one first, then deactivate this account.",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
                activeAccounts.forEach { a ->
                    val selected = a.id == targetId
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(
                                if (selected) MaterialTheme.colorScheme.primaryContainer
                                else MaterialTheme.colorScheme.surfaceVariant
                            )
                            .clickable { targetId = a.id }
                            .padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        RadioButton(selected = selected, onClick = { targetId = a.id })
                        Spacer(Modifier.width(8.dp))
                        Column(modifier = Modifier.weight(1f)) {
                            Text(a.account_name, style = MaterialTheme.typography.titleSmall)
                            if (a.bank_name != null) {
                                Text(
                                    a.bank_name,
                                    style = MaterialTheme.typography.bodySmall,
                                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                                )
                            }
                        }
                        Text(
                            Formatters.idr(a.currentBalanceDecimal()),
                            style = MaterialTheme.typography.labelMedium,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                        )
                    }
                    Spacer(Modifier.height(6.dp))
                }
                if (targetId != null) {
                    val target = activeAccounts.firstOrNull { it.id == targetId }
                    Spacer(Modifier.height(8.dp))
                    Text(
                        "Preview: ${Formatters.idr(balance)} will be moved to \"${target?.account_name ?: ""}\".",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                    )
                }
            }

            Spacer(Modifier.height(24.dp))
            MyMoneyButton(
                onClick = { onConfirm(targetId) },
                modifier = Modifier.fillMaxWidth(),
                enabled = !busy && (balance == BigDecimal.ZERO || targetId != null),
            ) {
                Text(if (busy) "Processing…" else "Deactivate")
            }
            Spacer(Modifier.height(8.dp))
            TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) { Text("Cancel") }
        }
    }
}

@Composable
private fun AccountRow(acc: AccountResponse, onEdit: () -> Unit, onDeactivate: () -> Unit) {
    MyMoneyCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(acc.account_name, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold)
                if (acc.bank_name != null) {
                    Text(acc.bank_name, style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(
                    Formatters.idr(acc.currentBalanceDecimal()),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.Bold,
                )
                Text(
                    "net ${Formatters.idr(acc.netBalanceDecimal())}",
                    style = MaterialTheme.typography.labelSmall,
                    color = if (acc.netBalanceDecimal() >= BigDecimal.ZERO) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.error,
                )
            }
            IconButton(onClick = onEdit) {
                Icon(Icons.Filled.Edit, contentDescription = "Edit", tint = MaterialTheme.colorScheme.outline)
            }
            IconButton(onClick = onDeactivate) {
                Icon(
                    Icons.Outlined.PowerSettingsNew,
                    contentDescription = "Deactivate",
                    tint = MaterialTheme.colorScheme.outline,
                )
            }
        }
    }
}

private fun AccountResponse.currentBalanceDecimal(): BigDecimal =
    runCatching { BigDecimal(current_balance) }.getOrDefault(BigDecimal.ZERO)

private fun AccountResponse.initialBalanceDecimal(): BigDecimal =
    runCatching { BigDecimal(initial_balance) }.getOrDefault(BigDecimal.ZERO)

private fun AccountResponse.netBalanceDecimal(): BigDecimal =
    runCatching { BigDecimal(net_balance) }.getOrDefault(BigDecimal.ZERO)

@Composable
private fun AccountEditDialog(
    title: String,
    initialName: String,
    initialBank: String,
    showBalance: Boolean,
    onDismiss: () -> Unit,
    onSave: (String, String?, BigDecimal) -> Unit,
) {
    var name by remember { mutableStateOf(initialName) }
    var bank by remember { mutableStateOf(initialBank) }
    var balanceText by remember { mutableStateOf("") }
    var error by remember { mutableStateOf<String?>(null) }
    val bankFocus = remember { FocusRequester() }
    val balanceFocus = remember { FocusRequester() }
    val focusManager = LocalFocusManager.current

    fun save() {
        if (name.isBlank()) {
            error = "Account name is required"
            return
        }
        val balance = if (showBalance) {
            runCatching { BigDecimal(balanceText) }.getOrNull() ?: run {
                error = "Enter a valid balance"
                return
            }
        } else BigDecimal.ZERO
        onSave(name, bank, balance)
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Account name") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Text,
                        imeAction = ImeAction.Next,
                    ),
                    keyboardActions = KeyboardActions(onNext = { bankFocus.requestFocus() }),
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = bank,
                    onValueChange = { bank = it },
                    label = { Text("Bank (optional)") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(
                        keyboardType = KeyboardType.Text,
                        imeAction = if (showBalance) ImeAction.Next else ImeAction.Done,
                    ),
                    keyboardActions = KeyboardActions(
                        onNext = { balanceFocus.requestFocus() },
                        onDone = { focusManager.clearFocus(); save() },
                    ),
                    modifier = Modifier.fillMaxWidth().focusRequester(bankFocus),
                )
                if (showBalance) {
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = balanceText,
                        onValueChange = { balanceText = it.filter { c -> c.isDigit() || c == '.' } },
                        label = { Text("Initial balance (IDR)") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(
                            keyboardType = KeyboardType.Decimal,
                            imeAction = ImeAction.Done,
                        ),
                        keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus(); save() }),
                        modifier = Modifier.fillMaxWidth().focusRequester(balanceFocus),
                    )
                }
                if (error != null) {
                    Spacer(Modifier.height(8.dp))
                    Text(error!!, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            TextButton(onClick = { save() }) { Text("Save") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}
