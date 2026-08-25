package id.my.mymoney.ui.transactions

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilterChip
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.rememberDatePickerState
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.data.model.AccountResponse
import id.my.mymoney.data.model.CategoryResponse
import id.my.mymoney.ui.receipt.ReceiptItem
import id.my.mymoney.ui.receipt.ReceiptParser
import id.my.mymoney.ui.theme.ExpenseRed
import id.my.mymoney.ui.theme.IncomeGreen
import id.my.mymoney.ui.theme.MoneyMedium
import id.my.mymoney.util.Formatters
import java.math.BigDecimal
import java.time.Instant
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset
import java.time.format.DateTimeFormatter

/**
 * Satu-satunya layar New Transaction (multi-item) — dipakai oleh tombol "+",
 * edit, dan alur kamera (OCR prefill via [TransactionFormViewModel]).
 * Konsep CRUD item = form New from Receipt yang lama.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun TransactionFormScreen(
    txId: String?,
    onDone: () -> Unit,
    initialType: String? = null,
    viewModel: TransactionFormViewModel = viewModel(factory = TransactionFormViewModel.Factory),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val isEdit = txId != null

    // State lokal (bukan items/merchant/type — itu di VM).
    var categoryId by rememberSaveable { mutableStateOf<String?>(null) }
    var accountId by rememberSaveable { mutableStateOf<String?>(null) }
    var note by rememberSaveable { mutableStateOf("") }
    var dateMillis by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var localError by remember { mutableStateOf<String?>(null) }

    LaunchedEffect(Unit) {
        viewModel.loadOptions {
            val editing = viewModel.uiState.value.editing
            if (editing != null) {
                categoryId = editing.category_id
                accountId = editing.account_id
                note = editing.note ?: ""
                dateMillis = runCatching {
                    OffsetDateTime.parse(editing.transaction_date).toInstant().toEpochMilli()
                }.getOrDefault(System.currentTimeMillis())
            }
        }
        if (isEdit) {
            viewModel.loadTransaction(txId) { editing ->
                categoryId = editing.category_id
                accountId = editing.account_id
                note = editing.note ?: ""
                dateMillis = runCatching {
                    OffsetDateTime.parse(editing.transaction_date).toInstant().toEpochMilli()
                }.getOrDefault(System.currentTimeMillis())
            }
        } else {
            // Kamera → form: isi items/merchant/type dari hasil OCR (jika ada).
            viewModel.applyPendingReceipt { pending ->
                categoryId = pending.suggestedCategoryId
                accountId = pending.suggestedAccountId
                // Tanggal dari nota (dd-MM-yyyy) → dateMillis, bila tercetak.
                pending.transactionDate?.let { raw ->
                    dateMillis = runCatching {
                        val date = LocalDate.parse(
                            raw,
                            DateTimeFormatter.ofPattern("dd-MM-yyyy"),
                        )
                        date.atStartOfDay(ZoneId.systemDefault()).toInstant().toEpochMilli()
                    }.getOrDefault(dateMillis)
                }
            }
            // Preselect dari quick action (Catat Pengeluaran/Pemasukan).
            if (initialType != null) viewModel.setType(initialType)
        }
    }

    var showDatePicker by remember { mutableStateOf(false) }
    if (showDatePicker) {
        val pickerState = rememberDatePickerState(initialSelectedDateMillis = dateMillis)
        DatePickerDialog(
            onDismissRequest = { showDatePicker = false },
            confirmButton = {
                TextButton(onClick = {
                    pickerState.selectedDateMillis?.let { dateMillis = it }
                    showDatePicker = false
                }) { Text("OK") }
            },
            dismissButton = {
                TextButton(onClick = { showDatePicker = false }) { Text("Cancel") }
            },
        ) {
            DatePicker(state = pickerState)
        }
    }

    val selectedDate: LocalDate = remember(dateMillis) {
        Instant.ofEpochMilli(dateMillis).atZone(ZoneId.systemDefault()).toLocalDate()
    }

    fun save() {
        if (state.saving) return
        localError = null
        val validItems = state.items.filter {
            it.name.isNotBlank() && (ReceiptParser.parsePriceToDecimal(it.price) ?: BigDecimal.ZERO) > BigDecimal.ZERO
        }
        if (validItems.isEmpty()) {
            localError = "Tambahkan minimal satu item dengan nama dan harga valid"
            return
        }
        val totalAmount = validItems.fold(BigDecimal.ZERO) { acc, item -> acc + item.lineTotal }
        if (totalAmount <= BigDecimal.ZERO) {
            localError = "Total harus lebih dari 0"
            return
        }
        val cat = categoryId
        val acc = accountId
        if (cat == null || acc == null) {
            localError = "Pilih kategori dan akun"
            return
        }
        val dateTime: OffsetDateTime =
            selectedDate.atTime(12, 0).atZone(ZoneId.systemDefault()).toOffsetDateTime()
        val callback: (Boolean, String?) -> Unit = { ok, err ->
            if (ok) onDone() else localError = err
        }
        if (isEdit && viewModel.uiState.value.editing != null) {
            viewModel.update(
                tx = viewModel.uiState.value.editing!!,
                type = state.type,
                totalAmount = totalAmount,
                categoryId = cat,
                accountId = acc,
                merchant = state.merchant,
                note = note,
                transactionDate = dateTime,
                items = validItems,
                onDone = callback,
            )
        } else {
            viewModel.create(
                type = state.type,
                totalAmount = totalAmount,
                categoryId = cat,
                accountId = acc,
                merchant = state.merchant,
                note = note,
                transactionDate = dateTime,
                items = validItems,
                onDone = callback,
            )
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text(if (isEdit) "Edit transaction" else "New transaction") }) },
    ) { innerPadding ->
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // ── Tipe income/expense ──
            item {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(
                        selected = state.type == "expense",
                        onClick = { viewModel.setType("expense") },
                        label = { Text("Expense") },
                    )
                    FilterChip(
                        selected = state.type == "income",
                        onClick = { viewModel.setType("income") },
                        label = { Text("Income") },
                    )
                }
            }

            // ── Merchant ──
            item {
                OutlinedTextField(
                    value = state.merchant,
                    onValueChange = viewModel::setMerchant,
                    label = { Text("Merchant (nama toko)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            // ── Items ──
            item {
                Text(
                    "Items (${state.items.size})",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                )
            }
            itemsIndexed(state.items) { index, item ->
                FormItemRow(
                    item = item,
                    onUpdate = { viewModel.updateItem(index, it) },
                    onRemove = { viewModel.removeItem(index) },
                )
            }
            item {
                TextButton(onClick = { viewModel.addItem() }) {
                    Icon(Icons.Filled.Add, contentDescription = null)
                    Spacer(Modifier.width(4.dp))
                    Text("Add item")
                }
            }

            // ── Kategori & akun ──
            item {
                CategoryDropdown(
                    selectedId = categoryId,
                    categories = state.categories.filter { it.type == state.type },
                    onSelect = { categoryId = it },
                )
            }
            item {
                AccountDropdown(
                    selectedId = accountId,
                    accounts = state.accounts,
                    onSelect = { accountId = it },
                )
            }

            // ── Catatan ──
            item {
                OutlinedTextField(
                    value = note,
                    onValueChange = { note = it },
                    label = { Text("Note (optional)") },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            // ── Tanggal ──
            item {
                OutlinedTextField(
                    value = selectedDate.toString(),
                    onValueChange = {},
                    label = { Text("Date") },
                    readOnly = true,
                    trailingIcon = { TextButton(onClick = { showDatePicker = true }) { Text("Pick") } },
                    modifier = Modifier.fillMaxWidth(),
                )
            }

            // ── Total ──
            item {
                Row(modifier = Modifier.fillMaxWidth()) {
                    Text(
                        "Total",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        modifier = Modifier.weight(1f),
                    )
                    Text(
                        Formatters.idr(viewModel.total),
                        style = MoneyMedium,
                        color = if (state.type == "expense") ExpenseRed else IncomeGreen,
                    )
                }
            }

            // ── Simpan ──
            item {
                val message = localError ?: state.error
                if (message != null) {
                    Text(
                        message,
                        color = MaterialTheme.colorScheme.error,
                        style = MaterialTheme.typography.bodySmall,
                    )
                    Spacer(Modifier.height(8.dp))
                }
                Button(
                    onClick = { save() },
                    enabled = !state.saving,
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    if (state.saving) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            color = MaterialTheme.colorScheme.onPrimary,
                        )
                    } else {
                        Text(if (isEdit) "Save changes" else "Save transaction")
                    }
                }
            }
            item {
                Spacer(Modifier.height(24.dp))
            }
        }
    }
}

@Composable
private fun FormItemRow(
    item: ReceiptItem,
    onUpdate: (ReceiptItem) -> Unit,
    onRemove: () -> Unit,
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(12.dp)) {
            Row(verticalAlignment = Alignment.Top) {
                OutlinedTextField(
                    value = item.name,
                    onValueChange = { onUpdate(item.copy(name = it)) },
                    label = { Text("Item name") },
                    modifier = Modifier.weight(1f),
                    maxLines = 2,
                )
                IconButton(onClick = onRemove) {
                    Icon(
                        Icons.Outlined.Delete,
                        contentDescription = "Remove",
                        tint = MaterialTheme.colorScheme.error,
                    )
                }
            }
            Spacer(Modifier.height(8.dp))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(
                    value = item.qty,
                    onValueChange = { onUpdate(item.copy(qty = it)) },
                    label = { Text("Qty") },
                    modifier = Modifier.weight(1f),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                )
                OutlinedTextField(
                    value = item.price,
                    onValueChange = { onUpdate(item.copy(price = it)) },
                    label = { Text("Price") },
                    modifier = Modifier.weight(2f),
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Decimal),
                )
            }
            Spacer(Modifier.height(4.dp))
            Text(
                "= ${Formatters.idr(item.lineTotal)}",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CategoryDropdown(
    selectedId: String?,
    categories: List<CategoryResponse>,
    onSelect: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedName = categories.firstOrNull { it.id == selectedId }?.name ?: "Select category"
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
    ) {
        OutlinedTextField(
            value = selectedName,
            onValueChange = {},
            readOnly = true,
            label = { Text("Category") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier
                .fillMaxWidth()
                .menuAnchor(),
        )
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            if (categories.isEmpty()) {
                DropdownMenuItem(text = { Text("No categories for this type") }, onClick = { expanded = false })
            }
            categories.forEach { cat ->
                DropdownMenuItem(
                    text = { Text(cat.name) },
                    onClick = {
                        onSelect(cat.id)
                        expanded = false
                    },
                )
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun AccountDropdown(
    selectedId: String?,
    accounts: List<AccountResponse>,
    onSelect: (String) -> Unit,
) {
    var expanded by remember { mutableStateOf(false) }
    val selectedName = accounts.firstOrNull { it.id == selectedId }?.account_name ?: "Select account"
    ExposedDropdownMenuBox(
        expanded = expanded,
        onExpandedChange = { expanded = it },
    ) {
        OutlinedTextField(
            value = selectedName,
            onValueChange = {},
            readOnly = true,
            label = { Text("Account") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier
                .fillMaxWidth()
                .menuAnchor(),
        )
        ExposedDropdownMenu(
            expanded = expanded,
            onDismissRequest = { expanded = false },
        ) {
            if (accounts.isEmpty()) {
                DropdownMenuItem(text = { Text("No accounts — add one in Accounts tab") }, onClick = { expanded = false })
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
