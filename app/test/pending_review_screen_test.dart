// Widget test alur "Pending" — baris mutasi yang belum balance dengan transaksi
// tercatat (hasil Matching Mutasi) harus bisa dikonfirmasi/dibatalkan dari layar
// itu sendiri, tanpa "menu Pending" terpisah yang tidak pernah ada.
//
// Jaringan dipalsukan lewat `HttpClientAdapter` Dio, jadi test ini tidak
// menyentuh backend sungguhan (pola `ApiClient.withDio`).

import 'dart:convert';
import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:mymoney_app/core/api_client.dart';
import 'package:mymoney_app/screens/mutation_match_screen.dart';
import 'package:mymoney_app/screens/pending_review_screen.dart';

/// Adapter Dio palsu: menjawab berdasarkan method + path, sekaligus mencatat
/// request yang masuk agar bisa diverifikasi.
class _FakeAdapter implements HttpClientAdapter {
  _FakeAdapter(this._routes);

  /// key: "METHOD /path" (tanpa query), value: (statusCode, body JSON).
  final Map<String, (int, Object)> _routes;
  final List<String> calls = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    final key = '${options.method} ${options.path}';
    calls.add(key);
    final route = _routes[key];
    if (route == null) {
      return ResponseBody.fromString(
        jsonEncode({'detail': 'not found: $key'}),
        404,
        headers: {
          Headers.contentTypeHeader: [Headers.jsonContentType],
        },
      );
    }
    return ResponseBody.fromString(
      jsonEncode(route.$2),
      route.$1,
      headers: {
        Headers.contentTypeHeader: [Headers.jsonContentType],
      },
    );
  }

  @override
  void close({bool force = false}) {}
}

Map<String, dynamic> _pendingJson({
  String id = 'p1',
  String type = 'expense',
  String amount = '135000.00',
  String merchant = 'QRIS TOKO ABC',
}) => {
  'id': id,
  'action': 'create',
  'type': type,
  'total_amount': amount,
  'category_id': 'cat-1',
  'category_name': 'Belanja',
  'account_id': 'acc-1',
  'account_name': 'BCA Tahunan',
  'merchant': merchant,
  'note': 'Mutasi: $merchant (2026-08-02)',
  'source': 'app',
  'confidence': 'medium',
  'raw_input': 'Matching Mutasi — mutasi.csv',
  'target_transaction_id': null,
  'created_at': '2026-08-02T10:00:00Z',
  'expires_at': '2026-08-03T10:00:00Z',
};

ApiClient _client(_FakeAdapter adapter) {
  final dio = Dio(BaseOptions(baseUrl: 'https://api.test'));
  dio.httpClientAdapter = adapter;
  return ApiClient.withDio(dio);
}

