/// Format utilitas untuk nilai uang & tanggal (locale ID).
///
/// IDR tanpa desimal untuk tampilan ringkas; tanggal mengikuti
/// konvensi Indonesia (dd MMM yyyy / EEE, d MMM).
library;

String formatRupiah(num value) {
  final negatif = value < 0;
  final abs = value.abs().toStringAsFixed(0);
  final buffer = StringBuffer();
  for (var i = 0; i < abs.length; i++) {
    final dariBelakang = abs.length - i;
    buffer.write(abs[i]);
    if (dariBelakang > 1 && (dariBelakang - 1) % 3 == 0) buffer.write('.');
  }
  return '${negatif ? '-' : ''}Rp$buffer';
}

String formatRupiahSigned(num value) {
  final s = formatRupiah(value);
  if (value > 0) return '+$s';
  return s;
}

const _bulan = [
  'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
  'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des',
];

const _hari = ['Sen', 'Sel', 'Rab', 'Kam', 'Jum', 'Sab', 'Min'];

/// "12 Agu" untuk label sumbu chart (ringkas).
String formatDateShort(DateTime d) => '${d.day} ${_bulan[d.month - 1]}';

/// "Agu 12" — label sumbu dengan tahun bila berbeda dari tahun sekarang.
String formatAxisLabel(DateTime d, {DateTime? today}) {
  final t = today ?? DateTime.now();
  if (d.year != t.year) return '${_bulan[d.month - 1]} ${d.year}';
  return '${_bulan[d.month - 1]} ${d.day}';
}

/// "Sen, 12 Agu" untuk panel detail.
String formatDateDetail(DateTime d) =>
    '${_hari[d.weekday - 1]}, ${d.day} ${_bulan[d.month - 1]}';
