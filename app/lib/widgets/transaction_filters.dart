/// Filter & sortir bersama untuk daftar transaksi (tab Transaksi dan daftar
/// yang dibuka dari dashboard Income/Expense/Net).
///
/// - Filter multi-checklist: akun + kategori (seperti filter akun di
///   dashboard).
/// - Sortir: tanggal terbaru/terlama, nominal terbesar/terkecil.
/// Bottom sheet di sini mengembalikan pilihan; layar pemanggil yang
/// menerapkan penyaringan/sortir pada datanya.
library;

import 'package:flutter/material.dart';

import '../models/transaction_models.dart';

/// Urutan tampil transaksi.
enum TransactionSort { newest, oldest, largest, smallest }

extension TransactionSortLabel on TransactionSort {
  String get label => switch (this) {
        TransactionSort.newest => 'Tanggal terbaru',
        TransactionSort.oldest => 'Tanggal terlama',
        TransactionSort.largest => 'Nominal terbesar',
        TransactionSort.smallest => 'Nominal terkecil',
      };
}

/// Hasil pilihan filter dari bottom sheet.
class TransactionFilterResult {
  const TransactionFilterResult({
    required this.accountIds,
    required this.categoryIds,
  });

  final Set<String> accountIds;
  final Set<String> categoryIds;

  bool get isEmpty => accountIds.isEmpty && categoryIds.isEmpty;
}

/// Terapkan sortir pada daftar (tanpa mengubah list asal).
List<TransactionModel> sortTransactions(
  List<TransactionModel> txs,
  TransactionSort sort,
) {
  final result = [...txs];
  result.sort((a, b) {
    switch (sort) {
      case TransactionSort.newest:
        return b.transactionDate.compareTo(a.transactionDate);
      case TransactionSort.oldest:
        return a.transactionDate.compareTo(b.transactionDate);
      case TransactionSort.largest:
        return b.totalAmount.compareTo(a.totalAmount);
      case TransactionSort.smallest:
        return a.totalAmount.compareTo(b.totalAmount);
    }
  });
  return result;
}

/// Terapkan filter akun + kategori (multi-checklist; kosong = semua).
List<TransactionModel> filterTransactions(
  List<TransactionModel> txs, {
  Set<String> accountIds = const {},
  Set<String> categoryIds = const {},
}) {
  var result = txs;
  if (accountIds.isNotEmpty) {
    result = result
        .where((tx) => accountIds.contains(tx.accountId))
        .toList();
  }
  if (categoryIds.isNotEmpty) {
    result = result
        .where((tx) => tx.categoryId != null && categoryIds.contains(tx.categoryId))
        .toList();
  }
  return result;
}

/// Tampilkan bottom sheet filter (akun + kategori, multi-checklist).
///
/// Mengembalikan pilihan baru, atau `null` jika user menutup tanpa
/// "Terapkan". Pilihan saat ini (`selectedAccountIds`/`selectedCategoryIds`)
/// dipakai sebagai nilai awal.
Future<TransactionFilterResult?> showTransactionFilterSheet({
  required BuildContext context,
  required List<AccountModel> accounts,
  required List<CategoryModel> categories,
  Set<String> selectedAccountIds = const {},
  Set<String> selectedCategoryIds = const {},
}) {
  final selectedAccounts = {...selectedAccountIds};
  final selectedCategories = {...selectedCategoryIds};

  return showModalBottomSheet<TransactionFilterResult>(
    context: context,
    isScrollControlled: true,
    showDragHandle: true,
    builder: (context) {
      return StatefulBuilder(
        builder: (context, setSheetState) {
          void toggleAccount(String id) {
            setSheetState(() {
              if (!selectedAccounts.add(id)) selectedAccounts.remove(id);
            });
          }

          void toggleCategory(String id) {
            setSheetState(() {
              if (!selectedCategories.add(id)) selectedCategories.remove(id);
            });
          }

          return DraggableScrollableSheet(
            expand: false,
            initialChildSize: 0.72,
            maxChildSize: 0.92,
            builder: (context, scrollController) => Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
                  child: Row(
                    children: [
                      Text(
                        'Filter',
                        style: Theme.of(context)
                            .textTheme
                            .titleMedium
                            ?.copyWith(fontWeight: FontWeight.w700),
                      ),
                      const Spacer(),
                      TextButton(
                        onPressed: () => setSheetState(() {
                          selectedAccounts.clear();
                          selectedCategories.clear();
                        }),
                        child: const Text('Reset'),
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: ListView(
                    controller: scrollController,
                    padding: const EdgeInsets.fromLTRB(20, 0, 20, 16),
                    children: [
                      _FilterSection(
                        icon: Icons.account_balance_wallet_outlined,
                        title: 'Akun',
                        children: [
                          for (final account in accounts)
                            FilterChip(
                              label: Text(account.label),
                              selected: selectedAccounts.contains(account.id),
                              onSelected: (_) => toggleAccount(account.id),
                            ),
                        ],
                      ),
                      const SizedBox(height: 20),
                      _FilterSection(
                        icon: Icons.category_outlined,
                        title: 'Kategori',
                        children: [
                          for (final category in categories)
                            FilterChip(
                              label: Text(category.name),
                              selected: selectedCategories.contains(category.id),
                              onSelected: (_) => toggleCategory(category.id),
                            ),
                        ],
                      ),
                    ],
                  ),
                ),
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
                  child: SizedBox(
                    width: double.infinity,
                    child: FilledButton(
                      onPressed: () => Navigator.of(context).pop(
                        TransactionFilterResult(
                          accountIds: selectedAccounts,
                          categoryIds: selectedCategories,
                        ),
                      ),
                      child: const Text('Terapkan'),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      );
    },
  );
}

class _FilterSection extends StatelessWidget {
  const _FilterSection({
    required this.icon,
    required this.title,
    required this.children,
  });

  final IconData icon;
  final String title;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Icon(
              icon,
              size: 18,
              color: Theme.of(context).colorScheme.onSurfaceVariant,
            ),
            const SizedBox(width: 8),
            Text(
              title,
              style: Theme.of(context)
                  .textTheme
                  .titleSmall
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: children.isEmpty
              ? [
                  Text(
                    'Belum ada data',
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ]
              : children,
        ),
      ],
    );
  }
}
