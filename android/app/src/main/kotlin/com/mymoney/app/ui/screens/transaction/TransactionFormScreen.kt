package com.mymoney.app.ui.screens.transaction

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowBack
import androidx.compose.material.icons.outlined.ArrowDropDown
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.PickVisualMediaRequest
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.mymoney.app.data.model.TransactionItemRequest
import com.mymoney.app.ui.theme.MyMoneyTypography
import java.time.LocalDateTime
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TransactionFormScreen(
    editId: String? = null,
    onSaved: () -> Unit,
    onCancel: () -> Unit,
    viewModel: TransactionFormViewModel = hiltViewModel(),
) {
    val state by viewModel.state.collectAsStateWithLifecycle()
    
    LaunchedEffect(state.isSaved) {
        if (state.isSaved) onSaved()
    }

    var type by remember { mutableStateOf("expense") }
    var amountStr by remember { mutableStateOf("") }
    var categoryId by remember { mutableStateOf("") }
    var accountId by remember { mutableStateOf("") }
    var merchant by remember { mutableStateOf("") }
    var note by remember { mutableStateOf("") }
    var items by remember { mutableStateOf(emptyList<TransactionItemRequest>()) }
    var showReviewWarning by remember { mutableStateOf(false) }

    var expandedCategory by remember { mutableStateOf(false) }
    var expandedAccount by remember { mutableStateOf(false) }
    
    val context = LocalContext.current
    val photoPickerLauncher = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.PickVisualMedia(),
        onResult = { uri ->
            if (uri != null) {
                viewModel.scanReceipt(uri, context)
            }
        }
    )

    LaunchedEffect(state.parsedReceipt) {
        state.parsedReceipt?.let { resp ->
            amountStr = resp.parsed.total.toInt().toString()
            merchant = resp.parsed.merchant ?: ""
            items = resp.parsed.items
            showReviewWarning = resp.reviewRequired
            viewModel.clearParsedReceipt()
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text(if (editId == null) "Catat Transaksi" else "Edit Transaksi", style = MyMoneyTypography.headlineMedium) },
                navigationIcon = {
                    IconButton(onClick = onCancel) { Icon(Icons.AutoMirrored.Outlined.ArrowBack, contentDescription = "Batal") }
                }
            )
        }
    ) { padding ->
        if (state.isLoading || state.isScanning) {
            Box(Modifier.fillMaxSize(), contentAlignment = androidx.compose.ui.Alignment.Center) { 
                Column(horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally) {
                    CircularProgressIndicator()
                    if (state.isScanning) {
                        Spacer(Modifier.height(16.dp))
                        Text("Memproses Nota dengan AI...")
                    }
                }
            }
            return@Scaffold
        }

        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .padding(horizontal = 16.dp)
                .verticalScroll(rememberScrollState()),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            if (showReviewWarning) {
                Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
                    Text(
                        text = "⚠️ Perhatian: Kualitas foto kurang baik atau nota sulit dibaca. Mohon periksa kembali rincian di bawah ini sebelum menyimpan.",
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        modifier = Modifier.padding(16.dp),
                        style = MaterialTheme.typography.bodyMedium
                    )
                }
            }

            Button(
                onClick = { photoPickerLauncher.launch(PickVisualMediaRequest(ActivityResultContracts.PickVisualMedia.ImageOnly)) },
                modifier = Modifier.fillMaxWidth()
            ) {
                Text("Scan Foto Nota")
            }

            // Type Toggle
            Row(Modifier.fillMaxWidth()) {
                FilterChip(
                    selected = type == "expense",
                    onClick = { type = "expense"; categoryId = "" },
                    label = { Text("Pengeluaran") },
                    modifier = Modifier.weight(1f)
                )
                Spacer(Modifier.width(8.dp))
                FilterChip(
                    selected = type == "income",
                    onClick = { type = "income"; categoryId = "" },
                    label = { Text("Pemasukan") },
                    modifier = Modifier.weight(1f)
                )
            }

            OutlinedTextField(
                value = amountStr, onValueChange = { amountStr = it },
                label = { Text("Nominal (Rp)") },
                keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                modifier = Modifier.fillMaxWidth(),
                singleLine = true
            )

            // Category Dropdown
            ExposedDropdownMenuBox(
                expanded = expandedCategory,
                onExpandedChange = { expandedCategory = !expandedCategory }
            ) {
                val selectedCategory = state.categories.find { it.id == categoryId }?.name ?: "Pilih Kategori"
                OutlinedTextField(
                    value = selectedCategory, onValueChange = {},
                    readOnly = true, label = { Text("Kategori") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expandedCategory) },
                    modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth()
                )
                ExposedDropdownMenu(
                    expanded = expandedCategory,
                    onDismissRequest = { expandedCategory = false }
                ) {
                    state.categories.filter { it.type == type }.forEach { cat ->
                        DropdownMenuItem(
                            text = { Text(cat.name) },
                            onClick = { categoryId = cat.id; expandedCategory = false }
                        )
                    }
                }
            }

            // Account Dropdown
            ExposedDropdownMenuBox(
                expanded = expandedAccount,
                onExpandedChange = { expandedAccount = !expandedAccount }
            ) {
                val selectedAccount = state.accounts.find { it.id == accountId }?.accountName ?: "Pilih Akun"
                OutlinedTextField(
                    value = selectedAccount, onValueChange = {},
                    readOnly = true, label = { Text("Akun") },
                    trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expandedAccount) },
                    modifier = Modifier.menuAnchor(MenuAnchorType.PrimaryNotEditable).fillMaxWidth()
                )
                ExposedDropdownMenu(
                    expanded = expandedAccount,
                    onDismissRequest = { expandedAccount = false }
                ) {
                    state.accounts.forEach { acc ->
                        DropdownMenuItem(
                            text = { Text(acc.accountName) },
                            onClick = { accountId = acc.id; expandedAccount = false }
                        )
                    }
                }
            }

            OutlinedTextField(
                value = merchant, onValueChange = { merchant = it },
                label = { Text("Nama Toko/Merchant (Opsional)") },
                modifier = Modifier.fillMaxWidth(), singleLine = true
            )

            OutlinedTextField(
                value = note, onValueChange = { note = it },
                label = { Text("Catatan (Opsional)") },
                modifier = Modifier.fillMaxWidth()
            )

            if (items.isNotEmpty()) {
                Text("Rincian Item", style = MaterialTheme.typography.titleMedium, modifier = Modifier.padding(top = 8.dp))
                items.forEachIndexed { index, item ->
                    Card(modifier = Modifier.fillMaxWidth()) {
                        Row(modifier = Modifier.padding(16.dp).fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                            Column {
                                Text(item.name, style = MaterialTheme.typography.bodyLarge)
                                Text("${item.qty} x Rp${item.price.toInt()}", style = MaterialTheme.typography.bodyMedium)
                            }
                            Text("Rp${(item.qty * item.price).toInt()}", style = MaterialTheme.typography.titleMedium)
                        }
                    }
                }
            }

            Spacer(Modifier.height(16.dp))
            Button(
                onClick = {
                    val amount = amountStr.toDoubleOrNull() ?: 0.0
                    val dt = LocalDateTime.now().atZone(ZoneOffset.UTC).format(DateTimeFormatter.ISO_INSTANT)
                    viewModel.saveTransaction(type, amount, categoryId, accountId, merchant, note, dt, items)
                },
                enabled = amountStr.isNotBlank() && categoryId.isNotBlank() && accountId.isNotBlank(),
                modifier = Modifier.fillMaxWidth().height(48.dp)
            ) {
                Text("Simpan Transaksi")
            }
            
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
        }
    }
}
