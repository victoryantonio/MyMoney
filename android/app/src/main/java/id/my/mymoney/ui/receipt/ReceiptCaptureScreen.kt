package id.my.mymoney.ui.receipt

import android.graphics.BitmapFactory
import android.net.Uri
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.view.CameraController
import androidx.camera.view.LifecycleCameraController
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
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
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material.icons.outlined.Delete
import androidx.compose.material.icons.outlined.FlashOff
import androidx.compose.material.icons.outlined.FlashOn
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
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.produceState
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.ui.theme.ExpenseRed
import id.my.mymoney.ui.theme.IncomeGreen
import id.my.mymoney.ui.theme.MoneyMedium
import id.my.mymoney.util.Formatters
import java.io.File
import java.math.BigDecimal

/**
 * Capture foto nota langsung dari kamera native (CameraX, ARCHITECTURE.md
 * §3.3 / REQUIREMENTS.md US-07) — TANPA layar perantara "New from receipt".
 *
 * Flow: kamera langsung → preview "Retake"/"Use this photo" → OCR (ML Kit)
 * → form editable (US-08, DESIGN.md §8.2) → simpan satu transaksi multi-item.
 *
 * Overlay kamera hanya 3 kontrol (shutter/flash/galeri), warna putih/abu —
 * pengecualian eksplisit DESIGN.md untuk live camera feed.
 */
private enum class Stage { CAPTURE, PREVIEW, FORM }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReceiptCaptureScreen(
    onDone: () -> Unit,
    onOpenForm: (String, String) -> Unit,
    viewModel: ReceiptViewModel = viewModel(factory = ReceiptViewModel.Factory),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current

    var stage by remember { mutableStateOf(Stage.CAPTURE) }
    var photoUri by remember { mutableStateOf<Uri?>(null) }
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

    fun decodeAndParse(uri: Uri) {
        val bmp = runCatching {
            context.contentResolver.openInputStream(uri)?.use { stream ->
                BitmapFactory.decodeStream(stream)
            }
        }.getOrNull()
        if (bmp != null) viewModel.processBitmap(bmp)
        stage = Stage.FORM
    }

    // Galeri → uri → OCR langsung (kontrol kanan overlay).
    val galleryLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.GetContent(),
    ) { uri ->
        if (uri != null) {
            photoUri = uri
            decodeAndParse(uri)
        }
    }

    Scaffold(
        topBar = {
            if (stage != Stage.CAPTURE) {
                TopAppBar(
                    title = { Text(if (stage == Stage.PREVIEW) "Preview" else "New from receipt") },
                    navigationIcon = {
                        IconButton(onClick = onDone) {
                            Icon(Icons.Outlined.ArrowBack, contentDescription = "Back")
                        }
                    },
                )
            }
        },
        snackbarHost = { SnackbarHost(hostState = snackbarHostState) },
    ) { innerPadding ->
        when (stage) {
            Stage.CAPTURE -> CameraCaptureView(
                onPhotoTaken = { uri ->
                    photoUri = uri
                    stage = Stage.PREVIEW
                },
                onGallery = { galleryLauncher.launch("image/*") },
            )
            Stage.PREVIEW -> {
                val uri = photoUri
                if (uri != null) {
                    PhotoPreview(
                        uri = uri,
                        onRetake = {
                            photoUri = null
                            stage = Stage.CAPTURE
                        },
                        onUse = { decodeAndParse(uri) },
                    )
                }
            }
            Stage.FORM -> ReceiptFormContent(
                state = state,
                categoryId = categoryId,
                accountId = accountId,
                onCategorySelect = { categoryId = it },
                onAccountSelect = { accountId = it },
                onShowError = { showError = it },
                onDone = onDone,
                viewModel = viewModel,
                modifier = Modifier.padding(innerPadding),
            )
        }
    }
}

/**
 * Live camera (CameraX) — TASK 3. Overlay minimal 3 kontrol:
 * flash (kiri), shutter besar tengah-bawah, galeri (kanan).
 * Putih/abu-abu = pengecualian DESIGN.md untuk live camera feed.
 */
