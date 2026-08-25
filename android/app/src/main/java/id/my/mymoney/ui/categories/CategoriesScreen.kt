package id.my.mymoney.ui.categories

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.FilterChip
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
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import id.my.mymoney.data.model.CategoryResponse
import id.my.mymoney.ui.components.EmptyState
import id.my.mymoney.ui.components.ErrorView
import id.my.mymoney.ui.components.LoadingView
import id.my.mymoney.ui.theme.ExpenseRed
import id.my.mymoney.ui.theme.IncomeGreen

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun CategoriesScreen(viewModel: CategoriesViewModel = viewModel(factory = CategoriesViewModel.Factory)) {
    val state by viewModel.uiState.collectAsStateWithLifecycle()
    var typeFilter by remember { mutableStateOf("all") }
    var editing by remember { mutableStateOf<CategoryResponse?>(null) }
    var deleting by remember { mutableStateOf<CategoryResponse?>(null) }
    var showCreate by remember { mutableStateOf(false) }

    Scaffold(
        topBar = { TopAppBar(title = { Text("Categories") }) },
        floatingActionButton = {
            FloatingActionButton(onClick = { showCreate = true }) {
                Icon(Icons.Filled.Add, contentDescription = "Add category")
            }
        },
    ) { innerPadding ->
        Column(modifier = Modifier.fillMaxSize().padding(innerPadding)) {
            Row(modifier = Modifier.padding(horizontal = 16.dp), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                FilterChip(selected = typeFilter == "all", onClick = { typeFilter = "all" }, label = { Text("All") })
                FilterChip(selected = typeFilter == "expense", onClick = { typeFilter = "expense" }, label = { Text("Expense") })
                FilterChip(selected = typeFilter == "income", onClick = { typeFilter = "income" }, label = { Text("Income") })
            }

            when {
                state.loading -> LoadingView()
                state.error != null && state.categories.isEmpty() ->
                    ErrorView(state.error, onRetry = { viewModel.load() })
                state.categories.isEmpty() -> EmptyState("No categories. Global defaults will appear here.")
                else -> {
                    val filtered = state.categories.filter { typeFilter == "all" || it.type == typeFilter }
                    LazyColumn(
                        modifier = Modifier.fillMaxSize(),
                        contentPadding = androidx.compose.foundation.layout.PaddingValues(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        items(filtered, key = { it.id }) { cat ->
                            CategoryRow(
                                cat = cat,
                                onEdit = { editing = cat },
                                onDelete = { deleting = cat },
                            )
                        }
                    }
                }
            }
        }
    }

    if (showCreate) {
        CategoryEditDialog(
            title = "New category",
            initialName = "",
            initialType = "expense",
            onDismiss = { showCreate = false },
            onSave = { name, type ->
                viewModel.create(name, type) { ok, err -> if (ok) showCreate = false }
            },
        )
    }

    editing?.let { cat ->
        CategoryEditDialog(
            title = "Edit category",
            initialName = cat.name,
            initialType = cat.type,
            onDismiss = { editing = null },
            onSave = { name, type ->
                viewModel.update(cat, name, type) { ok, _ -> if (ok) editing = null }
            },
        )
    }

    deleting?.let { cat ->
        AlertDialog(
            onDismissRequest = { deleting = null },
            title = { Text("Delete category") },
            text = { Text("Delete \"${cat.name}\"? Transactions keep their data but this category will be hidden.") },
            confirmButton = {
                TextButton(onClick = {
                    viewModel.delete(cat) { ok, _ -> if (ok) deleting = null }
                }) { Text("Delete", color = ExpenseRed) }
            },
            dismissButton = {
                TextButton(onClick = { deleting = null }) { Text("Cancel") }
            },
        )
    }
}

@Composable
private fun CategoryRow(cat: CategoryResponse, onEdit: () -> Unit, onDelete: () -> Unit) {
    // §3: card = surface-variant — kontras terhadap background surface.
    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(cat.name, style = MaterialTheme.typography.bodyLarge)
                Text(
                    if (cat.is_default) "Global default" else (if (cat.type == "expense") "Expense · custom" else "Income · custom"),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSurfaceVariant,
                )
            }
            Text(
                if (cat.type == "expense") "Expense" else "Income",
                style = MaterialTheme.typography.labelMedium,
                color = if (cat.type == "expense") ExpenseRed else IncomeGreen,
            )
            if (!cat.is_default) {
                IconButton(onClick = onEdit) {
                    Icon(Icons.Filled.Edit, contentDescription = "Edit", tint = MaterialTheme.colorScheme.outline)
                }
                IconButton(onClick = onDelete) {
                    Icon(Icons.Filled.Delete, contentDescription = "Delete", tint = MaterialTheme.colorScheme.outline)
                }
            }
        }
    }
}

@Composable
private fun CategoryEditDialog(
    title: String,
    initialName: String,
    initialType: String,
    onDismiss: () -> Unit,
    onSave: (String, String) -> Unit,
) {
    var name by remember { mutableStateOf(initialName) }
    var type by remember { mutableStateOf(initialType) }
    var error by remember { mutableStateOf<String?>(null) }
    val focusManager = LocalFocusManager.current

    fun save() {
        if (name.isBlank()) error = "Name is required" else onSave(name, type)
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(title) },
        text = {
            Column {
                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Name") },
                    singleLine = true,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Done),
                    keyboardActions = KeyboardActions(onDone = { focusManager.clearFocus(); save() }),
                    modifier = Modifier.fillMaxWidth(),
                )
                Spacer(Modifier.height(12.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    FilterChip(selected = type == "expense", onClick = { type = "expense" }, label = { Text("Expense") })
                    FilterChip(selected = type == "income", onClick = { type = "income" }, label = { Text("Income") })
                }
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
