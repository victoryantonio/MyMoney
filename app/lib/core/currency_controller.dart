/// Kontrol mata uang aplikasi — single currency, default Rupiah (IDR).
///
/// Persisten via shared_preferences (pola sama seperti `ThemeController`).
/// Seluruh format uang di `core/format.dart` membaca simbol dari
/// `CurrencyController.instance`; `main()` memanggil `load()` sebelum
/// `runApp` sehingga instance statis tersedia untuk fungsi format non-widget.
library;

import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

class Currency {
  const Currency({
    required this.code,
    required this.symbol,
    required this.name,
  });

  final String code;
  final String symbol;
  final String name;
}

/// Daftar mata uang yang didukung (single currency — user memilih SATU).
const List<Currency> supportedCurrencies = [
  Currency(code: 'IDR', symbol: 'Rp', name: 'Rupiah Indonesia'),
  Currency(code: 'USD', symbol: r'$', name: 'US Dollar'),
  Currency(code: 'EUR', symbol: '€', name: 'Euro'),
  Currency(code: 'SGD', symbol: r'S$', name: 'Singapore Dollar'),
  Currency(code: 'MYR', symbol: 'RM', name: 'Malaysian Ringgit'),
  Currency(code: 'GBP', symbol: '£', name: 'British Pound'),
  Currency(code: 'JPY', symbol: '¥', name: 'Japanese Yen'),
];

class CurrencyController extends ChangeNotifier {
  CurrencyController._(this._prefs);

  static const _key = 'currency_code';

  /// Instance statis untuk fungsi format non-widget. Null sebelum `load()`
  /// (mis. unit test) → pemanggil harus fallback ke 'Rp'.
  static CurrencyController? _instance;
  static CurrencyController? get instance => _instance;

  final SharedPreferences _prefs;

  Currency _currency = supportedCurrencies.first; // default IDR
  Currency get currency => _currency;
  String get symbol => _currency.symbol;

  /// Load mata uang tersimpan (default: Rupiah) dan pasang instance statis.
  static Future<CurrencyController> load() async {
    final prefs = await SharedPreferences.getInstance();
    final controller = CurrencyController._(prefs);
    final code = prefs.getString(_key);
    if (code != null) {
      for (final currency in supportedCurrencies) {
        if (currency.code == code) {
          controller._currency = currency;
          break;
        }
      }
    }
    _instance = controller;
    return controller;
  }

  Future<void> setCurrency(Currency currency) async {
    if (currency.code == _currency.code) return;
    _currency = currency;
    notifyListeners();
    await _prefs.setString(_key, currency.code);
  }
}
