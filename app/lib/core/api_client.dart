/// HTTP client ke backend FastAPI (REST, Supabase JWT di header).
///
/// Prinsip (ARCHITECTURE §3.3): Flutter = thin client — semua logic bisnis
/// tetap di backend; di sini hanya GET data report untuk dashboard.
library;

import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:supabase_flutter/supabase_flutter.dart' hide MultipartFile;

import '../models/report_models.dart';
import '../models/transaction_models.dart';
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
  /// Saat `period == 'custom'`, kirim `start`/`end` ISO datetime untuk rentang kustom.
  Future<ReportSummary> fetchSummary({
    String period = 'month',
    String? start,
    String? end,
  }) async {
    final query = <String, dynamic>{'period': period};
    if (period == 'custom' && start != null && end != null) {
      query['start'] = start;
      query['end'] = end;
    }
    final data = await _get('/api/reports/summary', query);
    return ReportSummary.fromJson(data);
  }

  /// GET /api/reports/trend?period=... → deret harian untuk line chart.
  /// Saat `period == 'custom'`, kirim `start`/`end` ISO datetime untuk rentang kustom.
  Future<ReportTrend> fetchTrend({
    String period = 'month',
    String? start,
    String? end,
  }) async {
    final query = <String, dynamic>{'period': period};
    if (period == 'custom' && start != null && end != null) {
      query['start'] = start;
      query['end'] = end;
    }
    final data = await _get('/api/reports/trend', query);
    return ReportTrend.fromJson(data);
  }

  // ── Scan Nota (OCR receipt) ────────────────────────────────────────────────

  /// POST /api/receipts/ocr — upload foto nota → hasil parse terstruktur.
  Future<ParsedReceipt> parseReceipt(Uint8List bytes, String filename) async {
    try {
      final form = FormData.fromMap({
        'file': MultipartFile.fromBytes(bytes, filename: filename),
      });
      final res = await _dio.post<Map<String, dynamic>>(
        '/api/receipts/ocr',
        data: form,
      );
      return ParsedReceipt.fromJson(res.data ?? const {});
    } on DioException catch (e) {
      final status = e.response?.statusCode;
      if (status == 422) {
        final detail = (e.response?.data as Map<String, dynamic>?)?['detail'];
        throw ApiException(
          detail is String ? detail : 'Nota tidak terbaca — coba foto ulang atau input manual.',
        );
      }
      throw ApiException(_dioMessage(e));
    }
  }

  /// GET /api/accounts → daftar akun user.
  Future<List<AccountModel>> fetchAccounts({bool includeInactive = false}) async {
    final query = <String, dynamic>{};
    if (includeInactive) query['include_inactive'] = 'true';
    final list = await _getList('/api/accounts', query);
    return list
        .map((e) => AccountModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  // ── Transaksi (list + CRUD) ────────────────────────────────────────────────

  /// GET /api/transactions — keyset pagination (`cursor` = next_cursor).
  Future<TransactionListResult> fetchTransactions({
    String? cursor,
    String? type,
    String? categoryId,
    String? accountId,
  }) async {
    final query = <String, dynamic>{};
    if (cursor != null) query['cursor'] = cursor;
    if (type != null) query['type'] = type;
    if (categoryId != null) query['category_id'] = categoryId;
    if (accountId != null) query['account_id'] = accountId;
    final data = await _get('/api/transactions', query);
    return TransactionListResult.fromJson(data);
  }

  /// Loop semua halaman transaksi (keyset pagination) → list lengkap.
  /// Dipakai untuk filter akun client-side di dashboard (tanpa N+1: satu
  /// loop berurutan, bukan query per-akun) — setara v1 `fetchAllTransactions`.
  Future<List<TransactionModel>> fetchAllTransactions({
    String? type,
    String? categoryId,
    String? accountId,
    int maxItems = 2000,
  }) async {
    final all = <TransactionModel>[];
    String? cursor;
    do {
      final page = await fetchTransactions(
        cursor: cursor,
        type: type,
        categoryId: categoryId,
        accountId: accountId,
      );
      all.addAll(page.items);
      cursor = page.nextCursor;
    } while (cursor != null && all.length < maxItems);
    return all;
  }

  /// GET /api/transactions/{id} — detail satu transaksi (untuk form edit).
  Future<TransactionModel> fetchTransaction(String id) async {
    try {
      final res = await _dio.get<Map<String, dynamic>>('/api/transactions/$id');
      return TransactionModel.fromJson(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException(_dioMessage(e));
    }
  }

  /// PUT /api/transactions/{id} — PATCH semantics: hanya field non-null
  /// yang dikirim (backend mengupdate yang ada saja).
  Future<void> updateTransaction(
    String id, {
    String? type,
    double? totalAmount,
    String? categoryId,
    String? accountId,
    String? merchant,
    String? note,
    DateTime? transactionDate,
    List<ReceiptItemModel>? items,
  }) async {
    try {
      final data = <String, dynamic>{};
      if (type != null) data['type'] = type;
      if (totalAmount != null) data['total_amount'] = totalAmount;
      if (categoryId != null) data['category_id'] = categoryId;
      if (accountId != null) data['account_id'] = accountId;
      if (merchant != null) data['merchant'] = merchant;
      if (note != null) data['note'] = note;
      if (transactionDate != null) {
        data['transaction_date'] = transactionDate.toIso8601String();
      }
      if (items != null) {
        data['items'] = items.map((i) => i.toJson()).toList();
      }
      await _dio.put<void>('/api/transactions/$id', data: data);
    } on DioException catch (e) {
      throw ApiException(_dioMessage(e));
    }
  }

  /// DELETE /api/transactions/{id} — hapus transaksi (204).
  Future<void> deleteTransaction(String id) async {
    try {
      await _dio.delete<void>('/api/transactions/$id');
    } on DioException catch (e) {
      throw ApiException(_dioMessage(e));
    }
  }

  // ── Kategori (management) ──────────────────────────────────────────────────

  /// GET /api/categories — opsional filter type=income|expense.
  Future<List<CategoryModel>> fetchCategories({String? type}) async {
    final query = <String, dynamic>{};
    if (type != null) query['type'] = type;
    final list = await _getList('/api/categories', query);
    return list
        .map((e) => CategoryModel.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  Future<CategoryModel> createCategory({
    required String name,
    required String type,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/api/categories',
        data: {'name': name, 'type': type},
      );
      return CategoryModel.fromJson(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException(_dioMessage(e));
    }
  }

  Future<CategoryModel> updateCategory(
    String id, {
    String? name,
    String? type,
  }) async {
    try {
      final data = <String, dynamic>{};
      if (name != null) data['name'] = name;
      if (type != null) data['type'] = type;
      final res = await _dio.put<Map<String, dynamic>>(
        '/api/categories/$id',
        data: data,
      );
      return CategoryModel.fromJson(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException(_dioMessage(e));
    }
  }

  Future<void> deleteCategory(String id) async {
    try {
      await _dio.delete<void>('/api/categories/$id');
    } on DioException catch (e) {
      throw ApiException(_dioMessage(e));
    }
  }

  // ── Akun (management) ──────────────────────────────────────────────────────

  Future<AccountModel> createAccount({
    required String accountName,
    String? bankName,
    double initialBalance = 0,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/api/accounts',
        data: {
          'account_name': accountName,
          'bank_name': bankName,
          'initial_balance': initialBalance,
        },
      );
      return AccountModel.fromJson(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException(_dioMessage(e));
    }
  }

  Future<AccountModel> updateAccount(
    String id, {
    String? accountName,
    String? bankName,
  }) async {
    try {
      final data = <String, dynamic>{};
      if (accountName != null) data['account_name'] = accountName;
      if (bankName != null) data['bank_name'] = bankName;
      final res = await _dio.put<Map<String, dynamic>>(
        '/api/accounts/$id',
        data: data,
      );
      return AccountModel.fromJson(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException(_dioMessage(e));
    }
  }

  /// POST /api/accounts/{id}/deactivate — nonaktifkan akun; `targetAccountId`
  /// wajib saat saldo ≠ 0 (saldo dipindah via transaksi balancing).
  Future<AccountModel> deactivateAccount(
    String id, {
    String? targetAccountId,
  }) async {
    try {
      final res = await _dio.post<Map<String, dynamic>>(
        '/api/accounts/$id/deactivate',
        data: {'target_account_id': targetAccountId},
      );
      return AccountModel.fromJson(res.data ?? const {});
    } on DioException catch (e) {
      throw ApiException(_dioMessage(e));
    }
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

  Future<List<dynamic>> _getList(
    String path, [
    Map<String, dynamic>? query,
  ]) async {
    try {
      final res = await _dio.get<List<dynamic>>(
        path,
        queryParameters: query,
      );
      return res.data ?? const [];
    } on DioException catch (e) {
      throw ApiException(_dioMessage(e));
    }
  }

  /// POST /api/transactions — simpan transaksi (hasil review Scan Nota).
  Future<void> createTransaction({
    required String type,
    required double totalAmount,
    required String categoryId,
    required String accountId,
    String? merchant,
    String? note,
    required DateTime transactionDate,
    required List<ReceiptItemModel> items,
  }) async {
    try {
      await _dio.post<void>(
        '/api/transactions',
        data: {
          'type': type,
          'total_amount': totalAmount,
          'category_id': categoryId,
          'account_id': accountId,
          'merchant': merchant,
          'note': note,
          'transaction_date': transactionDate.toIso8601String(),
          'items': items.map((i) => i.toJson()).toList(),
        },
      );
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
