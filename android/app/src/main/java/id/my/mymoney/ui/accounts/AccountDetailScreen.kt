package id.my.mymoney.ui.accounts

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
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
import id.my.mymoney.data.model.TransactionResponse
import id.my.mymoney.ui.components.EmptyState
import id.my.mymoney.ui.components.ErrorView
import id.my.mymoney.ui.components.LoadingView
import id.my.mymoney.ui.theme.ExpenseRed
import id.my.mymoney.ui.theme.IncomeGreen
import id.my.mymoney.ui.theme.MoneyMedium
import id.my.mymoney.util.Formatters
import java.math.BigDecimal

/**
 * Account detail (TASK 4.1): header + transaction history + edit +
 * deactivate via bottom sheet (DESIGN.md §8.5, ARCHITECTURE.md §4.4).
 *
 * Accounts are NEVER deleted — only deactivated. When the account has a
 * non-zero balance the user MUST pick a target account; the balance preview
 * is shown and confirm is disabled until a target is chosen (US-22).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AccountDetailScreen(
    accountId: String,
    onDone: () -> Unit,
    viewModel: AccountDetailViewModel = viewModel(factory = AccountDetailViewModel.Factory),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var showEdit by remember { mutableStateOf(false) }
    var showDeactivate by remember { mutableStateOf(false) }

    LaunchedEffect(accountId) { viewModel.load(accountId) }

    val acc = state.account

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(acc?.account_name ?: "Account") },
                navigationIcon = {
                    IconButton(onClick = onDone) {
                        Icon(Icons.AutoMirrored.Filled.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
    ) { innerPadding ->
        when {
            state.loading && acc == null -> LoadingView()
            state.error != null && acc == null ->
                ErrorView(state.error, onRetry = { viewModel.load(accountId) })
            acc == null -> EmptyState("Account not found")
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(innerPadding),
                    contentPadding = PaddingValues(16.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    item(key = "header") { AccountHeaderCard(acc) }
                    if (acc.is_active) {
                        item(key = "actions") {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.spacedBy(8.dp),
                            ) {
                                OutlinedButton(
                                    onClick = { showEdit = true },
                                    modifier = Modifier.weight(1f),
                                ) { Text("Edit") }
                                Button(
                                    onClick = { showDeactivate = true },
                                    modifier = Modifier.weight(1f),
                                    colors = ButtonDefaults.buttonColors(
                                        containerColor = MaterialTheme.colorScheme.error,
                                        contentColor = MaterialTheme.colorScheme.onError,
                                    ),
                                ) { Text("Nonaktifkan") }
                            }
                        }
                    }
                    item(key = "history_header") {
                        Text(
                            "Riwayat transaksi",
                            style = MaterialTheme.typography.titleSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            modifier = Modifier.padding(top = 16.dp, bottom = 4.dp),
                        )
                    }
                    if (state.transactions.isEmpty()) {
                        item(key = "history_empty") {
                            Text(
                                "Belum ada transaksi untuk akun ini.",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                                modifier = Modifier.padding(vertical = 16.dp),
                            )
                        }
                    } else {
                        items(state.transactions, key = { it.id }) { tx ->
                            TransactionRow(tx)
                        }
                    }
                }
            }
        }
    }

    if (showEdit && acc != null) {
        AccountDetailEditDialog(
            acc = acc,
            onDismiss = { showEdit = false },
            onSave = { name, bank ->
                viewModel.update(acc, name, bank) { ok, _ -> if (ok) showEdit = false }
            },
        )
    }

    if (showDeactivate && acc != null) {
        DeactivateAccountSheet(
            acc = acc,
            activeAccounts = state.activeAccounts.filter { it.id != acc.id },
            busy = state.busy,
            onDismiss = { showDeactivate = false },
            onConfirm = { targetId ->
                viewModel.deactivate(acc, targetId) { ok, _ ->
                    if (ok) {
                        showDeactivate = false
                        onDone()
                    }
                }
            },
        )
    }
}

/**
 * Header card (TASK 4.1): name (Manrope Medium), bank caption, computed
 * balance in IBM Plex Mono on-surface — NOT income/expense colors. Inactive
 * accounts get a "Nonaktif" label and are otherwise read-only.
 */
@Composable
private fun AccountHeaderCard(acc: AccountResponse) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                acc.account_name,
                style = MaterialTheme.typography.bodyLarge,
                fontWeight = FontWeight.Medium,
            )
            Text(
                acc.bank_name ?: "Cash",
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            Spacer(Modifier.height(4.dp))
            Text(
                Formatters.idr(acc.currentBalanceDecimal),
                style = MaterialTheme.typography.titleLarge,
                fontFamily = MoneyMedium.fontFamily,
                fontWeight = FontWeight.Normal,
                color = MaterialTheme.colorScheme.onSurface,
            )
            Text(
                "net ${Formatters.idr(acc.netBalanceDecimal)}",
                style = MaterialTheme.typography.labelSmall,
                color = if (acc.netBalanceDecimal >= BigDecimal.ZERO)
                    MaterialTheme.colorScheme.onSurfaceVariant
                else MaterialTheme.colorScheme.error,
            )
            if (!acc.is_active) {
                Spacer(Modifier.height(8.dp))
                Text(
                    "Nonaktif",
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.error,
                )
            }
        }
    }
}

