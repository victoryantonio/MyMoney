/// Ambil kurs mata uang dari open.er-api.com (gratis, tanpa API key).
///
/// Dipakai form transaksi saat user memilih mata uang non-IDR: hasilnya
/// dipakai menghitung `total_amount` (IDR) = nominal × kurs, lalu dikirim
/// ke backend beserta `original_currency` + `exchange_rate`.
library;

import 'dart:convert';

import 'package:http/http.dart' as http;

/// 1 unit [from] berapa unit [to] (mis. fetchExchangeRate('USD', 'IDR')
/// → ±16250). Melempar [ExchangeRateException] bila gagal.
Future<double> fetchExchangeRate(String from, String to) async {
  final uri = Uri.parse('https://open.er-api.com/v6/latest/$from');
  final resp = await http
      .get(uri)
      .timeout(const Duration(seconds: 10));
  if (resp.statusCode != 200) {
    throw ExchangeRateException(
      'Gagal ambil kurs (HTTP ${resp.statusCode})',
    );
  }
  final dynamic raw = jsonDecode(resp.body);
  final data = raw is Map<String, dynamic> ? raw : const <String, dynamic>{};
  if (data['result'] != 'success') {
    throw ExchangeRateException(
      'Gagal ambil kurs: ${data['result'] ?? 'respon tidak dikenal'}',
    );
  }
  final rates = data['rates'];
  if (rates is! Map<String, dynamic>) {
    throw ExchangeRateException('Data kurs tidak tersedia');
  }
  final rate = rates[to];
  if (rate is! num) {
    throw ExchangeRateException('Kurs $from → $to tidak ditemukan');
  }
  return rate.toDouble();
}

class ExchangeRateException implements Exception {
  ExchangeRateException(this.message);

  final String message;

  @override
  String toString() => message;
}
