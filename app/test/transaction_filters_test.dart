// Unit test untuk pengelompokan filter pohon (akun per tipe, kategori per
// tipe) di transaction_filters.dart — memastikan grup berurutan benar,
// nama ascending, dan nama kategori duplikat (expense vs income) terpisah.

import 'package:flutter_test/flutter_test.dart';

import 'package:mymoney_app/models/transaction_models.dart';
import 'package:mymoney_app/widgets/transaction_filters.dart';

AccountModel _account(String id, String name, String type) => AccountModel(
      id: id,
      accountName: name,
      accountType: type,
      initialBalance: 0,
      currentBalance: 0,
      netBalance: 0,
      isActive: true,
    );

CategoryModel _category(String id, String name, String type) => CategoryModel(
      id: id,
      name: name,
      type: type,
      isDefault: false,
      isActive: true,
    );

void main() {
  group('groupAccountsByType', () {
    test('kelompok Cash → Bank → E-Wallet, nama ascending', () {
      final accounts = [
        _account('1', 'GoPay', 'ewallet'),
        _account('2', 'CIMB Niaga', 'bank'),
        _account('3', 'BCA', 'bank'),
        _account('4', 'DANA', 'ewallet'),
        _account('5', 'Cash', 'cash'),
      ];
      final groups = groupAccountsByType(accounts);

      expect(groups.keys.toList(), ['cash', 'bank', 'ewallet']);
      expect(groups['cash']!.map((a) => a.accountName), ['Cash']);
      expect(groups['bank']!.map((a) => a.accountName), ['BCA', 'CIMB Niaga']);
      expect(groups['ewallet']!.map((a) => a.accountName), ['DANA', 'GoPay']);
    });

    test('tipe tanpa data tidak disertakan', () {
      final accounts = [_account('1', 'BCA', 'bank')];
      final groups = groupAccountsByType(accounts);
      expect(groups.keys.toList(), ['bank']);
    });
  });

  group('groupCategoriesByType', () {
    test('Pengeluaran dulu, lalu Pemasukan; nama ascending', () {
      final categories = [
        _category('1', 'Other', 'income'),
        _category('2', 'Transfer', 'expense'),
        _category('3', 'Other', 'expense'),
        _category('4', 'Food', 'expense'),
        _category('5', 'Transfer', 'income'),
      ];
      final groups = groupCategoriesByType(categories);

      expect(groups.keys.toList(), ['expense', 'income']);
      // Duplikat "Other"/"Transfer" kini terpisah per grup.
      expect(groups['expense']!.map((c) => c.name), ['Food', 'Other', 'Transfer']);
      expect(groups['income']!.map((c) => c.name), ['Other', 'Transfer']);
    });

    test('tipe tanpa data tidak disertakan', () {
      final categories = [_category('1', 'Food', 'expense')];
      final groups = groupCategoriesByType(categories);
      expect(groups.keys.toList(), ['expense']);
    });
  });

  group('label', () {
    test('accountTypeLabel & categoryTypeLabel ramah', () {
      expect(accountTypeLabel('cash'), 'Cash');
      expect(accountTypeLabel('bank'), 'Bank');
      expect(accountTypeLabel('ewallet'), 'E-Wallet');
      expect(categoryTypeLabel('expense'), 'Pengeluaran');
      expect(categoryTypeLabel('income'), 'Pemasukan');
    });
  });
}
