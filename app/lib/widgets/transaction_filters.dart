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

  /// Nilai query param `sort` untuk backend (server-side sorting).
  String get apiValue => switch (this) {
        TransactionSort.newest => 'newest',
        TransactionSort.oldest => 'oldest',
        TransactionSort.largest => 'largest',
        TransactionSort.smallest => 'smallest',
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

/// Sentinel ID khusus untuk jenis 'transfer' (tidak punya categoryId).
const _kTransferSentinelId = '__transfer__';

/// Terapkan filter akun + kategori (multi-checklist; kosong = semua).
/// Transaksi 'transfer' (categoryId == null) dicocokkan dengan sentinel ID
/// `__transfer__` agar bisa disertakan / dikecualikan lewat filter kategori.
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
    result = result.where((tx) {
      if (tx.type == 'transfer') {
        // Transfer tidak punya categoryId — cocokkan dgn sentinel
        return categoryIds.contains(_kTransferSentinelId);
      }
      return tx.categoryId != null && categoryIds.contains(tx.categoryId);
    }).toList();
  }
  return result;
}

// ── Grup pohon untuk filter (akun per tipe, kategori per tipe) ──────────────

/// Urutan tampil grup akun: Cash → Bank → E-Wallet.
const accountTypeOrder = ['cash', 'bank', 'ewallet'];

/// Urutan tampil grup kategori: Pengeluaran → Pemasukan.
const categoryTypeOrder = ['expense', 'income'];

String accountTypeLabel(String type) => switch (type) {
      'cash' => 'Cash',
      'bank' => 'Bank',
      'ewallet' => 'E-Wallet',
      _ => type,
    };

String categoryTypeLabel(String type) => switch (type) {
      'expense' => 'Pengeluaran',
      'income' => 'Pemasukan',
      _ => type,
    };

IconData accountTypeIcon(String type) => switch (type) {
      'cash' => Icons.payments_outlined,
      'bank' => Icons.account_balance_outlined,
      'ewallet' => Icons.phone_android_outlined,
      _ => Icons.account_balance_wallet_outlined,
    };

IconData categoryTypeIcon(String type) => switch (type) {
      'expense' => Icons.arrow_downward,
      'income' => Icons.arrow_upward,
      _ => Icons.category_outlined,
    };

/// Kelompokkan akun per tipe (Cash → Bank → E-Wallet), nama ascending.
/// Hanya tipe yang punya data yang disertakan.
Map<String, List<AccountModel>> groupAccountsByType(
  List<AccountModel> accounts,
) {
  final groups = <String, List<AccountModel>>{
    for (final type in accountTypeOrder) type: <AccountModel>[],
  };
  for (final account in accounts) {
    groups.putIfAbsent(account.accountType, () => []).add(account);
  }
  for (final list in groups.values) {
    list.sort((a, b) => a.accountName
        .toLowerCase()
        .compareTo(b.accountName.toLowerCase()));
  }
  return {
    for (final type in accountTypeOrder)
      if (groups[type]!.isNotEmpty) type: groups[type]!,
  };
}

