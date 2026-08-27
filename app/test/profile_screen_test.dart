// Widget test ProfileScreen: warning email belum terverifikasi, kirim ulang
// verifikasi (callback di-inject, tanpa network), dan tombol Keluar.

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'package:mymoney_app/screens/profile_screen.dart';

void main() {
  setUpAll(() {
    SharedPreferences.setMockInitialValues({});
    Supabase.initialize(
      url: 'https://placeholder.supabase.co',
      publishableKey: 'placeholder-anon-key',
    );
  });

  Widget buildScreen({
    required ProfileInfo info,
    Future<bool> Function()? resendVerification,
  }) {
    return MaterialApp(
      home: ProfileScreen(
        supabase: Supabase.instance.client,
        info: info,
        resendVerification: resendVerification,
      ),
    );
  }

  testWidgets('shows warning + resend button when email unverified',
      (WidgetTester tester) async {
    var resent = false;
    await tester.pumpWidget(buildScreen(
      info: const ProfileInfo(
        email: 'budi@mail.com',
        displayName: 'Budi',
        emailVerified: false,
      ),
      resendVerification: () async {
        resent = true;
        return true;
      },
    ));

    expect(find.text('Budi'), findsOneWidget);
    expect(find.text('budi@mail.com'), findsWidgets);
    expect(find.text('Email belum diverifikasi'), findsOneWidget);
    expect(find.text('Kirim ulang email verifikasi'), findsOneWidget);

    await tester.tap(find.text('Kirim ulang email verifikasi'));
    await tester.pump();

    expect(resent, isTrue);
    expect(find.textContaining('Email verifikasi terkirim'), findsOneWidget);
  });

  testWidgets('no warning when email verified', (WidgetTester tester) async {
    await tester.pumpWidget(buildScreen(
      info: const ProfileInfo(
        email: 'budi@mail.com',
        displayName: 'Budi',
        emailVerified: true,
      ),
    ));

    expect(find.text('Email belum diverifikasi'), findsNothing);
    expect(find.text('Terverifikasi'), findsOneWidget);
  });

  testWidgets('shows sign out button', (WidgetTester tester) async {
    await tester.pumpWidget(buildScreen(
      info: const ProfileInfo(
        email: 'budi@mail.com',
        displayName: 'Budi',
        emailVerified: true,
      ),
    ));

    expect(find.text('Keluar'), findsOneWidget);
    expect(find.byIcon(Icons.logout), findsOneWidget);
  });
}