/// Buka `PendingReviewScreen` lewat `Navigator.push` supaya bisa dipastikan
/// apakah layar benar-benar ditutup (pop) atau tidak.
Future<void> _pumpPendingHost(
  WidgetTester tester,
  _FakeAdapter adapter, {
  String? title,
}) async {
  await tester.pumpWidget(
    MaterialApp(
      home: Builder(
        builder: (context) => Scaffold(
          body: Center(
            child: ElevatedButton(
              onPressed: () => Navigator.of(context).push(
                MaterialPageRoute<bool>(
                  builder: (_) => PendingReviewScreen(
                    api: _client(adapter),
                    title: title ?? 'Pending',
                  ),
                ),
              ),
              child: const Text('Buka Pending'),
            ),
          ),
        ),
      ),
    ),
  );
  await tester.tap(find.text('Buka Pending'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('PendingReviewScreen lists pending rows with two actions', (
    tester,
  ) async {
    final adapter = _FakeAdapter({
      'GET /api/pending': (
        200,
        {
          'items': [_pendingJson()],
          'total': 1,
        },
      ),
    });

    await tester.pumpWidget(
      MaterialApp(home: PendingReviewScreen(api: _client(adapter))),
    );
    await tester.pumpAndSettle();

    expect(find.text('QRIS TOKO ABC'), findsOneWidget);
    expect(find.text('Konfirmasi'), findsOneWidget);
    expect(find.text('Batalkan'), findsOneWidget);
    expect(find.textContaining('1 baris menunggu konfirmasi'), findsOneWidget);
    // Saldo/nominal tampil dalam rupiah.
    expect(find.textContaining('135'), findsWidgets);
  });

  testWidgets('Konfirmasi moves the row to a real transaction', (tester) async {
    final adapter = _FakeAdapter({
      'GET /api/pending': (
        200,
        {
          'items': [_pendingJson()],
          'total': 1,
        },
      ),
      'POST /api/pending/p1/confirm': (
        200,
        {
          'pending_id': 'p1',
          'transaction_id': 'tx-1',
          'action': 'create',
          'type': 'expense',
          'total_amount': '135000.00',
        },
      ),
    });
    var changed = 0;

    await tester.pumpWidget(
      MaterialApp(
        home: PendingReviewScreen(
          api: _client(adapter),
          onChanged: () => changed++,
        ),
      ),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Konfirmasi'));
    await tester.pumpAndSettle();

    expect(adapter.calls, contains('POST /api/pending/p1/confirm'));
    expect(changed, 1);
    // Baris hilang dari daftar → empty state muncul.
    expect(find.text('QRIS TOKO ABC'), findsNothing);
    expect(find.text('Tidak ada transaksi pending'), findsOneWidget);
  });

  testWidgets('Konfirmasi Semua confirms every pending row at once', (
    tester,
  ) async {
    final adapter = _FakeAdapter({
      'GET /api/pending': (
        200,
        {
          'items': [
            _pendingJson(id: 'p1', merchant: 'QRIS TOKO ABC'),
            _pendingJson(id: 'p2', merchant: 'TRANSFER BUDI'),
          ],
          'total': 2,
        },
      ),
      'POST /api/pending/p1/confirm': (
        200,
        {
          'pending_id': 'p1',
          'transaction_id': 'tx-1',
          'action': 'create',
          'type': 'expense',
          'total_amount': '135000.00',
        },
      ),
      'POST /api/pending/p2/confirm': (
        200,
        {
          'pending_id': 'p2',
          'transaction_id': 'tx-2',
          'action': 'create',
          'type': 'expense',
          'total_amount': '135000.00',
        },
      ),
    });
    final resolved = <String>[];
    var changed = 0;

    await tester.pumpWidget(
      MaterialApp(
        home: PendingReviewScreen(
          api: _client(adapter),
          onChanged: () => changed++,
          onResolved: resolved.add,
        ),
      ),
    );
    await tester.pumpAndSettle();

    // Tombol di header (ikon centang ganda) membuka dialog persetujuan lebih
    // dulu — konfirmasi massal membuat transaksi nyata.
    await tester.tap(find.text('Konfirmasi Semua'));
    await tester.pumpAndSettle();
    expect(find.text('Ya, konfirmasi semua'), findsOneWidget);

    await tester.tap(find.text('Ya, konfirmasi semua'));
    await tester.pumpAndSettle();

    expect(adapter.calls, contains('POST /api/pending/p1/confirm'));
    expect(adapter.calls, contains('POST /api/pending/p2/confirm'));
    expect(resolved, ['p1', 'p2']);
    expect(changed, 1);
    expect(find.text('Tidak ada transaksi pending'), findsOneWidget);
  });

  testWidgets('Konfirmasi Semua does nothing when the dialog is dismissed', (
    tester,
  ) async {
    final adapter = _FakeAdapter({
      'GET /api/pending': (
        200,
        {
          'items': [_pendingJson()],
          'total': 1,
        },
      ),
      'POST /api/pending/p1/confirm': (
        200,
        {
          'pending_id': 'p1',
          'transaction_id': 'tx-1',
          'action': 'create',
          'type': 'expense',
          'total_amount': '135000.00',
        },
      ),
    });

    await tester.pumpWidget(
      MaterialApp(home: PendingReviewScreen(api: _client(adapter))),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Konfirmasi Semua'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Batal'));
    await tester.pumpAndSettle();

    expect(adapter.calls.any((c) => c.contains('/confirm')), isFalse);
    expect(find.text('QRIS TOKO ABC'), findsOneWidget);
  });

  testWidgets('Batalkan discards the row without creating anything', (
    tester,
  ) async {
    final adapter = _FakeAdapter({
      'GET /api/pending': (
        200,
        {
          'items': [_pendingJson()],
          'total': 1,
        },
      ),
      'POST /api/pending/p1/cancel': (
        200,
        {'pending_id': 'p1', 'cancelled': true},
      ),
    });

    await tester.pumpWidget(
      MaterialApp(home: PendingReviewScreen(api: _client(adapter))),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.text('Batalkan'));
    await tester.pumpAndSettle();

    expect(adapter.calls, contains('POST /api/pending/p1/cancel'));
    expect(adapter.calls.any((c) => c.contains('/confirm')), isFalse);
    expect(find.text('Tidak ada transaksi pending'), findsOneWidget);
  });

  testWidgets('Empty pending list shows a friendly empty state', (
    tester,
  ) async {
    final adapter = _FakeAdapter({
      'GET /api/pending': (200, {'items': <Object>[], 'total': 0}),
    });

    await tester.pumpWidget(
      MaterialApp(home: PendingReviewScreen(api: _client(adapter))),
    );
    await tester.pumpAndSettle();

    expect(find.text('Tidak ada transaksi pending'), findsOneWidget);
    expect(find.text('Konfirmasi'), findsNothing);
  });

  testWidgets('Back asks for confirmation before leaving the pending screen', (
    tester,
  ) async {
    final adapter = _FakeAdapter({
      'GET /api/pending': (
        200,
        {
          'items': [_pendingJson()],
          'total': 1,
        },
      ),
    });
    await _pumpPendingHost(tester, adapter);

    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();

    // Dialog peringatan: data pending tidak akan disimpan.
    expect(find.textContaining('Data tidak akan disimpan'), findsOneWidget);
    expect(find.text('Ya'), findsOneWidget);
    expect(find.text('Tidak'), findsOneWidget);

    await tester.tap(find.byKey(const Key('leave-no')));
    await tester.pumpAndSettle();

    // "Tidak" → tetap di layar Pending, tidak ada aksi apa pun.
    expect(find.textContaining('Data tidak akan disimpan'), findsNothing);
    expect(find.text('QRIS TOKO ABC'), findsOneWidget);
    expect(adapter.calls.any((c) => c.contains('/confirm')), isFalse);
    expect(adapter.calls.any((c) => c.contains('/cancel')), isFalse);
  });

  testWidgets('Ya on the leave dialog closes the pending screen', (
    tester,
  ) async {
    final adapter = _FakeAdapter({
      'GET /api/pending': (
        200,
        {
          'items': [_pendingJson()],
          'total': 1,
        },
      ),
    });
    await _pumpPendingHost(tester, adapter);

    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('leave-yes')));
    await tester.pumpAndSettle();

    // Kembali ke layar pemanggil.
    expect(find.text('Buka Pending'), findsOneWidget);
    expect(find.text('QRIS TOKO ABC'), findsNothing);
  });

  testWidgets('Empty pending list leaves without the warning dialog', (
    tester,
  ) async {
    final adapter = _FakeAdapter({
      'GET /api/pending': (200, {'items': <Object>[], 'total': 0}),
    });
    await _pumpPendingHost(tester, adapter);

    await tester.tap(find.byType(BackButton));
    await tester.pumpAndSettle();

    // Tidak ada data yang bisa hilang → langsung keluar.
    expect(find.textContaining('Data tidak akan disimpan'), findsNothing);
    expect(find.text('Buka Pending'), findsOneWidget);
  });

  testWidgets(
    'Result screen shows a bottom Matching button instead of a dead-end hint',
    (tester) async {
      final adapter = _FakeAdapter({
        'GET /api/accounts': (200, <Object>[]),
        'POST /api/mutations/match': (
          200,
          {
            'account_id': null,
            'account_name': null,
            'source_description': null,
            'total_mutations': 1,
            'matched_count': 0,
            'unmatched_mutation_count': 1,
            'unmatched_transaction_count': 0,
            'matches': <Object>[],
            'unmatched_mutations': [
              {
                'date': '2026-08-02',
                'time': null,
                'description': 'QRIS TOKO ABC',
                'amount': '135000.00',
                'direction': 'debit',
              },
            ],
            'created_pending_ids': ['p1'],
          },
        ),
        'GET /api/pending': (
          200,
          {
            'items': [_pendingJson()],
            'total': 1,
          },
        ),
      });

      await tester.pumpWidget(
        MaterialApp(
          home: MutationMatchScreen(
            api: _client(adapter),
            pickFile: (_) async => PickedMutationFile(
              bytes: Uint8List.fromList([1, 2, 3]),
              name: 'mutasi.csv',
            ),
          ),
        ),
      );
      await tester.pumpAndSettle();

      await tester.tap(find.text('Pilih PDF E-Statement'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cocokkan Mutasi'));
      await tester.pumpAndSettle();

      // Teks lama yang menyuruh membuka "menu Pending" harus sudah tidak ada.
      expect(find.textContaining('buka menu Pending'), findsNothing);

      // Tombol Matching ada di bagian bawah layar hasil.
      final matching = find.textContaining('Matching — konfirmasi');
      expect(matching, findsOneWidget);

      await tester.tap(matching);
      await tester.pumpAndSettle();

      // Layar Pending terbuka dan memuat baris dari server.
      expect(find.text('Matching — Pending'), findsOneWidget);
      expect(find.text('QRIS TOKO ABC'), findsOneWidget);
      expect(find.text('Konfirmasi'), findsOneWidget);
    },
  );

  testWidgets(
    'Leaving the result screen discards unconfirmed pending rows',
    (tester) async {
      final adapter = _FakeAdapter({
        'GET /api/accounts': (200, <Object>[]),
        'POST /api/mutations/match': (
          200,
          {
            'account_id': null,
            'account_name': null,
            'source_description': null,
            'total_mutations': 1,
            'matched_count': 0,
            'unmatched_mutation_count': 1,
            'unmatched_transaction_count': 0,
            'matches': <Object>[],
            'unmatched_mutations': [
              {
                'date': '2026-08-02',
                'time': null,
                'description': 'QRIS TOKO ABC',
                'amount': '135000.00',
                'direction': 'debit',
              },
            ],
            'created_pending_ids': ['p1', 'p2'],
          },
        ),
        'POST /api/pending/p1/cancel': (
          200,
          {'pending_id': 'p1', 'cancelled': true},
        ),
        'POST /api/pending/p2/cancel': (
          200,
          {'pending_id': 'p2', 'cancelled': true},
        ),
      });

      await tester.pumpWidget(
        MaterialApp(
          home: Builder(
            builder: (context) => Scaffold(
              body: ElevatedButton(
                onPressed: () => Navigator.of(context).push(
                  MaterialPageRoute<void>(
                    builder: (_) => MutationMatchScreen(
                      api: _client(adapter),
                      pickFile: (_) async => PickedMutationFile(
                        bytes: Uint8List.fromList([1, 2, 3]),
                        name: 'mutasi.csv',
                      ),
                    ),
                  ),
                ),
                child: const Text('buka matching'),
              ),
            ),
          ),
        ),
      );

      await tester.tap(find.text('buka matching'));
      await tester.pumpAndSettle();

      await tester.tap(find.text('Pilih PDF E-Statement'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Cocokkan Mutasi'));
      await tester.pumpAndSettle();

      // User keluar tanpa menekan tombol Matching → baris pending dibuang.
      await tester.pageBack();
      await tester.pumpAndSettle();

      expect(adapter.calls, contains('POST /api/pending/p1/cancel'));
      expect(adapter.calls, contains('POST /api/pending/p2/cancel'));
      // Kembali ke layar pemanggil.
      expect(find.text('buka matching'), findsOneWidget);
    },
  );
}
