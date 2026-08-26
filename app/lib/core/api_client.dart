/// HTTP client ke backend FastAPI (REST, Supabase JWT di header).
///
/// Prinsip (ARCHITECTURE §3.3): Flutter = thin client — semua logic bisnis
/// tetap di backend; di sini hanya GET data report untuk dashboard.
library;

import 'package:dio/dio.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../models/report_models.dart';
import 'config.dart';

class ApiException implements Exception {
  const ApiException(this.message);
  final String message;

  @override
  String toString() => message;
}

class ApiClient {
  ApiClient._(this._dio);

  final Dio _dio;

  static ApiClient? _instance;

  /// Singleton per aplikasi; `supabase` dipakai untuk mengambil access token
  /// terbaru (auto-refresh oleh supabase_flutter) setiap request.
  static ApiClient instance(SupabaseClient supabase) =>
      _instance ??= ApiClient._(_buildDio(supabase));

  static Dio _buildDio(SupabaseClient supabase) {
    final dio = Dio(
      BaseOptions(
        baseUrl: AppConfig.appBaseUrl,
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 30),
        headers: {'Content-Type': 'application/json'},
      ),
    );
    dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) {
          final token = supabase.auth.currentSession?.accessToken;
          if (token != null) {
            options.headers['Authorization'] = 'Bearer $token';
          }
          handler.next(options);
        },
      ),
    );
    return dio;
  }

  /// GET /api/reports/summary?period=... → total income/expense/net + kategori.
  Future<ReportSummary> fetchSummary({String period = 'month'}) async {
    final data = await _get('/api/reports/summary', {'period': period});
    return ReportSummary.fromJson(data);
  }

  /// GET /api/reports/trend?period=... → deret harian untuk line chart.
  Future<ReportTrend> fetchTrend({String period = 'month'}) async {
    final data = await _get('/api/reports/trend', {'period': period});
    return ReportTrend.fromJson(data);
  }

  Future<Map<String, dynamic>> _get(
    String path,
    Map<String, dynamic> query,
  ) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>(
        path,
        queryParameters: query,
      );
      return res.data ?? const {};
    } on DioException catch (e) {
      throw ApiException(_dioMessage(e));
    }
  }

  static String _dioMessage(DioException e) {
    final status = e.response?.statusCode;
    if (e.type == DioExceptionType.connectionTimeout ||
        e.type == DioExceptionType.connectionError) {
      return 'Tidak dapat terhubung ke server (${AppConfig.appBaseUrl})';
    }
    if (status == 401) return 'Sesi berakhir — silakan login ulang';
    if (status != null) return 'Server error ($status)';
    return e.message ?? 'Network error';
  }
}
