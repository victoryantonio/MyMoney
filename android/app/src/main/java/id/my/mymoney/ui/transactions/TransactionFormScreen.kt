package id.my.mymoney.ui.transactions

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
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.DatePicker
import androidx.compose.material3.DatePickerDialog
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.ExposedDropdownMenuBox
import androidx.compose.material3.ExposedDropdownMenuDefaults
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.data.model.CategoryResponse
import id.my.mymoney.ui.theme.ExpenseRed
import id.my.mymoney.ui.theme.IncomeGreen
import java.math.BigDecimal
import java.time.Instant
import java.time.LocalDate
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.ZoneOffset

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

    // Preselect dari quick action (Catat Pengeluaran/Pemasukan). Saat edit,
    // nilai dari server menimpa di bawah. Perlu rememberSaveable key agar state
    // per instance route tidak bocor antar navigasi.
    var type by rememberSaveable(initialType) { mutableStateOf(initialType ?: "expense") }
    var amountText by rememberSaveable { mutableStateOf("") }
    var categoryId by rememberSaveable { mutableStateOf<String?>(null) }
    var accountId by rememberSaveable { mutableStateOf<String?>(null) }
    var merchant by rememberSaveable { mutableStateOf("") }
    var note by rememberSaveable { mutableStateOf("") }
    var dateMillis by remember { mutableLongStateOf(System.currentTimeMillis()) }
    var localError by remember { mutableStateOf<String?>(null) }
    val merchantFocus = remember { FocusRequester() }
    val noteFocus = remember { FocusRequester() }
    val focusManager = LocalFocusManager.current

    LaunchedEffect(Unit) {
        viewModel.loadOptions {
            val editing = viewModel.uiState.value.editing
            if (editing != null) {
                type = editing.type
                amountText = editing.totalAmountDecimal.stripTrailingZeros().toPlainString()
                categoryId = editing.category_id
                accountId = editing.account_id
                merchant = editing.merchant ?: ""
                note = editing.note ?: ""
                dateMillis = runCatching {
                    OffsetDateTime.parse(editing.transaction_date).toInstant().toEpochMilli()
                }.getOrDefault(System.currentTimeMillis())
            }
        }
        if (isEdit) {
            viewModel.loadTransaction(txId) { editing ->
                type = editing.type
                amountText = editing.totalAmountDecimal.stripTrailingZeros().toPlainString()
                categoryId = editing.category_id
                accountId = editing.account_id
                merchant = editing.merchant ?: ""
                note = editing.note ?: ""
                dateMillis = runCatching {
                    OffsetDateTime.parse(editing.transaction_date).toInstant().toEpochMilli()
                }.getOrDefault(System.currentTimeMillis())
            }
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
        val amount = runCatching { BigDecimal(amountText) }.getOrNull()
        if (amount == null || amount <= BigDecimal.ZERO) {
            localError = "Enter a valid amount"
            return
        }
        val cat = categoryId
        val acc = accountId
        if (cat == null || acc == null) {
            localError = "Pick a category and account"
            return
        }
        val dateTime: OffsetDateTime = selectedDate.atTime(12, 0).atZone(ZoneId.systemDefault()).toOffsetDateTime()
        val callback: (Boolean, String?) -> Unit = { ok, err ->
            if (ok) onDone() else localError = err
        }
        if (isEdit && viewModel.uiState.value.editing != null) {
            viewModel.update(
                tx = viewModel.uiState.value.editing!!,
                type = type,
                totalAmount = amount,
                categoryId = cat,
                accountId = acc,
                merchant = merchant,
                note = note,
                transactionDate = dateTime,
                onDone = callback,
            )
        } else {
            viewModel.create(
                type = type,
                totalAmount = amount,
                categoryId = cat,
                accountId = acc,
                merchant = merchant,
                note = note,
                transactionDate = dateTime,
                onDone = callback,
            )
        }
    }

    Scaffold(
        topBar = { TopAppBar(title = { Text(if (isEdit) "Edit transaction" else "New transaction") }) },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
        ) {
            // Type toggle
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(
                    selected = type == "expense",
                    onClick = { type = "expense" },
                    label = { Text("Expense") },
                )
                FilterChip(
                    selected = type == "income",
                    onClick = { type = "income" },
                    label = { Text("Income") },
                )
            }
            Spacer(Modifier.height(12.dp))

            OutlinedTextField(
                value = amountText,
                onValueChange = { amountText = it.filter { c -> c.isDigit() || c == '.' } },
                label = { Text("Amount (IDR)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Decimal,
                    imeAction = ImeAction.Next,
                ),
                keyboardActions = KeyboardActions(onNext = { merchantFocus.requestFocus() }),
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))

            CategoryDropdown(
                categories = state.categories.filter { it.type == type },
                selectedId = categoryId,
                onSelect = { categoryId = it },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))

            AccountDropdown(
                accounts = state.accounts,
                selectedId = accountId,
                onSelect = { accountId = it },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(12.dp))

            OutlinedTextField(
                value = merchant,
                onValueChange = { merchant = it },
                label = { Text("Merchant (optional)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Text,
                    imeAction = ImeAction.Next,
                ),
                keyboardActions = KeyboardActions(onNext = { noteFocus.requestFocus() }),
                modifier = Modifier.fillMaxWidth().focusRequester(merchantFocus),
            )
            Spacer(Modifier.height(12.dp))

            OutlinedTextField(
                value = note,
                onValueChange = { note = it },
                label = { Text("Note (optional)") },
                singleLine = true,
                keyboardOptions = KeyboardOptions(
                    keyboardType = KeyboardType.Text,
                    imeAction = ImeAction.Done,
                ),
                keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus(); save() }),
                modifier = Modifier.fillMaxWidth().focusRequester(noteFocus),
            )
            Spacer(Modifier.height(12.dp))

            OutlinedTextField(
                value = selectedDate.toString(),
                onValueChange = {},
                label = { Text("Date") },
                readOnly = true,
                trailingIcon = { TextButton(onClick = { showDatePicker = true }) { Text("Pick") } },
                modifier = Modifier.fillMaxWidth(),
            )
            Spacer(Modifier.height(20.dp))

            val message = localError ?: state.error
            if (message != null) {
                Text(message, color = MaterialTheme.colorScheme.error, style = MaterialTheme.typography.bodySmall)
                Spacer(Modifier.height(8.dp))
            }

            Button(
                onClick = { save() },
                enabled = !state.saving,
                modifier = Modifier.fillMaxWidth(),
            ) {
                if (state.saving) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        CircularProgressIndicator(modifier = Modifier.height(18.dp), strokeWidth = 2.dp)
                        Spacer(Modifier.padding(start = 8.dp))
                        Text("Saving…")
                    }
                } else {
                    Text(if (isEdit) "Save changes" else "Save transaction")
                }
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
private fun CategoryDropdown(
    categories: List<CategoryResponse>,
    selectedId: String?,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    val selected = categories.find { it.id == selectedId }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }, modifier = modifier) {
        OutlinedTextField(
            value = selected?.name ?: "",
            onValueChange = {},
            readOnly = true,
            label = { Text("Category") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
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
    accounts: List<id.my.mymoney.data.model.AccountResponse>,
    selectedId: String?,
    onSelect: (String) -> Unit,
    modifier: Modifier = Modifier,
) {
    var expanded by remember { mutableStateOf(false) }
    val selected = accounts.find { it.id == selectedId }
    ExposedDropdownMenuBox(expanded = expanded, onExpandedChange = { expanded = it }, modifier = modifier) {
        OutlinedTextField(
            value = selected?.account_name ?: "",
            onValueChange = {},
            readOnly = true,
            label = { Text("Account") },
            trailingIcon = { ExposedDropdownMenuDefaults.TrailingIcon(expanded = expanded) },
            modifier = Modifier.menuAnchor().fillMaxWidth(),
        )
        ExposedDropdownMenu(expanded = expanded, onDismissRequest = { expanded = false }) {
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
