/// Daftar transaksi (tab Transaksi) — setara v1 Kotlin `TransactionsScreen`.
///
/// Keyset pagination (20/halaman) dengan infinite scroll, dikelompokkan per
/// tanggal ("Hari Ini", "Kemarin", lalu tanggal lengkap). Tap item → edit;
/// hapus via menu trailing dengan konfirmasi. FAB: tambah manual + scan nota.
library;

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/api_client.dart';
import '../core/app_colors.dart';
import '../core/format.dart';
import '../models/transaction_models.dart';
import '../widgets/transaction_filters.dart'
    show
        TransactionSort,
        TransactionSortLabel,
        categoryTypeLabel,
        filterTransactions,
        showTransactionFilterSheet,
        sortTransactions;
import 'transaction_form_screen.dart';

class TransactionsScreen extends StatefulWidget {
  const TransactionsScreen({super.key, this.refreshToken = 0});

  /// Dinaikkan oleh MainShell saat transaksi baru dibuat/diubah dari luar
  /// tab ini → memicu reload ulang daftar.
  final int refreshToken;

  @override
  State<TransactionsScreen> createState() => _TransactionsScreenState();
}

class _TransactionsScreenState extends State<TransactionsScreen> {
  late final ApiClient _api = ApiClient.instance(Supabase.instance.client);

  final _scrollController = ScrollController();

  final List<TransactionModel> _transactions = [];
  String? _nextCursor;
  bool _loading = false;
  bool _loadingMore = false;
  bool _hasError = false;
  String? _error;
  bool _loadedOnce = false;

  Map<String, String> _categoryNames = {};
  Map<String, String> _accountLabels = {};

  // Label kategori untuk chip filter aktif — nama sama tapi beda tipe
  // (mis. "Other" expense vs income) diberi akhiran tipe agar tidak ambigu.
  Map<String, String> _categoryLabels = {};

  // Filter & sortir (client-side, seperti filter akun di dashboard).
  List<AccountModel> _accounts = [];
  List<CategoryModel> _categories = [];
  final Set<String> _selectedAccountIds = {};
  final Set<String> _selectedCategoryIds = {};
  TransactionSort _sort = TransactionSort.newest;

