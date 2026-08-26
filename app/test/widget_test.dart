// Smoke test AuthScreen (Fase 0): render form login tanpa network.
// Supabase.initialize hanya menyimpan kredensial — tidak ada HTTP call
// sampai operasi auth dijalankan, jadi aman memakai URL placeholder.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:mymoney_app/screens/auth_screen.dart';

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

  testWidgets('AuthScreen menampilkan form login', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: AuthScreen()));

    expect(find.text('MyMoney'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(2));
    expect(find.text('Masuk'), findsOneWidget);
    expect(find.text('Belum punya akun? Daftar'), findsOneWidget);
  });

  testWidgets('AuthScreen toggle ke mode daftar', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: AuthScreen()));

    await tester.tap(find.text('Belum punya akun? Daftar'));
    await tester.pump();

    expect(find.text('Daftar'), findsOneWidget);
    expect(find.text('Sudah punya akun? Masuk'), findsOneWidget);
  });
}
