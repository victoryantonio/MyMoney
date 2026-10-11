// Widget test MutationMatchScreen (Req 9 — Matching Mutasi) — tahap UI saja.
//
// Menguji alur: stage pilih berkas → stage pratinjau setelah berkas dipilih →
// kembali ke stage pilih saat "Pilih Ulang". `pickFile` di-inject agar tidak
// bergantung plugin kamera/galeri. Tahap hasil (stage 3) butuh backend asli,
// jadi tidak diuji di sini.

import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:mymoney_app/core/api_client.dart';
import 'package:mymoney_app/screens/mutation_match_screen.dart';

/// PNG 1x1 transparan — gambar valid untuk `Image.memory` di pratinjau.
final Uint8List kTinyPng = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6k'
  'gAAAABJRU5ErkJggg==',
);

void main() {
  setUpAll(() {
    // supabase_flutter menyimpan session via shared_preferences;
    // di unit test plugin tidak tersedia → mock storage.
    SharedPreferences.setMockInitialValues({});
    Supabase.initialize(
      url: 'https://placeholder.supabase.co',
      publishableKey: 'placeholder-anon-key',
    );
  });

  Widget buildScreen({MutationFilePickFn? pickFile}) {
    return MaterialApp(
      home: MutationMatchScreen(
        api: ApiClient.instance(Supabase.instance.client),
        pickFile: pickFile ?? (_) async => null,
      ),
    );
  }

  testWidgets('MutationMatchScreen shows upload options', (tester) async {
    await tester.pumpWidget(buildScreen());
    // `initState` memuat daftar akun (best-effort); settle agar timer Dio selesai.
    await tester.pumpAndSettle();

    expect(find.text('Matching Mutasi'), findsOneWidget);
    expect(find.text('Cocokkan mutasi bank dengan catatan'), findsOneWidget);
    expect(find.text('Ambil Foto Mutasi'), findsOneWidget);
    expect(find.text('Pilih dari Galeri'), findsOneWidget);
    expect(find.text('Cocokkan Mutasi'), findsNothing);
  });

  testWidgets('Choosing a screenshot moves to preview stage', (tester) async {
    await tester.pumpWidget(
      buildScreen(
        pickFile: (_) async =>
            PickedMutationFile(bytes: kTinyPng, name: 'mutasi.png'),
      ),
    );

    await tester.tap(find.text('Ambil Foto Mutasi'));
    await tester.pumpAndSettle();

    expect(find.text('Cocokkan Mutasi'), findsOneWidget);
    expect(find.text('Pilih Ulang'), findsOneWidget);
    expect(find.text('Cocokkan mutasi bank dengan catatan'), findsNothing);
  });

  testWidgets('CSV file shows a document placeholder instead of image',
      (tester) async {
    await tester.pumpWidget(
      buildScreen(
        pickFile: (_) async =>
            PickedMutationFile(bytes: kTinyPng, name: 'mutasi.csv'),
      ),
    );

    await tester.tap(find.text('Pilih dari Galeri'));
    await tester.pumpAndSettle();

    expect(find.text('mutasi.csv'), findsOneWidget);
    expect(find.byIcon(Icons.description_outlined), findsOneWidget);
  });

  testWidgets('"Pilih Ulang" returns to the select stage', (tester) async {
    await tester.pumpWidget(
      buildScreen(
        pickFile: (_) async =>
            PickedMutationFile(bytes: kTinyPng, name: 'mutasi.png'),
      ),
    );

    await tester.tap(find.text('Ambil Foto Mutasi'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Pilih Ulang'));
    await tester.pumpAndSettle();

    expect(find.text('Ambil Foto Mutasi'), findsOneWidget);
    expect(find.text('Cocokkan Mutasi'), findsNothing);
  });

  testWidgets('Cancelling the picker keeps the select stage', (tester) async {
    await tester.pumpWidget(buildScreen(pickFile: (_) async => null));

    await tester.tap(find.text('Ambil Foto Mutasi'));
    await tester.pumpAndSettle();

    expect(find.text('Ambil Foto Mutasi'), findsOneWidget);
    expect(find.text('Cocokkan Mutasi'), findsNothing);
  });
}
