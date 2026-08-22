package com.mymoney.app.ui.screens.account

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.Add
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import com.mymoney.app.ui.components.MoneyText
import com.mymoney.app.ui.theme.MyMoneyTypography

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun AccountScreen(
    viewModel: AccountViewModel = hiltViewModel(),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var showAddDialog by remember { mutableStateOf(false) }

    // Deactivation Bottom Sheet
    if (state.deactivatingAccount != null) {
        val sheetState = rememberModalBottomSheetState()
        ModalBottomSheet(
            onDismissRequest = { viewModel.dismissDeactivate() },
            sheetState = sheetState
        ) {
            Column(Modifier.padding(24.dp).padding(bottom = 24.dp)) {
                Text("Pindah Saldo", style = MyMoneyTypography.headlineMedium)
                Spacer(Modifier.height(8.dp))
                Text("Pilih akun tujuan untuk saldo yang tersisa sebelum dinonaktifkan.")
                Spacer(Modifier.height(16.dp))
                
                val activeAccounts = state.accounts.filter { it.isActive && it.id != state.deactivatingAccount!!.id }
                activeAccounts.forEach { acc ->
                    Text(
                        text = acc.accountName,
                        style = MyMoneyTypography.titleLarge,
                        modifier = Modifier
                            .fillMaxWidth()
                            .clickable { viewModel.confirmDeactivate(state.deactivatingAccount!!.id, acc.id) }
                            .padding(vertical = 12.dp)
                    )
                    HorizontalDivider()
                }
            }
        }
    }

    if (showAddDialog) {
        var name by remember { mutableStateOf("") }
        var initialBalance by remember { mutableStateOf("") }
        
        AlertDialog(
            onDismissRequest = { showAddDialog = false },
            title = { Text("Tambah Akun") },
            text = {
                Column {
                    OutlinedTextField(
                        value = name, onValueChange = { name = it },
                        label = { Text("Nama Akun (mis. BCA, Tunai)") }, singleLine = true
                    )
                    Spacer(Modifier.height(8.dp))
                    OutlinedTextField(
                        value = initialBalance, onValueChange = { initialBalance = it },
                        label = { Text("Saldo Awal (Opsional)") }, singleLine = true
                    )
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        viewModel.createAccount(name, null, initialBalance.toDoubleOrNull() ?: 0.0)
                        showAddDialog = false
                    },
                    enabled = name.isNotBlank()
                ) { Text("Simpan") }
            },
            dismissButton = {
                TextButton(onClick = { showAddDialog = false }) { Text("Batal") }
            }
        )
    }

    Scaffold(
        floatingActionButton = {
            FloatingActionButton(onClick = { showAddDialog = true }) {
                Icon(Icons.Outlined.Add, contentDescription = "Tambah Akun")
            }
        }
    ) { padding ->
        if (state.isLoading && state.accounts.isEmpty()) {
            Box(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) { CircularProgressIndicator() }
            return@Scaffold
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(padding).padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            item {
                Spacer(Modifier.height(24.dp))
                Text("Daftar Akun", style = MyMoneyTypography.headlineLarge)
                Spacer(Modifier.height(16.dp))
            }

            items(state.accounts.filter { it.isActive }) { account ->
                Card(modifier = Modifier.fillMaxWidth()) {
                    Row(
                        Modifier.padding(16.dp),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        Column {
                            Text(account.accountName, style = MyMoneyTypography.titleMedium)
                            MoneyText(amount = account.currentBalance)
                        }
                        IconButton(onClick = { viewModel.requestDeactivate(account) }) {
                            Icon(Icons.Outlined.Delete, contentDescription = "Nonaktifkan", tint = MaterialTheme.colorScheme.error)
                        }
                    }
                }
            }
            item { Spacer(Modifier.height(80.dp)) }
        }
    }
}
