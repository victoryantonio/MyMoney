/// Layanan notifikasi lokal (flutter_local_notifications).
///
/// Fitur: pengingat per jam (setara WorkManager "HourlyReminder" di v1
/// Kotlin — setiap jam mengingatkan mencatat transaksi) + permintaan izin
/// POST_NOTIFICATIONS (Android 13+) / permission iOS.
library;

import 'package:flutter_local_notifications/flutter_local_notifications.dart';

class NotificationService {
  NotificationService._();

  static final NotificationService instance = NotificationService._();

  static const int _reminderId = 1001;

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  bool _initialized = false;

  static const AndroidNotificationDetails _androidDetails =
      AndroidNotificationDetails(
    'hourly_reminder',
    'Hourly reminder',
    channelDescription: 'Pengingat per jam untuk mencatat transaksi',
    importance: Importance.defaultImportance,
    priority: Priority.defaultPriority,
  );

  Future<void> init() async {
    if (_initialized) return;
    const android = AndroidInitializationSettings('@mipmap/ic_launcher');
    const ios = DarwinInitializationSettings(
      requestAlertPermission: false,
      requestBadgePermission: false,
      requestSoundPermission: false,
    );
    await _plugin.initialize(
      const InitializationSettings(android: android, iOS: ios),
    );
    _initialized = true;
  }

  /// Minta izin notifikasi (POST_NOTIFICATIONS di Android 13+).
  Future<bool> requestPermission() async {
    await init();
    final android = _plugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
    final granted = await android?.requestNotificationsPermission();
    final ios = _plugin
        .resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin>();
    await ios?.requestPermissions(alert: true, badge: true, sound: true);
    return granted ?? true;
  }

  /// Cek apakah notifikasi diizinkan (tanpa memunculkan dialog).
  Future<bool> isPermissionGranted() async {
    await init();
    final android = _plugin
        .resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
    final enabled = await android?.areNotificationsEnabled();
    if (enabled != null) return enabled;
    final ios = _plugin
        .resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin>();
    final settings = await ios?.checkPermissions();
    return settings?.isEnabled ?? true;
  }

  /// Jadwalkan pengingat setiap jam (fire pertama tepat di jam berikutnya,
  /// lalu berulang tiap 1 jam — perilaku sama dengan v1 Kotlin WorkManager).
  Future<void> scheduleHourlyReminder() async {
    await init();
    await _plugin.periodicallyShow(
      _reminderId,
      'Ayo catat transaksimu!',
      'Jangan lupa catat pengeluaran/pemasukan Anda.',
      RepeatInterval.hourly,
      const NotificationDetails(
        android: _androidDetails,
        iOS: DarwinNotificationDetails(),
      ),
      androidScheduleMode: AndroidScheduleMode.inexactAllowWhileIdle,
    );
  }

  Future<void> cancelHourlyReminder() => _plugin.cancel(_reminderId);

  Future<bool> isHourlyReminderScheduled() async {
    await init();
    final pending = await _plugin.pendingNotificationRequests();
    return pending.any((r) => r.id == _reminderId);
  }
}