  /// Saat filter/sortir non-default aktif, seluruh transaksi dimuat sekaligus
  /// (bukan pagination) supaya penyaringan & pengurutan akurat lintas halaman.
  bool _allLoaded = false;

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _load();
  }

  @override
  void didUpdateWidget(covariant TransactionsScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.refreshToken != widget.refreshToken) {
      _load();
    }
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (_scrollController.position.pixels >=
        _scrollController.position.maxScrollExtent - 300) {
      _loadMore();
    }
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _hasError = false;
      _error = null;
    });
    try {
      // Load categories, accounts, and the first page in parallel (lag fix —
      // previously sequential awaits).
      final results = await Future.wait<Object?>([
        _api.fetchCategories(),
        _api.fetchAccounts(),
        _needsAllData
            ? _api.fetchAllTransactions(sort: _sort.apiValue)
            : _api.fetchTransactions(sort: _sort.apiValue),
      ]);
      if (!mounted) return;
      final categories = results[0] as List<CategoryModel>;
      final accounts = results[1] as List<AccountModel>;
      setState(() {
        _categoryNames = {for (final c in categories) c.id: c.name};
        _accountLabels = {for (final a in accounts) a.id: a.label};
        // Nama kategori yang muncul lebih dari sekali (beda tipe) diberi
        // akhiran "· Pengeluaran"/"· Pemasukan" di chip filter aktif.
        final nameCounts = <String, int>{};
        for (final c in categories) {
          nameCounts[c.name] = (nameCounts[c.name] ?? 0) + 1;
        }
        _categoryLabels = {
          for (final c in categories)
            c.id: nameCounts[c.name]! > 1
                ? '${c.name} · ${categoryTypeLabel(c.type)}'
                : c.name,
        };
        _categories = categories;
        _accounts = accounts;
        if (_needsAllData) {
          final all = results[2] as List<TransactionModel>;
          _transactions
            ..clear()
            ..addAll(sortTransactions(
              filterTransactions(
                all,
                accountIds: _selectedAccountIds,
                categoryIds: _selectedCategoryIds,
              ),
              _sort,
            ));
          _nextCursor = null;
          _allLoaded = true;
        } else {
          final page = results[2] as TransactionListResult;
          _transactions
            ..clear()
            ..addAll(page.items);
          _nextCursor = page.nextCursor;
          _allLoaded = false;
        }
        _loadedOnce = true;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _hasError = true;
        _error = e.message;
        _loading = false;
      });
    }
  }

  /// Perlu memuat SEMUA transaksi: hanya saat ada filter akun/kategori
  /// (multi-checklist yang tidak bisa diwakili satu query param).
  /// Sortir kini ditangani server-side (`sort=`), jadi mengubah urutan tidak
  /// lagi memicu pemuatan semua data (perbaikan lag 1 detik).
  bool get _needsAllData =>
      _selectedAccountIds.isNotEmpty || _selectedCategoryIds.isNotEmpty;

  Future<void> _loadMore() async {
    if (_loadingMore || _nextCursor == null || _allLoaded) return;
    setState(() => _loadingMore = true);
    try {
      final page = await _api.fetchTransactions(
        cursor: _nextCursor,
        sort: _sort.apiValue,
      );
      if (!mounted) return;
      setState(() {
        _transactions.addAll(page.items);
        _nextCursor = page.nextCursor;
        _loadingMore = false;
      });
    } on ApiException {
      if (!mounted) return;
      setState(() => _loadingMore = false);
    }
  }

  Future<void> _refresh() => _load();

  /// Buka bottom sheet filter akun + kategori. Saat berubah → reload penuh
  /// (memuat semua transaksi) supaya hasil filter akurat.
  Future<void> _openFilter() async {
    final result = await showTransactionFilterSheet(
      context: context,
      accounts: _accounts,
      categories: _categories,
      selectedAccountIds: _selectedAccountIds,
      selectedCategoryIds: _selectedCategoryIds,
    );
    if (result == null) return;
    if (result.accountIds.length == _selectedAccountIds.length &&
        result.accountIds.containsAll(_selectedAccountIds) &&
        result.categoryIds.length == _selectedCategoryIds.length &&
        result.categoryIds.containsAll(_selectedCategoryIds)) {
      return; // tidak berubah
    }
    setState(() {
      _selectedAccountIds
        ..clear()
        ..addAll(result.accountIds);
      _selectedCategoryIds
        ..clear()
        ..addAll(result.categoryIds);
    });
    _load();
  }

  void _changeSort(TransactionSort sort) {
    if (sort == _sort) return;
    setState(() => _sort = sort);
    if (_allLoaded) {
      // Filter aktif → seluruh data sudah dimuat; urutkan ulang di klien
      // (instan, tanpa request tambahan). Hitung dulu ke variabel lokal,
      // baru timpa list — mencegah bug list kosong akibat cascade clear
      // yang membaca list setelah dikosongkan.
      final sorted = sortTransactions(
        filterTransactions(
          _transactions,
          accountIds: _selectedAccountIds,
          categoryIds: _selectedCategoryIds,
        ),
        _sort,
      );
      setState(() {
        _transactions
          ..clear()
          ..addAll(sorted);
      });
    } else {
      // Sortir server-side: muat ulang halaman pertama dengan urutan baru.
      _load();
    }
  }

  /// Hapus semua filter aktif → reload pagination normal.
  void _clearFilters() {
    if (_selectedAccountIds.isEmpty && _selectedCategoryIds.isEmpty) return;
    setState(() {
      _selectedAccountIds.clear();
      _selectedCategoryIds.clear();
    });
    _load();
  }

  int get _activeFilterCount =>
      _selectedAccountIds.length + _selectedCategoryIds.length;

  Future<void> _edit(TransactionModel tx) async {
    final changed = await Navigator.of(context).push<bool>(
      MaterialPageRoute(
        builder: (_) => TransactionFormScreen(api: _api, transaction: tx),
      ),
    );
    if (changed == true) _load();
  }

  Future<void> _confirmDelete(TransactionModel tx) async {
    final ok = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Hapus transaksi?'),
        content: Text(
          'Transaksi "${_categoryNames[tx.categoryId] ?? (tx.type == 'transfer' ? 'Transfer' : tx.merchant ?? 'ini')}" '
          'sebesar ${formatRupiah(tx.totalAmount)} akan dihapus permanen.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Batal'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Hapus'),
          ),
        ],
      ),
    );
    if (ok != true) return;
    try {
      await _api.deleteTransaction(tx.id);
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Transaksi dihapus')),
      );
      _load();
    } on ApiException catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message)),
      );
    }
  }

  /// Kelompokkan transaksi: "Hari Ini" / "Kemarin" / tanggal lengkap.
  List<(String, List<TransactionModel>)> _groupByDay() {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));

    final groups = <(String, List<TransactionModel>)>[];
    for (final tx in _transactions) {
      final d = tx.transactionDate;
      final day = DateTime(d.year, d.month, d.day);
      String label;
      if (day == today) {
        label = 'Hari Ini';
      } else if (day == yesterday) {
        label = 'Kemarin';
      } else {
        label = formatDateDetail(d);
      }
      if (groups.isNotEmpty && groups.last.$1 == label) {
        groups[groups.length - 1].$2.add(tx);
      } else {
        groups.add((label, [tx]));
      }
    }
    return groups;
  }

  @override
  Widget build(BuildContext context) {
    final filterCount = _activeFilterCount;
    return Scaffold(
      appBar: AppBar(
        title: const Text('Transaksi'),
        actions: [
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
            onSelected: _changeSort,
            itemBuilder: (_) => const [
              PopupMenuItem(
                value: TransactionSort.newest,
                child: Text('Tanggal terbaru'),
              ),
              PopupMenuItem(
                value: TransactionSort.oldest,
                child: Text('Tanggal terlama'),
              ),
              PopupMenuItem(
                value: TransactionSort.largest,
                child: Text('Nominal terbesar'),
              ),
              PopupMenuItem(
                value: TransactionSort.smallest,
                child: Text('Nominal terkecil'),
              ),
            ],
            icon: const Icon(Icons.sort),
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: _buildBody(context),
      ),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading && !_loadedOnce) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_hasError && !_loadedOnce) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, size: 48),
              const SizedBox(height: 12),
              Text(_error ?? 'Terjadi kesalahan', textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Coba lagi'),
              ),
            ],
          ),
        ),
      );
    }
    if (_transactions.isEmpty) {
      return ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          if (_activeFilterCount > 0 || _sort != TransactionSort.newest)
            _filterBar(),
          const SizedBox(height: 160),
          Icon(
            _activeFilterCount > 0
                ? Icons.filter_alt_off_outlined
                : Icons.receipt_long_outlined,
            size: 56,
          ),
          const SizedBox(height: 12),
          Center(
            child: Text(
              _activeFilterCount > 0
                  ? 'Tidak ada transaksi yang cocok'
                  : 'Belum ada transaksi',
            ),
          ),
          const SizedBox(height: 4),
          Center(
            child: Text(
              _activeFilterCount > 0
                  ? 'Coba ubah filter atau reset pilihan'
                  : 'Tekan "+" untuk mencatat pemasukan/pengeluaran',
              style: TextStyle(fontSize: 12),
            ),
          ),
          if (_activeFilterCount > 0)
            Padding(
              padding: const EdgeInsets.only(top: 12),
              child: Center(
                child: OutlinedButton.icon(
                  onPressed: _clearFilters,
                  icon: const Icon(Icons.filter_alt_off),
                  label: const Text('Reset filter'),
                ),
              ),
            ),
        ],
      );
    }

    final groups = _groupByDay();
    return Column(
      children: [
        if (_activeFilterCount > 0 || _sort != TransactionSort.newest)
          _filterBar(),
        Expanded(
          child: ListView.builder(
            controller: _scrollController,
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
            itemCount: groups.length + 1,
            itemBuilder: (context, i) {
              if (i == groups.length) {
                if (_loadingMore) {
                  return const Padding(
                    padding: EdgeInsets.all(16),
                    child: Center(child: CircularProgressIndicator()),
                  );
                }
                return const SizedBox(height: 16);
              }
              final (label, items) = groups[i];
              return Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 8),
                    child: Text(
                      label,
                      style: Theme.of(context).textTheme.labelLarge?.copyWith(
                            color:
                                Theme.of(context).colorScheme.onSurfaceVariant,
                            fontWeight: FontWeight.w700,
                          ),
                    ),
                  ),
                  Card(
                    margin: EdgeInsets.zero,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(12),
                      side: BorderSide(
                        color: Theme.of(context).colorScheme.outlineVariant,
                      ),
                    ),
                    child: Column(
                      children: [
                        for (var j = 0; j < items.length; j++) ...[
                          if (j > 0)
                            Divider(
                              height: 1,
                              indent: 16,
                              endIndent: 16,
                              color: Theme.of(context).colorScheme.outlineVariant,
                            ),
                          _TransactionTile(
                            tx: items[j],
                            categoryName: items[j].type == 'transfer'
                                ? 'Transfer'
                                : _categoryNames[items[j].categoryId] ?? '—',
                            accountLabel:
                                _accountLabels[items[j].accountId] ?? '',
                            onTap: () => _edit(items[j]),
                            onDelete: () => _confirmDelete(items[j]),
                          ),
                        ],
                      ],
                    ),
                  ),
                ],
              );
            },
          ),
        ),
      ],
    );
  }

  /// Baris chip filter/sortir aktif — bisa langsung dihapus per chip.
  Widget _filterBar() {
    final scheme = Theme.of(context).colorScheme;
    final chips = <Widget>[
      for (final id in _selectedAccountIds)
        if (_accountLabels[id] != null)
          InputChip(
            label: Text(_accountLabels[id]!),
            avatar: Icon(Icons.account_balance_wallet_outlined,
                size: 16, color: scheme.onSurfaceVariant),
            onDeleted: () {
              setState(() => _selectedAccountIds.remove(id));
              _load();
            },
          ),
      for (final id in _selectedCategoryIds)
        if (_categoryLabels[id] != null)
          InputChip(
            label: Text(_categoryLabels[id]!),
            avatar:
                Icon(Icons.category_outlined, size: 16, color: scheme.onSurfaceVariant),
            onDeleted: () {
              setState(() => _selectedCategoryIds.remove(id));
              _load();
            },
          ),
      if (_sort != TransactionSort.newest)
        InputChip(
          label: Text(_sort.label),
          avatar: Icon(Icons.sort, size: 16, color: scheme.onSurfaceVariant),
          onDeleted: () => _changeSort(TransactionSort.newest),
        ),
    ];
    return Container(
      width: double.infinity,
      color: scheme.surfaceContainerLow,
      padding: const EdgeInsets.fromLTRB(16, 8, 16, 8),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: [
            ...chips,
            if (_activeFilterCount > 0) ...[
              const SizedBox(width: 4),
              IconButton(
                tooltip: 'Reset semua filter',
                onPressed: _clearFilters,
                icon: const Icon(Icons.filter_alt_off, size: 20),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

class _TransactionTile extends StatelessWidget {
  const _TransactionTile({
    required this.tx,
    required this.categoryName,
    required this.accountLabel,
    required this.onTap,
    required this.onDelete,
  });

  final TransactionModel tx;
  final String categoryName;
  final String accountLabel;
  final VoidCallback onTap;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final isIncome = tx.type == 'income';
    final isTransfer = tx.type == 'transfer';
    final color = isTransfer
        ? Theme.of(context).colorScheme.primary
        : isIncome
            ? AppColors.income(context)
            : AppColors.expense(context);
    final title = tx.merchant?.isNotEmpty == true
        ? tx.merchant!
        : (isTransfer ? 'Transfer' : categoryName);
    final subtitle = [
      if (tx.merchant?.isNotEmpty == true && !isTransfer) categoryName,
      if (tx.merchant?.isNotEmpty == true && isTransfer) 'Transfer',
      if (accountLabel.isNotEmpty) accountLabel,
      if (tx.note?.isNotEmpty == true) tx.note!,
    ].join(' · ');

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        child: Row(
          children: [
            CircleAvatar(
              radius: 18,
              backgroundColor: color.withValues(alpha: 0.15),
              child: Icon(
                isTransfer
                    ? Icons.swap_horiz
                    : isIncome
                        ? Icons.arrow_upward
                        : Icons.arrow_downward,
                size: 18,
                color: color,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    title,
                    style: Theme.of(context)
                        .textTheme
                        .bodyMedium
                        ?.copyWith(fontWeight: FontWeight.w600),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  if (subtitle.isNotEmpty)
                    Text(
                      subtitle,
                      style: Theme.of(context).textTheme.bodySmall?.copyWith(
                            color:
                                Theme.of(context).colorScheme.onSurfaceVariant,
                          ),
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              mainAxisSize: MainAxisSize.min,
              children: [
                Text(
                  '${isTransfer ? '' : isIncome ? '+' : '-'}${formatRupiah(tx.totalAmount)}',
                  style: TextStyle(fontWeight: FontWeight.w700, color: color),
                ),
                if (tx.originalCurrency != 'IDR')
                  Text(
                    tx.originalCurrency,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color:
                              Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
              ],
            ),
            const SizedBox(width: 4),
            PopupMenuButton<String>(
              onSelected: (v) {
                if (v == 'delete') onDelete();
              },
              itemBuilder: (context) => const [
                PopupMenuItem(
                  value: 'delete',
                  child: ListTile(
                    contentPadding: EdgeInsets.zero,
                    leading: Icon(Icons.delete_outline),
                    title: Text('Hapus'),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
