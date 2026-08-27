/// Smoke test layar Notifikasi (tab baru Phase D).
///
/// Di lingkungan test, plugin flutter_local_notifications tidak punya
/// implementasi host → pemanggilan platform channel melempar
/// MissingPluginException yang ditangkap oleh `NotificationService`/
/// `NotificationsScreen` (state fallback: switch off). Ini menguji bahwa
/// layar tetap render dengan benar.
library;

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:mymoney_app/screens/notifications_screen.dart';

void main() {
  testWidgets('NotificationsScreen renders hourly reminder card',
      (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: NotificationsScreen()),
    );
    await tester.pumpAndSettle();

    expect(find.text('Hourly reminder'), findsOneWidget);
    expect(find.textContaining('Setiap jam'), findsOneWidget);
    expect(find.byType(Switch), findsOneWidget);
    expect(find.text('Belum ada notifikasi'), findsOneWidget);
  });

  testWidgets('toggling reminder shows error snackbar when plugin unavailable',
      (tester) async {
    await tester.pumpWidget(
      const MaterialApp(home: NotificationsScreen()),
    );
    await tester.pumpAndSettle();

    await tester.tap(find.byType(Switch));
    await tester.pumpAndSettle();

    // Plugin tidak tersedia di test → SnackBar error.
    expect(find.text('Gagal mengubah pengingat.'), findsOneWidget);
  });
}
