/// Gerbang onboarding zona waktu (Req 5).
///
/// Setelah user login pertama kali (`profiles.timezone_confirmed == false`),
/// aplikasi menampilkan form pilih zona waktu — nilai awalnya diperkirakan
/// dari perangkat. Setelah disimpan, gerbang tidak muncul lagi; user tetap
/// bisa mengubahnya kapan saja di menu Profil.
///
/// Storage tetap UTC; zona waktu ini hanya dipakai saat MEMBACA/menampilkan
/// waktu, dan di-snapshot per transaksi sehingga riwayat lama tidak bergeser.
///
/// `loadProfile`/`saveTimezone` dapat di-inject di widget test agar tidak ada
/// panggilan jaringan.
library;

import 'package:flutter/material.dart';

import '../core/timezones.dart';
import '../models/profile_settings.dart';
import '../widgets/timezone_picker.dart';

class TimezoneGate extends StatefulWidget {
  const TimezoneGate({
    super.key,
    required this.child,
    this.loadProfile,
    this.saveTimezone,
  });

  /// Konten aplikasi yang ditampilkan setelah zona waktu dikonfirmasi.
  final Widget child;

  /// GET /api/profile. Null (setup hint / test) → gerbang dilewati.
  final Future<ProfileSettings> Function()? loadProfile;

  /// PATCH /api/profile untuk menyimpan zona waktu terpilih.
  final Future<void> Function(String timezone)? saveTimezone;

  @override
  State<TimezoneGate> createState() => _TimezoneGateState();
}

class _TimezoneGateState extends State<TimezoneGate> {
  bool _loading = true;
  bool _needsChoice = false;
  bool _saving = false;
  String _current = fallbackTimezone;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    final loader = widget.loadProfile;
    if (loader == null) {
      setState(() {
        _loading = false;
        _needsChoice = false;
      });
      return;
    }
    try {
      final settings = await loader();
      if (!mounted) return;
      setState(() {
        _loading = false;
        _needsChoice = !settings.timezoneConfirmed;
        // Belum dikonfirmasi → pakai perkiraan dari perangkat sebagai nilai
        // awal, supaya user tidak perlu mencari nama zona waktunya.
        _current = settings.timezoneConfirmed
            ? settings.timezone
            : guessDeviceTimezoneName();
      });
    } catch (_) {
      // Jaringan bermasalah → jangan blokir aplikasi; gerbang dilewati dan
      // zona waktu default backend ('Asia/Jakarta') yang dipakai.
      if (mounted) {
        setState(() {
          _loading = false;
          _needsChoice = false;
        });
      }
    }
  }

  Future<void> _pick() async {
    final chosen = await showTimezonePickerSheet(context, current: _current);
    if (chosen == null || !mounted) return;
    setState(() => _current = chosen);
  }

  Future<void> _confirm() async {
    final saver = widget.saveTimezone;
    if (saver == null) {
      setState(() => _needsChoice = false);
      return;
    }
    setState(() => _saving = true);
    try {
      await saver(_current);
      if (!mounted) return;
      setState(() {
        _saving = false;
        _needsChoice = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('Gagal menyimpan zona waktu. Coba lagi.'),
          behavior: SnackBarBehavior.floating,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (!_needsChoice) return widget.child;

    final theme = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Spacer(),
              Icon(Icons.public, size: 56, color: theme.colorScheme.primary),
              const SizedBox(height: 16),
              Text(
                'Pilih Zona Waktu Anda',
                textAlign: TextAlign.center,
                style: theme.textTheme.headlineSmall
                    ?.copyWith(fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 12),
              Text(
                'Transaksi disimpan dalam UTC, lalu ditampilkan memakai zona '
                'waktu pilihan Anda. Zona waktu ini juga disimpan bersama '
                'setiap transaksi, jadi menggantinya nanti tidak mengubah '
                'tanggal transaksi yang sudah tercatat.',
                textAlign: TextAlign.center,
                style: theme.textTheme.bodyMedium
                    ?.copyWith(color: theme.colorScheme.onSurfaceVariant),
              ),
              const SizedBox(height: 24),
              Card(
                elevation: 0,
                shape: RoundedRectangleBorder(
                  borderRadius: BorderRadius.circular(12),
                  side: BorderSide(color: theme.colorScheme.outlineVariant),
                ),
                child: ListTile(
                  leading: const Icon(Icons.schedule_outlined),
                  title: Text(timezoneLabel(_current)),
                  subtitle: const Text('Diperkirakan dari perangkat Anda'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: _saving ? null : _pick,
                ),
              ),
              const Spacer(),
              FilledButton(
                onPressed: _saving ? null : _confirm,
                child: _saving
                    ? const SizedBox(
                        width: 20,
                        height: 20,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : const Text('Lanjut'),
              ),
              TextButton(
                onPressed:
                    _saving ? null : () => setState(() => _needsChoice = false),
                child: const Text('Nanti saja'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
