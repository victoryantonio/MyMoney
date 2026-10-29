// Perhitungan saldo dashboard.
//
// Dipisah dari widget supaya bisa diuji langsung: kartu "Total Balance" harus
// mengikuti filter akun yang aktif, sama seperti kartu Income/Expense/Trend.

import '../models/transaction_models.dart';

/// Total saldo akun yang sedang difilter.
///
/// - `selectedAccountIds == null` → semua akun (tanpa filter).
/// - Himpunan kosong → 0 (user meng-unselect semua akun).
/// - Selain itu → hanya akun yang id-nya ada di himpunan tersebut.
double totalBalanceFor(
  Iterable<AccountModel> accounts,
  Set<String>? selectedAccountIds,
) {
  if (selectedAccountIds == null) {
    return accounts.fold(0, (sum, account) => sum + account.currentBalance);
  }
  return accounts
      .where((account) => selectedAccountIds.contains(account.id))
      .fold(0, (sum, account) => sum + account.currentBalance);
}

/// Keterangan cakupan kartu saldo; null berarti seluruh akun ditampilkan.
String? balanceScopeLabel(
  Iterable<AccountModel> accounts,
  Set<String>? selectedAccountIds,
) {
  if (selectedAccountIds == null) return null;
  if (selectedAccountIds.isEmpty) return 'Tidak ada akun dipilih';
  final selected =
      accounts.where((a) => selectedAccountIds.contains(a.id)).toList();
  if (selected.length == 1) return selected.first.label;
  return '${selected.length} akun terpilih';
}