@Composable
private fun CameraCaptureView(
    onPhotoTaken: (Uri) -> Unit,
    onGallery: () -> Unit,
) {
    val context = LocalContext.current
    val lifecycleOwner = LocalLifecycleOwner.current
    val controller = remember {
        LifecycleCameraController(context).apply {
            setEnabledUseCases(CameraController.IMAGE_CAPTURE)
            setImageCaptureFlashMode(ImageCapture.FLASH_MODE_OFF) // torch dikontrol manual
        }
    }
    var torchOn by remember { mutableStateOf(false) }
    var hasPermission by remember { mutableStateOf(false) }

    // Izin kamera runtime (minSdk 24).
    val permissionLauncher = rememberLauncherForActivityResult(
        ActivityResultContracts.RequestPermission(),
    ) { granted -> hasPermission = granted }
    LaunchedEffect(Unit) {
        hasPermission = ContextCompat.checkSelfPermission(
            context,
            android.Manifest.permission.CAMERA,
        ) == android.content.pm.PackageManager.PERMISSION_GRANTED
        if (!hasPermission) {
            permissionLauncher.launch(android.Manifest.permission.CAMERA)
        }
    }

    DisposableEffect(lifecycleOwner, controller) {
        controller.bindToLifecycle(lifecycleOwner)
        onDispose { controller.unbind() }
    }

    fun capture() {
        val dir = File(context.cacheDir, "receipts").apply { mkdirs() }
        val file = File(dir, "receipt_${System.currentTimeMillis()}.jpg")
        val output = ImageCapture.OutputFileOptions.Builder(file).build()
        controller.takePicture(
            output,
            ContextCompat.getMainExecutor(context),
            object : ImageCapture.OnImageSavedCallback {
                override fun onImageSaved(results: ImageCapture.OutputFileResults) {
                    val uri = androidx.core.content.FileProvider.getUriForFile(
                        context,
                        "${context.packageName}.fileprovider",
                        file,
                    )
                    onPhotoTaken(uri)
                }

                override fun onError(exc: ImageCaptureException) {
                    // Abaikan — user bisa menekan shutter lagi.
                }
            },
        )
    }

    Box(modifier = Modifier.fillMaxSize().background(Color.Black)) {
        if (hasPermission) {
            AndroidView(
                factory = { ctx ->
                    PreviewView(ctx).apply {
                        scaleType = PreviewView.ScaleType.FILL_CENTER
                    }
                },
                modifier = Modifier.fillMaxSize(),
            ) { previewView ->
                previewView.controller = controller
            }

            // Flash — kiri.
            IconButton(
                onClick = {
                    torchOn = !torchOn
                    controller.enableTorch(torchOn)
                },
                modifier = Modifier
                    .align(Alignment.CenterStart)
                    .padding(start = 24.dp)
                    .size(48.dp)
                    .background(Color.White.copy(alpha = 0.85f), CircleShape),
            ) {
                Icon(
                    if (torchOn) Icons.Outlined.FlashOn else Icons.Outlined.FlashOff,
                    contentDescription = "Flash",
                    tint = Color.Black,
                )
            }

            // Galeri — kanan.
            IconButton(
                onClick = onGallery,
                modifier = Modifier
                    .align(Alignment.CenterEnd)
                    .padding(end = 24.dp)
                    .size(48.dp)
                    .background(Color.White.copy(alpha = 0.85f), CircleShape),
            ) {
                Icon(
                    Icons.Outlined.PhotoLibrary,
                    contentDescription = "Gallery",
                    tint = Color.Black,
                )
            }

            // Shutter — tengah bawah.
            Box(
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = 40.dp)
                    .size(72.dp)
                    .clip(CircleShape)
                    .background(Color.White)
                    .clickable { capture() },
            ) {
                Box(
                    modifier = Modifier
                        .align(Alignment.Center)
                        .size(58.dp)
                        .clip(CircleShape)
                        .border(4.dp, Color.Gray, CircleShape),
                )
            }
        } else {
            // Izin belum diberikan — tombol untuk meminta lagi.
            Column(
                modifier = Modifier.align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                Text(
                    "Izin kamera diperlukan untuk memotret nota.",
                    color = Color.White,
                    style = MaterialTheme.typography.bodyMedium,
                )
                Spacer(Modifier.height(12.dp))
                Button(
                    onClick = { permissionLauncher.launch(android.Manifest.permission.CAMERA) },
                ) {
                    Text("Berikan izin kamera")
                }
            }
        }
    }
}

/** Preview hasil foto: "Retake" / "Use this photo" sebelum OCR (TASK 3). */
@Composable
private fun PhotoPreview(
    uri: Uri,
    onRetake: () -> Unit,
    onUse: () -> Unit,
) {
    val context = LocalContext.current
    val bitmap by produceState<android.graphics.Bitmap?>(initialValue = null, uri) {
        value = runCatching {
            context.contentResolver.openInputStream(uri)?.use { stream ->
                BitmapFactory.decodeStream(stream)
            }
        }.getOrNull()
    }

    Box(modifier = Modifier.fillMaxSize().background(Color.Black)) {
        bitmap?.let {
            Image(
                bitmap = it.asImageBitmap(),
                contentDescription = "Receipt photo",
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Fit,
            )
        }
        Row(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .fillMaxWidth()
                .padding(24.dp),
            horizontalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            TextButton(onClick = onRetake, modifier = Modifier.weight(1f)) {
                Text("Retake", color = Color.White)
            }
            Button(onClick = onUse, modifier = Modifier.weight(1f)) {
                Text("Use this photo")
            }
        }
    }
}

/**
 * Form konfirmasi editable (US-08, DESIGN.md §8.2) — tidak berubah dari
 * alur sebelumnya: type chips, merchant, items, kategori, akun, total, simpan.
 */
@Composable
private fun ReceiptFormContent(
    state: ReceiptViewModel.UiState,
    categoryId: String?,
    accountId: String?,
    onCategorySelect: (String) -> Unit,
    onAccountSelect: (String) -> Unit,
    onShowError: (String) -> Unit,
    onDone: () -> Unit,
    viewModel: ReceiptViewModel,
    modifier: Modifier = Modifier,
) {
    Column(
        modifier = modifier.fillMaxSize().padding(16.dp),
    ) {
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
                    onSelect = onCategorySelect,
                )
            }
            item {
                AccountDropdown(
                    selectedId = accountId,
                    accounts = state.accounts,
                    onSelect = onAccountSelect,
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
                            onShowError("Pilih kategori dan akun")
                            return@Button
                        }
                        viewModel.save(
                            categoryId = categoryId!!,
                            accountId = accountId!!,
                            note = null,
                        ) { success, message ->
                            if (success) onDone() else onShowError(message ?: "Terjadi kesalahan")
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

@Composable
private fun ReceiptItemRow(
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
