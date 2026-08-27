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

  testWidgets('AuthScreen displays the login form', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: AuthScreen()));

    expect(find.text('My Money'), findsOneWidget);
    expect(find.byType(Image), findsOneWidget); // icon aplikasi di form login
    expect(find.byType(TextField), findsNWidgets(2));
    expect(find.text('Login'), findsOneWidget);
    expect(find.text("Don't have an account yet? Register"), findsOneWidget);
  });

  testWidgets('Switch AuthScreen to register mode', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: AuthScreen()));

    await tester.tap(find.text("Don't have an account yet? Register"));
    await tester.pump();

    expect(find.text('Register'), findsOneWidget);
    expect(find.text('Already have an account? Login'), findsOneWidget);
  });

  testWidgets('Register mode shows Full Name field', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: AuthScreen()));

    await tester.tap(find.text("Don't have an account yet? Register"));
    await tester.pump();

    expect(find.text('Full Name'), findsOneWidget);
    expect(find.byType(TextField), findsNWidgets(3)); // full name + email + password
  });

  testWidgets('Register requires full name', (WidgetTester tester) async {
    await tester.pumpWidget(const MaterialApp(home: AuthScreen()));

    await tester.tap(find.text("Don't have an account yet? Register"));
    await tester.pump();

    // Nama dibiarkan kosong → tekan Register → validasi lokal muncul (tanpa network).
    await tester.tap(find.text('Register'));
    await tester.pump();

    expect(find.text('Full name is required.'), findsOneWidget);
  });
}