/**
 * Transaction row — mirrors TransactionsScreen.TransactionCard: title
 * (merchant/note), date · items caption, amount signed +/- in expense/income
 * colors. No delete here (history is read-only).
 */
@Composable
private fun TransactionRow(tx: TransactionResponse) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(
            containerColor = MaterialTheme.colorScheme.surfaceVariant,
        ),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    tx.merchant ?: tx.note ?: (if (tx.isExpense) "Expense" else "Income"),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                )
                Spacer(Modifier.height(2.dp))
                Text(
                    "${Formatters.date(tx.transaction_date)} · " +
                        (if (tx.items.isEmpty()) "—" else "${tx.items.size} item(s)"),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            val color = if (tx.isExpense) ExpenseRed else IncomeGreen
            val sign = if (tx.isExpense) "-" else "+"
            Text(
                "$sign${Formatters.idr(tx.totalAmountDecimal)}",
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.Bold,
                color = color,
            )
        }
    }
}

/** Edit dialog (TASK 4.2): name required, bank optional. Balance never editable. */
@Composable
private fun AccountDetailEditDialog(
    acc: AccountResponse,
    onDismiss: () -> Unit,
    onSave: (String, String?) -> Unit,
) {
    var name by remember { mutableStateOf(acc.account_name) }
    var bank by remember { mutableStateOf(acc.bank_name ?: "") }
    var error by remember { mutableStateOf<String?>(null) }
    val bankFocus = remember { FocusRequester() }
    val focusManager = LocalFocusManager.current

    fun save() {
        if (name.isBlank()) {
            error = "Account name is required"
            return
        }
        onSave(name.trim(), bank)
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Edit account") },
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
                        imeAction = ImeAction.Done,
                    ),
                    keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus(); save() }),
                    modifier = Modifier.fillMaxWidth().focusRequester(bankFocus),
                )
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

/**
 * Deactivate bottom sheet (DESIGN.md §8.5 — elevation 3, NOT an AlertDialog).
 *
 * balance == 0  → simple confirmation.
 * balance != 0  → target account dropdown (active accounts, excluding self) +
 *                 transfer preview; confirm enabled ONLY when a target is
 *                 chosen (US-22). ARCHITECTURE.md §4.4 does the transfer.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun DeactivateAccountSheet(
    acc: AccountResponse,
    activeAccounts: List<AccountResponse>,
    busy: Boolean,
    onDismiss: () -> Unit,
    onConfirm: (String?) -> Unit,
) {
    val sheetState = rememberModalBottomSheetState()
    val balance = acc.currentBalanceDecimal
    var targetId by remember { mutableStateOf<String?>(null) }
    val target = activeAccounts.find { it.id == targetId }

    ModalBottomSheet(onDismissRequest = onDismiss, sheetState = sheetState) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp).padding(bottom = 24.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            Text("Nonaktifkan akun", style = MaterialTheme.typography.titleLarge)

            if (balance == BigDecimal.ZERO) {
                Text(
                    "Akun \"${acc.account_name}\" tidak memiliki saldo dan akan langsung dinonaktifkan.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                Button(
                    onClick = { onConfirm(null) },
                    enabled = !busy,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                        contentColor = MaterialTheme.colorScheme.onError,
                    ),
                ) { Text("Nonaktifkan") }
            } else {
                Text(
                    "Akun ini memiliki saldo ${Formatters.idr(balance)}. " +
                        "Pilih akun tujuan untuk memindahkan saldo sebelum dinonaktifkan.",
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
                TargetAccountDropdown(
                    accounts = activeAccounts,
                    selectedId = targetId,
                    onSelect = { targetId = it },
                )
                if (target != null) {
                    Text(
                        "${Formatters.idr(balance)} akan dipindahkan ke ${target.account_name}",
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.onSurface,
                    )
                }
                Button(
                    onClick = { onConfirm(targetId) },
                    enabled = targetId != null && !busy,
                    modifier = Modifier.fillMaxWidth(),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = MaterialTheme.colorScheme.error,
                        contentColor = MaterialTheme.colorScheme.onError,
                    ),
                ) { Text("Nonaktifkan & pindahkan saldo") }
            }
            TextButton(onClick = onDismiss, modifier = Modifier.fillMaxWidth()) { Text("Batal") }
        }
    }
}

/** Target-account dropdown for the transfer (active accounts, excluding self). */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun TargetAccountDropdown(
    accounts: List<AccountResponse>,
    selectedId: String?,
    onSelect: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val selected = accounts.find { it.id == selectedId }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }) {
        OutlinedTextField(
            value = selected?.account_name ?: "",
            onValueChange = {},
            readOnly = true,
            label = { Text("Target account") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
            if (accounts.isEmpty()) {
                DropdownMenuItem(
                    text = { Text("No other active accounts — add one in Accounts tab") },
                    onClick = { expanded = false },
                )
            }
            accounts.forEach { acc ->
                DropdownMenuItem(
                    text = { Text(acc.account_name) },
                    onClick = {
                        onSelect(acc.id)
                        expanded = false
                    },
                )
            }
        }
    }
}
