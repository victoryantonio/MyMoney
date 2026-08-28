/// Tab Notifikasi — setara v1 Kotlin `NotificationsScreen`.
///
/// Fitur: pengingat per jam ("Setiap jam tepat di jam mengingatkan Anda
/// mencatat expense/income") via notifikasi lokal
/// (flutter_local_notifications) + permintaan izin POST_NOTIFICATIONS
/// (Android 13+) / iOS. Daftar notifikasi masih placeholder (belum ada
/// tabel notifikasi di backend) — sama seperti v1.
library;

import 'package:flutter/material.dart';

import '../core/notification_service.dart';

class NotificationsScreen extends StatefulWidget {
  const NotificationsScreen({super.key});

  @override
  State<NotificationsScreen> createState() => _NotificationsScreenState();
}

class _NotificationsScreenState extends State<NotificationsScreen> {
  bool? _enabled; // null = belum dicek
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    _loadState();
  }

  Future<void> _loadState() async {
    try {
      final enabled = await NotificationService.instance
          .isHourlyReminderScheduled();
      if (!mounted) return;
      setState(() => _enabled = enabled);
    } catch (_) {
      if (!mounted) return;
      setState(() => _enabled = false);
    }
  }

  Future<void> _setReminder(bool enabled) async {
    setState(() => _busy = true);
    try {
      if (enabled) {
        final granted = await NotificationService.instance
            .requestPermission();
        if (!granted) {
          if (!mounted) return;
          setState(() => _busy = false);
          ScaffoldMessenger.of(context).showSnackBar(
            const SnackBar(
              content: Text(
                'Izin notifikasi ditolak — aktifkan di pengaturan perangkat '
                'untuk menggunakan pengingat.',
              ),
            ),
          );
          return;
        }
        await NotificationService.instance.scheduleHourlyReminder();
      } else {
        await NotificationService.instance.cancelHourlyReminder();
      }
      if (!mounted) return;
      setState(() => _enabled = enabled);
    } catch (_) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Gagal mengubah pengingat.')),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Scaffold(
      appBar: AppBar(title: const Text('Notifikasi')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            margin: EdgeInsets.zero,
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: theme.colorScheme.outlineVariant),
            ),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Container(
                    width: 40,
                    height: 40,
                    decoration: BoxDecoration(
                      color: theme.colorScheme.primaryContainer,
                      shape: BoxShape.circle,
                    ),
                    child: Icon(
                      Icons.schedule,
                      color: theme.colorScheme.primary,
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          'Hourly reminder',
                          style: theme.textTheme.titleSmall
                              ?.copyWith(fontWeight: FontWeight.w700),
                        ),
                        const SizedBox(height: 2),
                        Text(
                          'Setiap jam (tepat di jam) mengingatkan Anda '
                          'mencatat pengeluaran/pemasukan.',
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: theme.colorScheme.onSurfaceVariant,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 8),
                  Switch(
                    value: _enabled ?? false,
                    onChanged: _busy ? null : _setReminder,
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Text(
            'Notifications',
            style: theme.textTheme.titleMedium
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 16),
          Padding(
            padding: const EdgeInsets.symmetric(vertical: 48),
            child: Column(
              children: [
                Icon(
                  Icons.notifications_off_outlined,
                  size: 56,
                  color: theme.colorScheme.onSurfaceVariant,
                ),
                const SizedBox(height: 12),
                Text(
                  'Belum ada notifikasi',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}
