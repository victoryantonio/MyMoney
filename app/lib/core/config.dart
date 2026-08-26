/// Build-time configuration (Fase 4).
///
/// Semua nilai di-inject saat build/run:
///   flutter run --dart-define=SUPABASE_URL=... \
///     --dart-define=SUPABASE_ANON_KEY=... \
///     --dart-define=APP_BASE_URL=...
///
/// `SUPABASE_URL` & `SUPABASE_ANON_KEY` adalah public-by-design (client-safe).
/// `APP_BASE_URL` = URL publik backend FastAPI (bukan Supabase).
library;

class AppConfig {
  AppConfig._();

  static const supabaseUrl = String.fromEnvironment('SUPABASE_URL');
  static const supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY');
  static const appBaseUrl = String.fromEnvironment(
    'APP_BASE_URL',
    defaultValue: 'http://localhost:8000',
  );

  static bool get isConfigured =>
      supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty;
}
