// Unit test format utilitas (Fase 4) — murni, tanpa network/plugin.

import 'package:flutter_test/flutter_test.dart';

import 'package:mymoney_app/core/format.dart';

void main() {
  group('formatRupiah', () {
    test('nol', () {
      expect(formatRupiah(0), 'Rp0');
    });

    test('ribuan', () {
      expect(formatRupiah(40000), 'Rp40.000');
    });

    test('jutaan', () {
      expect(formatRupiah(100000000), 'Rp100.000.000');
    });

    test('negatif', () {
      expect(formatRupiah(-25000), '-Rp25.000');
    });
  });

  group('formatRupiahSigned', () {
    test('positif ditambah tanda +', () {
      expect(formatRupiahSigned(20000), '+Rp20.000');
    });

    test('negatif tetap minus', () {
      expect(formatRupiahSigned(-20000), '-Rp20.000');
    });
  });

  group('format tanggal', () {
    test('formatDateShort', () {
      expect(formatDateShort(DateTime(2026, 8, 12)), '12 Agu');
    });

    test('formatDateDetail', () {
      // 2026-08-12 adalah hari Rabu.
      expect(formatDateDetail(DateTime(2026, 8, 12)), 'Rab, 12 Agu');
    });
  });
}
