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
    // Email di bawah nama disensor: 3 depan + ***** + 5 belakang.
    expect(find.text('bud*****l.com'), findsOneWidget);
    expect(find.text('budi@mail.com'), findsNothing);
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

    await tester.scrollUntilVisible(
      find.text('Keluar'),
      300,
      scrollable: find.byType(Scrollable),
    );
    expect(find.text('Keluar'), findsOneWidget);
    expect(find.byIcon(Icons.logout), findsOneWidget);
  });
}
