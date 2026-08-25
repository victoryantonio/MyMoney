package id.my.mymoney.ui.accounts

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FloatingActionButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.data.model.AccountResponse
import id.my.mymoney.ui.components.EmptyState
import id.my.mymoney.ui.components.ErrorView
import id.my.mymoney.ui.components.LoadingView
import id.my.mymoney.util.Formatters
import java.math.BigDecimal

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AccountsScreen(viewModel: AccountsViewModel = viewModel(factory = AccountsViewModel.Factory)) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var editing by remember { mutableStateOf<AccountResponse?>(null) }
    var deleting by remember { mutableStateOf<AccountResponse?>(null) }
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
                        AccountRow(acc = acc, onEdit = { editing = acc }, onDelete = { deleting = acc })
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

    deleting?.let { acc ->
        AlertDialog(
            onDismissRequest = { deleting = null },
            title = { Text("Delete account") },
            text = { Text("Delete \"${acc.account_name}\"? Transactions are kept but this account will be hidden.") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.delete(acc) { ok, _ -> if (ok) deleting = null }
                }) { Text("Delete", color = MaterialTheme.colorScheme.error) }
            },
            dismissButton = {
                TextButton(onClick = { deleting = null }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun AccountRow(acc: AccountResponse, onEdit: () -> Unit, onDelete: () -> Unit) {
    Card(modifier = Modifier.fillMaxWidth()) {
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
                    "init ${Formatters.idr(acc.initialBalanceDecimal())}",
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            IconButton(onClick = onEdit) {
                Icon(Icons.Filled.Edit, contentDescription = "Edit", tint = MaterialTheme.colorScheme.outline)
            }
            IconButton(onClick = onDelete) {
                Icon(Icons.Filled.Delete, contentDescription = "Delete", tint = MaterialTheme.colorScheme.outline)
            }
        }
    }
}

private fun AccountResponse.currentBalanceDecimal(): BigDecimal =
    runCatching { BigDecimal(current_balance) }.getOrDefault(BigDecimal.ZERO)

private fun AccountResponse.initialBalanceDecimal(): BigDecimal =
    runCatching { BigDecimal(initial_balance) }.getOrDefault(BigDecimal.ZERO)

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
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                OutlinedTextField(
                    value = bank,
                    onValueChange = { bank = it },
                    label = { Text("Bank (optional)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                if (showBalance) {
                    Spacer(Modifier.height(12.dp))
                    OutlinedTextField(
                        value = balanceText,
                        onValueChange = { balanceText = it.filter { c -> c.isDigit() || c == '.' } },
                        label = { Text("Initial balance (IDR)") },
                        singleLine = true,
                        keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                        modifier = Modifier.fillMaxWidth(),
                    )
                }
                if (error != null) {
                    Spacer(Modifier.height(8.dp))
                    Text(error!!, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                }
            }
        },
        confirmButton = {
            TextButton(onClick = {
                if (name.isBlank()) {
                    error = "Account name is required"
                    return@TextButton
                }
                val balance = if (showBalance) {
                    runCatching { BigDecimal(balanceText) }.getOrNull() ?: run {
                        error = "Enter a valid balance"
                        return@TextButton
                    }
                } else BigDecimal.ZERO
                onSave(name, bank, balance)
            }) { Text("Save") }
        },
        dismissButton = {
            TextButton(onClick = onDismiss) { Text("Cancel") }
        },
    )
}
