// Widget test kartu "Total Balance" dashboard (Req 6 — filter akun).
//
// Regresi yang dikunci: saat filter akun diganti di dashboard, angka pada kartu
// "Total Balance" DULU tetap menjumlah seluruh akun (tidak mengikuti filter).
// Test ini memompa DashboardScreen sungguhan tanpa jaringan (Dio memakai
// adapter palsu), menekan item pada dropdown filter, lalu memeriksa nominal +
// subtitle kartu:
//
//   "Semua akun"   → Rp1.300.000, tanpa subtitle
//   1 akun dipilih → Rp1.000.000, subtitle "SeaBank · Bank"
//   0 akun dipilih → Rp0,        subtitle "Tidak ada akun dipilih"

import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart' hide Headers;
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:mymoney_app/core/api_client.dart';
import 'package:mymoney_app/screens/dashboard_screen.dart';

/// Adapter Dio palsu: menjawab semua endpoint dashboard dengan data tetap.
class _FakeDashboardAdapter implements HttpClientAdapter {
  int accountsCalls = 0;

  @override
  void close({bool force = false}) {}

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    switch (options.uri.path) {
      case '/api/reports/summary':
        return _json({
          'start_date': '2026-09-01T00:00:00',
          'end_date': '2026-09-30T23:59:59',
          'total_income': '0.00',
          'total_expense': '0.00',
          'net': '0.00',
          'categories': <dynamic>[],
        });
      case '/api/reports/trend':
        return _json({
          'start_date': '2026-09-01T00:00:00',
          'end_date': '2026-09-30T23:59:59',
          'points': <dynamic>[],
        });
      case '/api/accounts':
        accountsCalls++;
        return _json([
          _account('a1', 'SeaBank', 'bank', 1000000),
          _account('a2', 'BCA', 'bank', 300000),
        ]);
      case '/api/categories':
        return _json(<dynamic>[]);
      case '/api/transactions':
        return _json({
          'items': <dynamic>[],
          'next_cursor': null,
          'total_count': 0,
        });
    }
    return ResponseBody.fromString('{}', 404);
  }

  static Map<String, dynamic> _account(
    String id,
    String name,
    String type,
    double balance,
  ) =>
      {
        'id': id,
        'account_name': name,
        'account_type': type,
        'initial_balance': balance.toStringAsFixed(2),
        'current_balance': balance.toStringAsFixed(2),
        'net_balance': '0.00',
        'is_active': true,
      };

  static ResponseBody _json(Object body) => ResponseBody.fromString(
        jsonEncode(body),
        200,
        headers: {
          'content-type': ['application/json'],
        },
      );
}

void main() {
  setUpAll(() async {
    SharedPreferences.setMockInitialValues({});
    await Supabase.initialize(
      url: 'https://placeholder.supabase.co',
      publishableKey: 'placeholder-anon-key',
    );
  });

  tearDown(() {
    ApiClient.overrideInstance = null;
  });

  Future<void> pumpDashboard(WidgetTester tester) async {
    final dio = Dio(BaseOptions(baseUrl: 'https://api.test'))
      ..httpClientAdapter = _FakeDashboardAdapter();
    ApiClient.overrideInstance = ApiClient.withDio(dio);
    await tester.pumpWidget(
      MaterialApp(
        home: DashboardScreen(supabase: Supabase.instance.client),
      ),
    );
    await tester.pumpAndSettle();
  }

  /// Menutup menu filter (tap di luar) lalu memastikan menu benar tertutup.
  Future<void> closeMenu(WidgetTester tester) async {
    await tester.tapAt(const Offset(10, 560));
    await tester.pumpAndSettle();
    expect(
      find.text('Select all'),
      findsNothing,
      reason: 'menu filter harus sudah tertutup',
    );
    expect(
      find.text('Unselect all'),
      findsNothing,
      reason: 'menu filter harus sudah tertutup',
    );
  }

  testWidgets(
    'Total Balance mengikuti filter akun: semua -> 1 akun',
    (tester) async {
      await pumpDashboard(tester);

      // Kondisi awal: semua akun → jumlah seluruh saldo, tanpa subtitle.
      expect(find.text('Semua akun (2)'), findsOneWidget);
      expect(find.text('Rp1.300.000'), findsOneWidget);
      expect(find.text('1 akun terpilih'), findsNothing);

      // Buka dropdown lalu matikan BCA → hanya SeaBank yang dihitung.
      await tester.tap(find.text('Semua akun (2)'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('BCA · Bank'));
      await tester.pumpAndSettle();

      await closeMenu(tester);

      expect(
        find.text('Rp1.000.000'),
        findsOneWidget,
        reason: 'kartu harus hanya menjumlah akun terpilih',
      );
      expect(find.text('Rp1.300.000'), findsNothing);
      expect(
        find.text('SeaBank · Bank'),
        findsOneWidget,
        reason: 'subtitle menjelaskan cakupan saldo',
      );
      expect(find.text('1 akun terpilih'), findsOneWidget);
    },
  );

  testWidgets(
    'Total Balance jadi Rp0 saat tidak ada akun dipilih',
    (tester) async {
      await pumpDashboard(tester);
      expect(find.text('Rp1.300.000'), findsOneWidget);

      // Matikan semua akun lewat item "Unselect all".
      await tester.tap(find.text('Semua akun (2)'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Unselect all'));
      await tester.pumpAndSettle();

      await closeMenu(tester);

      expect(find.text('Rp0'), findsWidgets);
      expect(find.text('Tidak ada akun dipilih'), findsWidgets);
      expect(find.text('Rp1.300.000'), findsNothing);
      expect(find.text('Rp1.000.000'), findsNothing);
    },
  );
}
