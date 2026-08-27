/// Daftar transaksi terfilter dari summary card.
library;

import 'package:flutter/material.dart';

import '../core/app_colors.dart';
import '../core/format.dart';
import '../models/transaction_models.dart';

enum _TransactionSort { newest, oldest, largest, smallest }

class TransactionListScreen extends StatefulWidget {
  const TransactionListScreen({
    super.key,
    required this.title,
    required this.transactions,
    required this.categoryNames,
    required this.accountLabels,
    required this.onTransactionTap,
  });

  final String title;
  final List<TransactionModel> transactions;
  final Map<String, String> categoryNames;
  final Map<String, String> accountLabels;
  final ValueChanged<TransactionModel> onTransactionTap;

  @override
  State<TransactionListScreen> createState() => _TransactionListScreenState();
}

class _TransactionListScreenState extends State<TransactionListScreen> {
  _TransactionSort _sort = _TransactionSort.newest;

  List<TransactionModel> get _sorted {
    final result = [...widget.transactions];
    result.sort((a, b) {
      switch (_sort) {
        case _TransactionSort.newest:
          return b.transactionDate.compareTo(a.transactionDate);
        case _TransactionSort.oldest:
          return a.transactionDate.compareTo(b.transactionDate);
        case _TransactionSort.largest:
          return b.totalAmount.compareTo(a.totalAmount);
        case _TransactionSort.smallest:
          return a.totalAmount.compareTo(b.totalAmount);
      }
    });
    return result;
  }

  @override
  Widget build(BuildContext context) {
    final items = _sorted;
    return Scaffold(
      appBar: AppBar(
        title: Text(widget.title),
        actions: [
          PopupMenuButton<_TransactionSort>(
            tooltip: 'Urutkan',
            initialValue: _sort,
            onSelected: (sort) => setState(() => _sort = sort),
            itemBuilder: (_) => const [
              PopupMenuItem(value: _TransactionSort.newest, child: Text('Tanggal terbaru')),
              PopupMenuItem(value: _TransactionSort.oldest, child: Text('Tanggal terlama')),
              PopupMenuItem(value: _TransactionSort.largest, child: Text('Nominal terbesar')),
              PopupMenuItem(value: _TransactionSort.smallest, child: Text('Nominal terkecil')),
            ],
            icon: const Icon(Icons.sort),
          ),
        ],
      ),
      body: items.isEmpty
          ? const Center(child: Text('Tidak ada transaksi pada periode ini'))
          : ListView.separated(
              padding: const EdgeInsets.all(16),
              itemCount: items.length,
              separatorBuilder: (_, _) => const SizedBox(height: 8),
              itemBuilder: (context, index) {
                final tx = items[index];
                final color = tx.type == 'income'
                    ? AppColors.income(context)
                    : AppColors.expense(context);
                return Card(
                  margin: EdgeInsets.zero,
                  elevation: 0,
                  child: ListTile(
                    onTap: () => widget.onTransactionTap(tx),
                    leading: CircleAvatar(
                      backgroundColor: color.withValues(alpha: 0.14),
                      child: Icon(
                        tx.type == 'income' ? Icons.arrow_upward : Icons.arrow_downward,
                        color: color,
                      ),
                    ),
                    title: Text(
                      tx.merchant ?? widget.categoryNames[tx.categoryId] ?? 'Transaksi',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                    subtitle: Text(
                      '${formatDateDetail(tx.transactionDate)} · '
                      '${widget.accountLabels[tx.accountId] ?? 'Akun'} · '
                      '${widget.categoryNames[tx.categoryId] ?? '—'}',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                    trailing: Text(
                      formatRupiah(tx.totalAmount),
                      style: TextStyle(color: color, fontWeight: FontWeight.w700),
                    ),
                  ),
                );
              },
            ),
    );
  }
}