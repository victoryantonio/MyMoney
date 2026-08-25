package id.my.mymoney.ui.receipt

import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.PhotoCamera
import androidx.compose.material.icons.outlined.PhotoLibrary
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.CircularProgressIndicator
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
import androidx.compose.material3.SnackbarHost
import androidx.compose.material3.SnackbarHostState
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.ui.components.MyMoneyCard
import id.my.mymoney.ui.theme.ExpenseRed
import id.my.mymoney.ui.theme.IncomeGreen
import id.my.mymoney.ui.theme.MoneyMedium
import id.my.mymoney.util.Formatters
import java.io.File
import java.math.BigDecimal

/**
 * Capture foto nota (kamera/galeri) → OCR (ML Kit) → item bisa diedit →
 * simpan sebagai SATU transaksi multi-item (DESIGN.md §8.6).
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReceiptCaptureScreen(
    onDone: () -> Unit,
    onOpenForm: (String, String) -> Unit,
    viewModel: ReceiptViewModel = viewModel(factory = ReceiptViewModel.Factory),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current

    var bitmapUri by remember { mutableStateOf<Uri?>(null) }
    var categoryId by remember { mutableStateOf<String?>(null) }
    var accountId by remember { mutableStateOf<String?>(null) }
    var showError by remember { mutableStateOf<String?>(null) }
    val snackbarHostState = remember { SnackbarHostState() }

    LaunchedEffect(Unit) { viewModel.loadOptions() }

    // Error state dari VM → snackbar.
    LaunchedEffect(state.error) {
        state.error?.let {
            snackbarHostState.showSnackbar(it)
            viewModel.setError(null)
        }
    }
    LaunchedEffect(showError) {
        showError?.let {
            snackbarHostState.showSnackbar(it)
            showError = null
        }
    }

    // Kamera → cache file → bitmap.
    val cameraLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.TakePicture(),
    ) { success ->
        if (success && bitmapUri != null) {
            val bmp = runCatching {
                context.contentResolver.openInputStream(bitmapUri!!)?.use { stream ->
                    android.graphics.BitmapFactory.decodeStream(stream)
                }
            }.getOrNull()
            if (bmp != null) viewModel.processBitmap(bmp)
        }
    }
    fun takePhoto() {
        val file = File(context.cacheDir, "receipts").apply { mkdirs() }
            .let { File(it, "receipt_${System.currentTimeMillis()}.jpg") }
        val uri = androidx.core.content.FileProvider.getUriForFile(
            context,
            "${context.packageName}.fileprovider",
            file,
        )
        bitmapUri = uri
        cameraLauncher.launch(uri)
    }

    // Galeri → uri.
    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent(),
    ) { uri ->
        if (uri != null) {
            bitmapUri = uri
            val bmp = runCatching {
                context.contentResolver.openInputStream(uri)?.use { stream ->
                    android.graphics.BitmapFactory.decodeStream(stream)
                }
            }.getOrNull()
            if (bmp != null) viewModel.processBitmap(bmp)
        }
    }

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("New from receipt") },
                navigationIcon = {
                    IconButton(onClick = onDone) {
                        Icon(Icons.Outlined.ArrowBack, contentDescription = "Back")
                    }
                },
            )
        },
        snackbarHost = { SnackbarHost(hostState = snackbarHostState) },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
        ) {
            // ── Tombol kamera / galeri ──
            if (state.ocrText.isBlank()) {
                MyMoneyCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier.fillMaxWidth().padding(24.dp),
                        horizontalAlignment = Alignment.CenterHorizontally,
                    ) {
                        if (state.processing) {
                            CircularProgressIndicator()
                            Spacer(Modifier.height(12.dp))
                            Text(
                                "Memindai nota…",
                                style = MaterialTheme.typography.bodyMedium,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                        } else {
                            Text(
                                "Foto nota untuk dijadikan transaksi",
                                style = MaterialTheme.typography.titleSmall,
                                fontWeight = FontWeight.SemiBold,
                            )
                            Spacer(Modifier.height(4.dp))
                            Text(
                                "Kamera atau galeri. Setiap item di nota menjadi line item dalam satu transaksi.",
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.onSurfaceVariant,
                            )
                            Spacer(Modifier.height(16.dp))
                            Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                                Button(onClick = { takePhoto() }) {
                                    Icon(Icons.Outlined.PhotoCamera, contentDescription = null)
                                    Spacer(Modifier.width(8.dp))
                                    Text("Camera")
                                }
                                TextButton(onClick = { galleryLauncher.launch("image/*") }) {
                                    Icon(Icons.Outlined.PhotoLibrary, contentDescription = null)
                                    Spacer(Modifier.width(8.dp))
                                    Text("Gallery")
                                }
                            }
                        }
                    }
                }
            }

            if (state.ocrText.isNotBlank()) {
                LazyColumn(
                    modifier = Modifier.weight(1f),
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

                    // ── Merchant (nama usaha, contoh: Mi Gacoan) ──
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
                        ReceiptItemRow(
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
                            categories = state.categories,
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
                        Button(
                            onClick = {
                                if (categoryId == null || accountId == null) {
                                    showError = "Pilih kategori dan akun"
                                    return@Button
                                }
                                viewModel.save(
                                    categoryId = categoryId!!,
                                    accountId = accountId!!,
                                    note = null,
                                ) { success, message ->
                                    if (success) onDone() else showError = message
                                }
                            },
                            enabled = !state.saving,
                            modifier = Modifier.fillMaxWidth(),
                        ) {
                            if (state.saving) {
                                CircularProgressIndicator(
                                    modifier = Modifier.size(18.dp),
                                    color = MaterialTheme.colorScheme.onPrimary,
                                )
                            } else {
                                Text("Save transaction")
                            }
                        }
                    }
                    item {
                        Spacer(Modifier.height(24.dp))
                    }
                }
            }
        }
    }
}

@Composable
private fun ReceiptItemRow(
    item: ReceiptItem,
    onUpdate: (ReceiptItem) -> Unit,
    onRemove: () -> Unit,
) {
    MyMoneyCard(modifier = Modifier.fillMaxWidth()) {
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
                )
                OutlinedTextField(
                    value = item.price,
                    onValueChange = { onUpdate(item.copy(price = it)) },
                    label = { Text("Price") },
                    modifier = Modifier.weight(2f),
                    singleLine = true,
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
    categories: List<id.my.mymoney.data.model.CategoryResponse>,
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
    accounts: List<id.my.mymoney.data.model.AccountResponse>,
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
