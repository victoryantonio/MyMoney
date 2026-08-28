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
import 'transaction_form_screen.dart';

class TransactionsScreen extends StatefulWidget {
  const TransactionsScreen({super.key});

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

  @override
  void initState() {
    super.initState();
    _scrollController.addListener(_onScroll);
    _load();
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
        _api.fetchTransactions(),
      ]);
      if (!mounted) return;
      final categories = results[0] as List<CategoryModel>;
      final accounts = results[1] as List<AccountModel>;
      final page = results[2] as TransactionListResult;
      setState(() {
        _categoryNames = {for (final c in categories) c.id: c.name};
        _accountLabels = {for (final a in accounts) a.id: a.label};
        _transactions
          ..clear()
          ..addAll(page.items);
        _nextCursor = page.nextCursor;
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

  Future<void> _loadMore() async {
    if (_loadingMore || _nextCursor == null) return;
    setState(() => _loadingMore = true);
    try {
      final page = await _api.fetchTransactions(cursor: _nextCursor);
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
    return Scaffold(
      appBar: AppBar(title: const Text('Transaksi')),
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
        children: const [
          SizedBox(height: 160),
          Icon(Icons.receipt_long_outlined, size: 56),
          SizedBox(height: 12),
          Center(child: Text('Belum ada transaksi')),
          SizedBox(height: 4),
          Center(
            child: Text(
              'Tekan "+" untuk mencatat pemasukan/pengeluaran',
              style: TextStyle(fontSize: 12),
            ),
          ),
        ],
      );
    }

    final groups = _groupByDay();
    return ListView.builder(
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
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
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
            Text(
              '${isTransfer ? '' : isIncome ? '+' : '-'}${formatRupiah(tx.totalAmount)}',
              style: TextStyle(fontWeight: FontWeight.w700, color: color),
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
