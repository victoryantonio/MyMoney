/// Kontrol tema aplikasi (System / Light / Dark) — persisten via
/// shared_preferences (setara DataStoreThemeStore di v1 Kotlin).
library;

import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class ThemeController extends ChangeNotifier {
  ThemeController._(this._prefs);

  static const _key = 'theme_mode';

  final SharedPreferences _prefs;

  ThemeMode _mode = ThemeMode.system;
  ThemeMode get mode => _mode;

  /// Load mode tersimpan (default: system).
  static Future<ThemeController> load() async {
    final prefs = await SharedPreferences.getInstance();
    final c = ThemeController._(prefs);
    switch (prefs.getString(_key)) {
      case 'light':
        c._mode = ThemeMode.light;
      case 'dark':
        c._mode = ThemeMode.dark;
      default:
        c._mode = ThemeMode.system;
    }
    return c;
  }

  Future<void> setMode(ThemeMode mode) async {
    if (mode == _mode) return;
    _mode = mode;
    notifyListeners();
    final stored = switch (mode) {
      ThemeMode.light => 'light',
      ThemeMode.dark => 'dark',
      ThemeMode.system => 'system',
    };
    await _prefs.setString(_key, stored);
  }
}
