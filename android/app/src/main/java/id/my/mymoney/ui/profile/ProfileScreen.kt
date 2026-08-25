package id.my.mymoney.ui.profile

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
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.outlined.ArrowForwardIos
import androidx.compose.material.icons.outlined.AccountBalanceWallet
import androidx.compose.material.icons.outlined.Category
import androidx.compose.material.icons.outlined.DarkMode
import androidx.compose.material.icons.outlined.LightMode
import androidx.compose.material.icons.outlined.Logout
import androidx.compose.material.icons.outlined.PhoneAndroid
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.data.ThemeMode
import id.my.mymoney.data.model.UserResponse
import id.my.mymoney.ui.components.ConfirmDialog
import id.my.mymoney.ui.components.MyMoneyCard

/**
 * Menu Profile (DESIGN.md §8.5): pengaturan tema, kelola kategori & akun,
 * dan logout. Categories/Accounts dipindah dari tab utama ke sini.
 */
@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun ProfileScreen(
    user: UserResponse,
    onLogout: () -> Unit,
    onOpenCategories: () -> Unit,
    onOpenAccounts: () -> Unit,
    viewModel: ProfileViewModel = viewModel(factory = ProfileViewModel.Factory),
) {
    val themeMode by viewModel.themeMode.collectAsStateWithLifecycle()

    Scaffold(
        topBar = {
            TopAppBar(title = { Text("Profile") })
        },
    ) { innerPadding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(innerPadding)
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            // ── Header pengguna ──
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier
                        .size(56.dp)
                        .clip(CircleShape)
                        .background(
                            MaterialTheme.colorScheme.primaryContainer,
                            CircleShape,
                        ),
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.Center,
                ) {
                    Text(
                        user.display_name.take(1).uppercase(),
                        style = MaterialTheme.typography.titleLarge,
                        color = MaterialTheme.colorScheme.primary,
                    )
                }
                Spacer(Modifier.size(12.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        user.display_name,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        user.email,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onSurfaceVariant,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }

            // ── Pengaturan tampilan: tema ──
            MyMoneyCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                    Text(
                        "Appearance",
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Spacer(Modifier.height(8.dp))
                    ThemeMode.entries.forEach { mode ->
                        ThemeOptionRow(
                            mode = mode,
                            selected = mode == themeMode,
                            onClick = { viewModel.setThemeMode(mode) },
                        )
                    }
                }
            }

            // ── Manajemen ──
            MyMoneyCard(modifier = Modifier.fillMaxWidth()) {
                Column(modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
                    ProfileMenuItem(
                        icon = Icons.Outlined.Category,
                        label = "Categories Management",
                        onClick = onOpenCategories,
                    )
                    HorizontalDivider(
                        modifier = Modifier.padding(horizontal = 16.dp),
                        color = MaterialTheme.colorScheme.outline,
                    )
                    ProfileMenuItem(
                        icon = Icons.Outlined.AccountBalanceWallet,
                        label = "Accounts Management",
                        onClick = onOpenAccounts,
                    )
                }
            }

            Spacer(Modifier.weight(1f))

            // ── Logout ──
            var showConfirm by androidx.compose.runtime.remember { androidx.compose.runtime.mutableStateOf(false) }
            MyMoneyCard(
                modifier = Modifier.fillMaxWidth(),
                onClick = { showConfirm = true },
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth().padding(16.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Icon(
                        Icons.Outlined.Logout,
                        contentDescription = null,
                        tint = MaterialTheme.colorScheme.error,
                    )
                    Spacer(Modifier.size(12.dp))
                    Text(
                        "Logout",
                        style = MaterialTheme.typography.bodyLarge,
                        color = MaterialTheme.colorScheme.error,
                        modifier = Modifier.weight(1f),
                    )
                }
            }
            if (showConfirm) {
                ConfirmDialog(
                    title = "Logout",
                    message = "Apakah Anda yakin ingin keluar?",
                    confirmText = "Logout",
                    onConfirm = {
                        showConfirm = false
                        onLogout()
                    },
                    onDismiss = { showConfirm = false },
                )
            }
        }
    }
}

@Composable
private fun ThemeOptionRow(
    mode: ThemeMode,
    selected: Boolean,
    onClick: () -> Unit,
) {
    val icon = when (mode) {
        ThemeMode.SYSTEM -> Icons.Outlined.PhoneAndroid
        ThemeMode.LIGHT -> Icons.Outlined.LightMode
        ThemeMode.DARK -> Icons.Outlined.DarkMode
    }
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clip(MaterialTheme.shapes.medium)
            .background(
                if (selected) MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.5f)
                else androidx.compose.ui.graphics.Color.Transparent,
            )
            .clickable(onClick = onClick)
            .padding(12.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.size(12.dp))
        Text(
            mode.label,
            style = MaterialTheme.typography.bodyMedium,
            modifier = Modifier.weight(1f),
        )
        if (selected) {
            Text(
                "✓",
                style = MaterialTheme.typography.labelLarge,
                color = MaterialTheme.colorScheme.primary,
            )
        }
    }
}

@Composable
private fun ProfileMenuItem(
    icon: ImageVector,
    label: String,
    onClick: () -> Unit,
) {
    Row(
        modifier = Modifier
            .fillMaxWidth()
            .clickable(onClick = onClick)
            .padding(16.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Icon(icon, contentDescription = null, tint = MaterialTheme.colorScheme.primary)
        Spacer(Modifier.size(12.dp))
        Text(
            label,
            style = MaterialTheme.typography.bodyLarge,
            modifier = Modifier.weight(1f),
        )
        Icon(
            Icons.AutoMirrored.Outlined.ArrowForwardIos,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.onSurfaceVariant,
            modifier = Modifier.size(16.dp),
        )
    }
}

private val ThemeMode.label: String
    get() = when (this) {
        ThemeMode.SYSTEM -> "System default"
        ThemeMode.LIGHT -> "Light"
        ThemeMode.DARK -> "Dark"
    }
