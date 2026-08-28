/// Format utilitas untuk nilai uang & tanggal (locale ID).
///
/// Uang: single currency (default Rupiah) — simbol mengikuti
/// `CurrencyController`; tanpa desimal untuk tampilan ringkas. Tanggal
/// mengikuti konvensi Indonesia (dd MMM yyyy / EEE, d MMM yyyy).
library;

import 'currency_controller.dart';

/// Simbol mata uang aktif; fallback 'Rp' bila controller belum di-load
/// (mis. unit test).
String get currencySymbol => CurrencyController.instance?.symbol ?? 'Rp';

String formatMoney(num value) {
  final negatif = value < 0;
  final abs = value.abs().toStringAsFixed(0);
  final buffer = StringBuffer();
  for (var i = 0; i < abs.length; i++) {
    final dariBelakang = abs.length - i;
    buffer.write(abs[i]);
    if (dariBelakang > 1 && (dariBelakang - 1) % 3 == 0) buffer.write('.');
  }
  return '${negatif ? '-' : ''}$currencySymbol$buffer';
}

/// Alias historis — tetap dipakai banyak layar; simbol mengikuti currency aktif.
String formatRupiah(num value) => formatMoney(value);

String formatRupiahSigned(num value) {
  final s = formatRupiah(value);
  if (value > 0) return '+$s';
  return s;
}

const _bulan = [
  'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
  'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des',
];

const _hari = ['Senin', 'Selasa', 'Rabu', 'Kamis', 'Jumat', 'Sabtu', 'Minggu'];

/// "12 Agu" untuk label sumbu chart (ringkas).
String formatDateShort(DateTime d) => '${d.day} ${_bulan[d.month - 1]}';

/// "12 Agu" — label sumbu dengan tahun bila berbeda dari tahun sekarang
/// (tanggal dulu, baru bulan — sesuai preferensi pengguna).
String formatAxisLabel(DateTime d, {DateTime? today}) {
  final t = today ?? DateTime.now();
  if (d.year != t.year) return '${d.day} ${_bulan[d.month - 1]} ${d.year}';
  return '${d.day} ${_bulan[d.month - 1]}';
}

/// "Sen, 12 Agu 2026" untuk panel detail / header tanggal.
String formatDateDetail(DateTime d) =>
    '${_hari[d.weekday - 1]}, ${d.day} ${_bulan[d.month - 1]} ${d.year}';