/// Kelompokkan kategori per tipe (Pengeluaran → Pemasukan), nama ascending.
/// Kategori dengan nama sama tapi tipe beda (mis. "Other" expense vs income)
/// kini terpisah jelas di grupnya masing-masing.
Map<String, List<CategoryModel>> groupCategoriesByType(
  List<CategoryModel> categories,
) {
  final groups = <String, List<CategoryModel>>{
    for (final type in categoryTypeOrder) type: <CategoryModel>[],
  };
  for (final category in categories) {
    groups.putIfAbsent(category.type, () => []).add(category);
  }
  for (final list in groups.values) {
    list.sort((a, b) =>
        a.name.toLowerCase().compareTo(b.name.toLowerCase()));
  }
  return {
    for (final type in categoryTypeOrder)
      if (groups[type]!.isNotEmpty) type: groups[type]!,
  };
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
                      Text(
                        'Pilih grup untuk memilih semua, atau centang per item.',
                        style: Theme.of(context).textTheme.bodySmall?.copyWith(
                              color: Theme.of(context).colorScheme.onSurfaceVariant,
                            ),
                      ),
                      const SizedBox(height: 12),
                      for (final entry in groupAccountsByType(accounts).entries) ...[
                        _FilterGroup(
                          icon: accountTypeIcon(entry.key),
                          title: accountTypeLabel(entry.key),
                          selectedCount: entry.value
                              .where((a) => selectedAccounts.contains(a.id))
                              .length,
                          totalCount: entry.value.length,
                          onToggleAll: () => setSheetState(() {
                            final ids = entry.value.map((a) => a.id).toList();
                            final allSelected = ids.every(selectedAccounts.contains);
                            if (allSelected) {
                              selectedAccounts.removeAll(ids);
                            } else {
                              selectedAccounts.addAll(ids);
                            }
                          }),
                          children: [
                            for (final account in entry.value)
                              FilterChip(
                                // Grup sudah menunjukkan tipe (Cash/Bank/
                                // E-Wallet) di header → cukup nama akun.
                                label: Text(account.accountName),
                                selected: selectedAccounts.contains(account.id),
                                onSelected: (_) => toggleAccount(account.id),
                              ),
                          ],
                        ),
                        const SizedBox(height: 20),
                      ],
                      for (final entry in groupCategoriesByType(categories).entries) ...[
                        _FilterGroup(
                          icon: categoryTypeIcon(entry.key),
                          title: categoryTypeLabel(entry.key),
                          selectedCount: entry.value
                              .where((c) => selectedCategories.contains(c.id))
                              .length,
                          totalCount: entry.value.length,
                          onToggleAll: () => setSheetState(() {
                            final ids = entry.value.map((c) => c.id).toList();
                            final allSelected = ids.every(selectedCategories.contains);
                            if (allSelected) {
                              selectedCategories.removeAll(ids);
                            } else {
                              selectedCategories.addAll(ids);
                            }
                          }),
                          children: [
                            for (final category in entry.value)
                              FilterChip(
                                label: Text(category.name),
                                selected: selectedCategories.contains(category.id),
                                onSelected: (_) => toggleCategory(category.id),
                              ),
                          ],
                        ),
                        const SizedBox(height: 20),
                      ],
                      // ── Grup Transfer (sentinel, tidak pakai kategori) ──
                      _FilterGroup(
                        icon: Icons.swap_horiz,
                        title: 'Transfer',
                        selectedCount:
                            selectedCategories.contains(_kTransferSentinelId) ? 1 : 0,
                        totalCount: 1,
                        onToggleAll: () => setSheetState(() {
                          if (selectedCategories.contains(_kTransferSentinelId)) {
                            selectedCategories.remove(_kTransferSentinelId);
                          } else {
                            selectedCategories.add(_kTransferSentinelId);
                          }
                        }),
                        children: [
                          FilterChip(
                            label: const Text('Transfer antar akun'),
                            selected:
                                selectedCategories.contains(_kTransferSentinelId),
                            onSelected: (_) => setSheetState(() {
                              if (selectedCategories
                                  .contains(_kTransferSentinelId)) {
                                selectedCategories.remove(_kTransferSentinelId);
                              } else {
                                selectedCategories.add(_kTransferSentinelId);
                              }
                            }),
                          ),
                        ],
                      ),
                      const SizedBox(height: 20),
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

/// Satu grup pohon di bottom sheet filter: header (icon + nama + checkbox
/// select-all dengan indikator sebagian terpilih) + daftar chip item.
class _FilterGroup extends StatelessWidget {
  const _FilterGroup({
    required this.icon,
    required this.title,
    required this.selectedCount,
    required this.totalCount,
    required this.onToggleAll,
    required this.children,
  });

  final IconData icon;
  final String title;
  final int selectedCount;
  final int totalCount;
  final VoidCallback onToggleAll;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final textTheme = Theme.of(context).textTheme;
    final checked = selectedCount > 0 && selectedCount == totalCount;
    final indeterminate = selectedCount > 0 && selectedCount < totalCount;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        InkWell(
          onTap: onToggleAll,
          borderRadius: BorderRadius.circular(8),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
            child: Row(
              children: [
                Icon(icon, size: 18, color: scheme.onSurfaceVariant),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    title,
                    style: textTheme.titleSmall
                        ?.copyWith(fontWeight: FontWeight.w700),
                  ),
                ),
                Text(
                  totalCount > 0 ? '$selectedCount/$totalCount' : '',
                  style: textTheme.bodySmall?.copyWith(color: scheme.onSurfaceVariant),
                ),
                Checkbox(
                  value: indeterminate ? null : checked,
                  tristate: true,
                  onChanged: (_) => onToggleAll(),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 6),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: children.isEmpty
              ? [
                  Text(
                    'Belum ada data',
                    style: textTheme.bodySmall?.copyWith(
                      color: scheme.onSurfaceVariant,
                    ),
                  ),
                ]
              : children,
        ),
      ],
    );
  }
}
