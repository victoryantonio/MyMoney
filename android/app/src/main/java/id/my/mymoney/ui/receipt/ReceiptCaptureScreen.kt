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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.outlined.ArrowBack
import androidx.compose.material.icons.outlined.FlashOff
import androidx.compose.material.icons.outlined.FlashOn
import androidx.compose.material.icons.outlined.PhotoLibrary
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import java.io.File

/**
 * Capture foto nota langsung dari kamera native (CameraX, ARCHITECTURE.md
 * §3.3 / REQUIREMENTS.md US-07).
 *
 * Flow: kamera langsung → preview "Retake"/"Use this photo" → OCR (ML Kit,
 * loading) → buka form New Transaction (SATU form multi-item yang sama dengan
 * tombol "+"; hasil OCR diisi via AppContainer.pendingReceipt).
 *
 * Overlay kamera hanya 3 kontrol (shutter/flash/galeri), warna putih/abu —
 * pengecualian eksplisit DESIGN.md untuk live camera feed.
 */
private enum class Stage { CAPTURE, PREVIEW }

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ReceiptCaptureScreen(
    onDone: () -> Unit,
    onOpenForm: () -> Unit,
    viewModel: ReceiptViewModel = viewModel(factory = ReceiptViewModel.Factory),
) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    val context = LocalContext.current

    var stage by remember { mutableStateOf(Stage.CAPTURE) }
    var photoUri by remember { mutableStateOf<Uri?>(null) }
    var navigatedToForm by remember { mutableStateOf(false) }
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

    // OCR selesai → buka form New Transaction (hasilnya sudah di pendingReceipt,
    // TransactionFormScreen yang membaca & mengisinya). Loading tampil di preview.
    LaunchedEffect(state.processing) {
        if (!state.processing && state.items.isNotEmpty() && !navigatedToForm) {
            navigatedToForm = true
            onOpenForm()
        }
    }

    Scaffold(
        topBar = {
            if (stage == Stage.PREVIEW) {
                TopAppBar(
                    title = { Text("Preview") },
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
                        processing = state.processing,
                        onRetake = {
                            photoUri = null
                            navigatedToForm = false
                            stage = Stage.CAPTURE
                        },
                        onUse = { decodeAndParse(uri) },
                        modifier = Modifier.padding(innerPadding),
                    )
                }
            }
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
    processing: Boolean,
    onRetake: () -> Unit,
    onUse: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val context = LocalContext.current
    val bitmap by produceState<android.graphics.Bitmap?>(initialValue = null, uri) {
        value = runCatching {
            context.contentResolver.openInputStream(uri)?.use { stream ->
                BitmapFactory.decodeStream(stream)
            }
        }.getOrNull()
    }

    Box(modifier = modifier.fillMaxSize().background(Color.Black)) {
        bitmap?.let {
            Image(
                bitmap = it.asImageBitmap(),
                contentDescription = "Receipt photo",
                modifier = Modifier.fillMaxSize(),
                contentScale = ContentScale.Fit,
            )
        }
        if (processing) {
            Column(
                modifier = Modifier.align(Alignment.Center),
                horizontalAlignment = Alignment.CenterHorizontally,
            ) {
                CircularProgressIndicator(color = Color.White)
                Spacer(Modifier.height(12.dp))
                Text(
                    "Membaca nota…",
                    color = Color.White,
                    style = MaterialTheme.typography.bodyMedium,
                )
            }
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
            Button(onClick = onUse, enabled = !processing, modifier = Modifier.weight(1f)) {
                Text("Use this photo")
            }
        }
    }
}
