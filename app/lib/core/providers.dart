/// Provider Riverpod global.
///
/// `themeControllerProvider` wajib di-override di `main()` (nilainya di-load
/// async dari shared_preferences sebelum runApp). Ketika di-baca tanpa
/// override (mis. mode setup / unit test) akan throw dengan pesan jelas.
library;

import 'package:flutter_riverpod/legacy.dart' show ChangeNotifierProvider;

import 'theme_controller.dart';

final themeControllerProvider =
    ChangeNotifierProvider<ThemeController>((ref) {
  throw UnimplementedError(
    'themeControllerProvider harus di-override di main() sebelum runApp',
  );
});
