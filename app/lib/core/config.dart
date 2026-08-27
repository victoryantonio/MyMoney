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

  /// Fallback default (public-by-design) agar app langsung jalan tanpa
  /// --dart-define — memperbaiki SocketException "No address associated with
  /// hostname" (errno 7 = DNS gagal karena URL kosong saat build tanpa config).
  static const supabaseUrl = String.fromEnvironment(
    'SUPABASE_URL',
    defaultValue: 'https://fqjkqcigjeyooejcgbrk.supabase.co',
  );
  static const supabaseAnonKey = String.fromEnvironment(
    'SUPABASE_ANON_KEY',
    defaultValue:
        'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZxamtxY2lnamV5b29lamNnYnJrIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODc3NDIyMjAsImV4cCI6MjEwMzMxODIyMH0.KTCG_IlHAZqvydlWMQZL1B7THscRLXrZitnhpGUVrVg',
  );
  static const appBaseUrl = String.fromEnvironment(
    'APP_BASE_URL',
    // HTTPS via Cloudflare Tunnel (Android 9+ memblokir HTTP cleartext default).
    defaultValue: 'https://api.mymoneyofficial.online',
  );

  static bool get isConfigured =>
      supabaseUrl.isNotEmpty && supabaseAnonKey.isNotEmpty;
}
