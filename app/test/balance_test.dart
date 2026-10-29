// Unit test perhitungan saldo dashboard (Req 6 — filter akun).
//
// Regresi: kartu "Total Balance" dulu selalu menjumlah SEMUA akun, sehingga
// angkanya tidak berubah saat filter akun diganti.

import 'package:flutter_test/flutter_test.dart';

import 'package:mymoney_app/core/balance.dart';
import 'package:mymoney_app/models/transaction_models.dart';

AccountModel _account(String id, String name, double balance,
        {String type = 'bank'}) =>
    AccountModel(
      id: id,
      accountName: name,
      accountType: type,
      initialBalance: balance,
      currentBalance: balance,
      netBalance: balance,
      isActive: true,
    );

final _accounts = [
  _account('a1', 'SeaBank', 1000000),
  _account('a2', 'BCA', 250000),
  _account('a3', 'Dompet', 50000, type: 'cash'),
];

void main() {
  group('totalBalanceFor', () {
    test('null (tanpa filter) menjumlah semua akun', () {
      expect(totalBalanceFor(_accounts, null), 1300000);
    });

    test('subset akun hanya menjumlah akun terpilih', () {
      expect(totalBalanceFor(_accounts, {'a1'}), 1000000);
      expect(totalBalanceFor(_accounts, {'a1', 'a3'}), 1050000);
    });

    test('himpunan kosong (unselect all) menghasilkan 0', () {
      expect(totalBalanceFor(_accounts, <String>{}), 0);
    });

    test('id yang tidak dikenal diabaikan', () {
      expect(totalBalanceFor(_accounts, {'tidak-ada'}), 0);
    });

    test('daftar akun kosong menghasilkan 0', () {
      expect(totalBalanceFor(const <AccountModel>[], null), 0);
    });
  });

  group('balanceScopeLabel', () {
    test('null saat semua akun ditampilkan', () {
      expect(balanceScopeLabel(_accounts, null), isNull);
    });

    test('menyebut nama akun saat hanya satu yang dipilih', () {
      expect(balanceScopeLabel(_accounts, {'a1'}), 'SeaBank · Bank');
      expect(balanceScopeLabel(_accounts, {'a3'}), 'Dompet');
    });

    test('menyebut jumlah saat lebih dari satu akun dipilih', () {
      expect(balanceScopeLabel(_accounts, {'a1', 'a2'}), '2 akun terpilih');
    });

    test('menyatakan tidak ada akun dipilih', () {
      expect(balanceScopeLabel(_accounts, <String>{}), 'Tidak ada akun dipilih');
    });
  });
}
