/// Daftar transaksi terfilter dari summary card (Income/Expense/Net).
///
/// Sudah dibatasi periode & akun oleh dashboard; di sini user bisa
/// mempersempit lagi per kategori/akun (multi-checklist) + sortir tanggal
/// maupun nominal sehingga halaman lebih ringkas.
library;

import 'package:flutter/material.dart';

import '../core/app_colors.dart';
import '../core/format.dart';
import '../models/transaction_models.dart';
import '../widgets/transaction_filters.dart';

class TransactionListScreen extends StatefulWidget {
  const TransactionListScreen({
    super.key,
    required this.title,
    required this.transactions,
    required this.categoryNames,
    required this.accountLabels,
    required this.onTransactionTap,
    this.accounts = const [],
    this.categories = const [],
  });

  final String title;
  final List<TransactionModel> transactions;
  final Map<String, String> categoryNames;
  final Map<String, String> accountLabels;
  final ValueChanged<TransactionModel> onTransactionTap;

  /// Untuk bottom sheet filter (opsional — jika kosong, tombol filter
  /// disembunyikan).
  final List<AccountModel> accounts;
  final List<CategoryModel> categories;

  @override
  State<TransactionListScreen> createState() => _TransactionListScreenState();
}

class _TransactionListScreenState extends State<TransactionListScreen> {
  TransactionSort _sort = TransactionSort.newest;
  final Set<String> _selectedAccountIds = {};
  final Set<String> _selectedCategoryIds = {};

  bool get _canFilter =>
      widget.accounts.isNotEmpty || widget.categories.isNotEmpty;

  int get _activeFilterCount =>
      _selectedAccountIds.length + _selectedCategoryIds.length;

  List<TransactionModel> get _sorted {
    var result = filterTransactions(
      widget.transactions,
      accountIds: _selectedAccountIds,
      categoryIds: _selectedCategoryIds,
    );
    result = sortTransactions(result, _sort);
    return result;
  }

  Future<void> _openFilter() async {
    final result = await showTransactionFilterSheet(
      context: context,
      accounts: widget.accounts,
      categories: widget.categories,
      selectedAccountIds: _selectedAccountIds,
      selectedCategoryIds: _selectedCategoryIds,
    );
    if (result == null) return;
    setState(() {
      _selectedAccountIds
        ..clear()
        ..addAll(result.accountIds);
      _selectedCategoryIds
        ..clear()
        ..addAll(result.categoryIds);
    });
  }

  void _clearFilters() {
    setState(() {
      _selectedAccountIds.clear();
      _selectedCategoryIds.clear();
    });
  }


  @override
  Widget build(BuildContext context) {
    final items = _sorted;
    final filterCount = _activeFilterCount;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          if (_canFilter)
            IconButton(
              tooltip: 'Filter akun & kategori',
              onPressed: _openFilter,
              icon: Badge(
                isLabelVisible: filterCount > 0,
                label: Text('$filterCount'),
                child: const Icon(Icons.filter_list),
              ),
            ),
          PopupMenuButton<TransactionSort>(
            tooltip: 'Urutkan',
            initialValue: _sort,
            onSelected: (sort) => setState(() => _sort = sort),
            itemBuilder: (_) => [
              for (final sort in TransactionSort.values)
                PopupMenuItem(
                  value: sort,
                  child: Text(sort.label),
                ),
            ],
            icon: const Icon(Icons.sort),
          ),
        ],
      ),
      body: Column(
        children: [
          if (filterCount > 0)
            Container(
              width: double.infinity,
              color: Theme.of(context).colorScheme.surfaceContainerLow,
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
              child: Row(
                children: [
                  Expanded(
                    child: Text(
                      '$filterCount filter aktif',
                      style: Theme.of(context).textTheme.bodySmall,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  TextButton.icon(
                    onPressed: _clearFilters,
                    icon: const Icon(Icons.filter_alt_off, size: 18),
                    label: const Text('Reset'),
                  ),
                ],
              ),
            ),
          Expanded(
            child: items.isEmpty
                ? Center(
                    child: Text(
                      filterCount > 0
                          ? 'Tidak ada transaksi yang cocok'
                          : 'Tidak ada transaksi pada periode ini',
                    ),
                  )
                : ListView.separated(
                    padding: const EdgeInsets.all(16),
                    itemCount: items.length,
                    separatorBuilder: (_, _) => const SizedBox(height: 8),
                    itemBuilder: (context, index) {
                      final tx = items[index];
                      final color = switch (tx.type) {
                        'income' => AppColors.income(context),
                        'transfer' => Theme.of(context).colorScheme.primary,
                        _ => AppColors.expense(context),
                      };
                      final categoryLabel = tx.type == 'transfer'
                          ? 'Transfer'
                          : widget.categoryNames[tx.categoryId] ?? '—';
                      return Card(
                        margin: EdgeInsets.zero,
                        elevation: 0,
                        child: ListTile(
                          onTap: () => widget.onTransactionTap(tx),
                          leading: CircleAvatar(
                            backgroundColor: color.withValues(alpha: 0.14),
                            child: Icon(
                              tx.type == 'income'
                                  ? Icons.arrow_upward
                                  : tx.type == 'transfer'
                                      ? Icons.swap_horiz
                                      : Icons.arrow_downward,
                              color: color,
                            ),
                          ),
                          title: Text(
                            tx.merchant ??
                                (tx.type == 'transfer'
                                    ? 'Transfer'
                                    : widget.categoryNames[tx.categoryId] ??
                                        'Transaksi'),
                            maxLines: 1,
                            overflow: TextOverflow.ellipsis,
                          ),
                          subtitle: Text(
                            '${formatDateDetail(tx.transactionDate)} · '
                            '${widget.accountLabels[tx.accountId] ?? 'Akun'} · '
                            '$categoryLabel',
                            maxLines: 2,
                            overflow: TextOverflow.ellipsis,
                          ),
                          trailing: Column(
                            mainAxisAlignment: MainAxisAlignment.center,
                            crossAxisAlignment: CrossAxisAlignment.end,
                            children: [
                              Text(
                                formatRupiah(tx.totalAmount),
                                style: TextStyle(
                                  color: color,
                                  fontWeight: FontWeight.w700,
                                ),
                              ),
                              if (tx.originalCurrency != 'IDR')
                                Text(
                                  tx.originalCurrency,
                                  style: Theme.of(context)
                                      .textTheme
                                      .bodySmall
                                      ?.copyWith(
                                        color: Theme.of(context)
                                            .colorScheme
                                            .onSurfaceVariant,
                                      ),
                                ),
                            ],
                          ),
                        ),
                      );
                    },
                  ),
          ),
        ],
      ),
    );
  }
}