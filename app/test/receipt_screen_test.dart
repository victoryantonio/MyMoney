// Widget test ReceiptScreen (Scan Nota) — Fase UI tanpa network.
//
// Menguji alur: stage pilih sumber → stage preview setelah memilih gambar.
// `pickImage` di-inject agar tidak bergantung plugin kamera; tahap OCR/simpan
// tidak ditekan di sini (butuh backend asli).

import 'dart:convert';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:mymoney_app/core/api_client.dart';
import 'package:mymoney_app/screens/receipt_screen.dart';

/// PNG 1x1 transparan — gambar valid untuk Image.memory di preview.
final Uint8List kTinyPng = base64Decode(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
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

  Widget buildScreen({ImagePickFn? pickImage}) {
    return MaterialApp(
      home: ReceiptScreen(
        api: ApiClient.instance(Supabase.instance.client),
        pickImage: pickImage ?? (_) async => null,
      ),
    );
  }

  testWidgets('ReceiptScreen shows scan source options', (tester) async {
    await tester.pumpWidget(buildScreen());

    expect(find.text('Scan Nota'), findsOneWidget);
    expect(find.text('Ambil Foto'), findsOneWidget);
    expect(find.text('Pilih dari Galeri'), findsOneWidget);
  });

  testWidgets('Choosing a photo moves to preview stage', (tester) async {
    await tester.pumpWidget(
      buildScreen(
        pickImage: (_) async =>
            PickedReceiptImage(bytes: kTinyPng, name: 'nota.jpg'),
      ),
    );

    await tester.tap(find.text('Ambil Foto'));
    await tester.pumpAndSettle();

    expect(find.text('Proses OCR'), findsOneWidget);
    expect(find.text('Ambil Ulang'), findsOneWidget);
  });

  testWidgets('Cancel picker keeps select stage', (tester) async {
    await tester.pumpWidget(buildScreen());

    await tester.tap(find.text('Ambil Foto'));
    await tester.pumpAndSettle();

    expect(find.text('Ambil Foto'), findsOneWidget);
    expect(find.text('Proses OCR'), findsNothing);
  });
}
