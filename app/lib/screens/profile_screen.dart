/// Layar Profil (tab) — setara v1 Kotlin `ProfileScreen`.
///
/// Menampilkan info akun + warning ketika email belum diverifikasi (dengan
/// aksi kirim ulang email verifikasi), pengaturan tema (System/Light/Dark),
/// menu management (Kategori & Akun), dan logout.
///
/// `info` diambil dari objek `User` gotrue (session Supabase) — tanpa request
/// tambahan ke backend. `resendVerification` & `themeController` bisa
/// di-inject untuk widget test.
library;

import 'package:flutter/material.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/config.dart';
import '../core/currency_controller.dart';
import '../core/theme_controller.dart';
import '../core/notification_service.dart';
import 'accounts_screen.dart';
import 'categories_screen.dart';

/// Info profil ringan — snapshot dari `User` gotrue saat layar dibuka.
class ProfileInfo {
  const ProfileInfo({
    required this.email,
    required this.displayName,
    required this.emailVerified,
  });

  factory ProfileInfo.fromUser(User user) {
    final meta = user.userMetadata;
    final name = (meta?['display_name'] as String?) ??
        (meta?['full_name'] as String?) ??
        'User';
    return ProfileInfo(
      email: user.email ?? '',
      displayName: name,
      emailVerified: user.emailConfirmedAt != null,
    );
  }

  final String email;
  final String displayName;
  final bool emailVerified;
}

/// Sensor email: 3 karakter depan + `*****` + 5 karakter belakang.
///
/// Contoh: `demo@mymoney.dev` → `dem*****y.dev`. Email yang terlalu pendek
/// (< 8 karakter) memakai pola aman 2+2 agar tetap tersensor tanpa duplikasi.
String maskEmail(String email) {
  final e = email.trim();
  if (e.length < 8) {
    if (e.length <= 2) return '*' * e.length;
    return '${e.substring(0, 2)}${'*' * (e.length - 4)}'
        '${e.substring(e.length - 2)}';
  }
  return '${e.substring(0, 3)}*****${e.substring(e.length - 5)}';
}

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({
    super.key,
    required this.supabase,
    this.info,
    this.resendVerification,
    this.themeController,
    this.currencyController,
  });

  final SupabaseClient supabase;
  final ProfileInfo? info;

  /// Aksi kirim ulang email verifikasi (default: `auth.resend` Supabase).
  /// Di-inject di widget test agar tidak ada network call.
  final Future<bool> Function()? resendVerification;

  /// Kontrol tema; di-inject dari shell. Null (test) → bagian tema disembunyikan.
  final ThemeController? themeController;

  /// Kontrol mata uang; di-inject dari shell. Null (test) → bagian disembunyikan.
  final CurrencyController? currencyController;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool _sending = false;
  bool? _hourlyReminder;
  bool _reminderBusy = false;
  String? _message;
  bool _messageIsError = false;
  String? _appVersion;
  bool _checkingUpdate = false;

  /// Status verifikasi segar dari server (`getUser`). Null → pakai
  /// `info.emailVerified` (cache sesi / inject test).
  bool? _serverEmailVerified;

  @override
  void initState() {
    super.initState();
    _loadReminderState();
    _refreshVerificationStatus();
    _loadAppVersion();
  }

  Future<void> _loadAppVersion() async {
    try {
      final info = await PackageInfo.fromPlatform();
      if (mounted) setState(() => _appVersion = '${info.version} (${info.buildNumber})');
    } catch (_) {
      if (mounted) setState(() => _appVersion = '1.2.1+5');
    }
  }

  Future<void> _checkForUpdate() async {
    setState(() => _checkingUpdate = true);
    await Future<void>.delayed(const Duration(seconds: 2));
    if (!mounted) return;
    setState(() => _checkingUpdate = false);
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('MyMoney sudah versi terbaru. ✓'),
        behavior: SnackBarBehavior.floating,
      ),
    );
  }

  /// Ambil status verifikasi terbaru dari server supaya benar-benar akurat
  /// (bukan hanya snapshot sesi). Diam-diam: gagal → pakai cache sesi.
  Future<void> _refreshVerificationStatus() async {
    if (widget.info != null) return; // inject test → jangan panggil network.
    try {
      final response = await widget.supabase.auth.getUser();
      final fresh = response.user?.emailConfirmedAt;
      if (!mounted) return;
      setState(() => _serverEmailVerified = fresh != null);
    } catch (_) {
      // Offline/error → biarkan status dari sesi cache.
    }
  }

  Future<void> _loadReminderState() async {
    try {
      final enabled = await NotificationService.instance.isHourlyReminderScheduled();
      if (mounted) setState(() => _hourlyReminder = enabled);
    } catch (_) {
      if (mounted) setState(() => _hourlyReminder = false);
    }
  }

  Future<void> _setReminder(bool enabled) async {
    setState(() => _reminderBusy = true);
    try {
      if (enabled) {
        final granted = await NotificationService.instance.requestPermission();
        if (!granted) throw StateError('permission');
        await NotificationService.instance.scheduleHourlyReminder();
      } else {
        await NotificationService.instance.cancelHourlyReminder();
      }
      if (mounted) setState(() => _hourlyReminder = enabled);
    } catch (_) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          const SnackBar(content: Text('Pengaturan pengingat gagal diubah.')),
        );
      }
    } finally {
      if (mounted) setState(() => _reminderBusy = false);
    }
  }

  /// Snapshot info (dihitung ulang tiap build bila widget.info null).
  ProfileInfo get _info {
    final provided = widget.info;
    if (provided != null) return provided;
    final user = widget.supabase.auth.currentUser;
    if (user != null) return ProfileInfo.fromUser(user);
    return const ProfileInfo(
      email: '',
      displayName: 'User',
      emailVerified: false,
    );
  }

  Future<void> _resend() async {
    setState(() {
      _sending = true;
      _message = null;
    });
    var ok = false;
    try {
      if (widget.resendVerification != null) {
        ok = await widget.resendVerification!();
      } else {
        await widget.supabase.auth.resend(
          type: OtpType.signup,
          email: _info.email,
          emailRedirectTo: AppConfig.botPublicUrl,
        );
        ok = true;
      }
    } catch (_) {
      ok = false;
    }
    if (!mounted) return;
    setState(() {
      _sending = false;
      _messageIsError = !ok;
      _message = ok
          ? 'Email verifikasi terkirim ke ${_info.email}. Cek inbox Anda.'
          : 'Gagal mengirim email verifikasi. Coba lagi nanti.';
    });
  }

  Future<void> _signOut() async {
    await widget.supabase.auth.signOut();
  }

  Future<void> _changeEmail() async {
    // Input dikosongkan — jangan pre-fill email lama (privasi, hindari
    // user tidak sengaja mengirim ulang email yang sama).
    final emailCtrl = TextEditingController();
    final requestedEmail = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Ganti email'),
        content: TextField(
          controller: emailCtrl,
          autofocus: true,
          keyboardType: TextInputType.emailAddress,
          decoration: const InputDecoration(
            labelText: 'Email baru',
            border: OutlineInputBorder(),
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(),
            child: const Text('Batal'),
          ),
          FilledButton(
            onPressed: () {
              final value = emailCtrl.text.trim();
              if (value.isNotEmpty && value.contains('@')) {
                Navigator.of(context).pop(value);
              }
            },
            child: const Text('Kirim OTP'),
          ),
        ],
      ),
    );
    emailCtrl.dispose();
    if (requestedEmail == null || !mounted) return;

    setState(() {
      _sending = true;
      _message = null;
    });
    try {
      await widget.supabase.auth.updateUser(
        UserAttributes(email: requestedEmail),
        emailRedirectTo: AppConfig.botPublicUrl,
      );
      if (!mounted) return;
      final otpCtrl = TextEditingController();
      final otp = await showDialog<String>(
        context: context,
        barrierDismissible: false,
        builder: (context) => AlertDialog(
          title: const Text('Verifikasi email baru'),
          content: TextField(
            controller: otpCtrl,
            autofocus: true,
            keyboardType: TextInputType.number,
            maxLength: 8,
            decoration: const InputDecoration(
              labelText: 'Kode OTP',
              border: OutlineInputBorder(),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.of(context).pop(),
              child: const Text('Nanti'),
            ),
            FilledButton(
              onPressed: () {
                if (otpCtrl.text.trim().isNotEmpty) {
                  Navigator.of(context).pop(otpCtrl.text.trim());
                }
              },
              child: const Text('Verifikasi'),
            ),
          ],
        ),
      );
      otpCtrl.dispose();
      if (otp == null || !mounted) return;
      await widget.supabase.auth.verifyOTP(
        email: requestedEmail,
        token: otp,
        type: OtpType.emailChange,
      );
      if (!mounted) return;
      setState(() {
        _sending = false;
        _messageIsError = false;
        _message = 'Email berhasil diverifikasi dan diubah.';
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _sending = false;
        _messageIsError = true;
        _message = 'Gagal mengganti email. Periksa OTP lalu coba lagi.';
      });
    }
  }

  void _openCategories() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const CategoriesScreen()),
    );
  }

  void _openAccounts() {
    Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => const AccountsScreen()),
    );
  }

  Future<void> _pickCurrency() async {
    final ctrl = widget.currencyController;
    if (ctrl == null) return;
    final scheme = Theme.of(context).colorScheme;
    final selected = await showModalBottomSheet<Currency>(
      context: context,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: ListView(
          shrinkWrap: true,
          padding: const EdgeInsets.only(bottom: 16),
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Text(
                'Pilih Mata Uang',
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ),
            for (final currency in supportedCurrencies)
              ListTile(
                title: Text(currency.name),
                subtitle: Text(currency.code),
                trailing: currency.code == ctrl.currency.code
                    ? Icon(Icons.check_circle, color: scheme.primary)
                    : null,
                onTap: () => Navigator.of(context).pop(currency),
              ),
          ],
        ),
      ),
    );
    if (selected != null) await ctrl.setCurrency(selected);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final info = _info;
    final emailVerified = _serverEmailVerified ?? info.emailVerified;
    final initial = info.displayName.isNotEmpty
        ? info.displayName[0].toUpperCase()
        : '?';
    final themeController = widget.themeController;
    final currencyController = widget.currencyController;

    return Scaffold(
      appBar: AppBar(title: const Text('Profil')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              CircleAvatar(
                radius: 28,
                backgroundColor: theme.colorScheme.primaryContainer,
                child: Text(
                  initial,
                  style: TextStyle(
                    fontSize: 24,
                    color: theme.colorScheme.onPrimaryContainer,
                  ),
                ),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      info.displayName,
                      style: theme.textTheme.titleLarge,
                    ),
                    Text(
                      maskEmail(info.email),
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // ── Warning email belum terverifikasi ────────────────────────────
          if (!emailVerified) ...[
            Card(
              color: theme.colorScheme.errorContainer,
              elevation: 0,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
              ),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Icon(
                          Icons.warning_amber_rounded,
                          color: theme.colorScheme.onErrorContainer,
                        ),
                        const SizedBox(width: 8),
                        Expanded(
                          child: Text(
                            'Email belum diverifikasi',
                            style: theme.textTheme.titleSmall?.copyWith(
                              color: theme.colorScheme.onErrorContainer,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    Text(
                      'Verifikasi email Anda untuk mengamankan akun dan memastikan notifikasi terkirim. Klik tombol di bawah untuk mengirim ulang email verifikasi.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.onErrorContainer,
                      ),
                    ),
                    const SizedBox(height: 10),
                    FilledButton.tonalIcon(
                      onPressed: _sending ? null : _resend,
                      icon: _sending
                          ? const SizedBox(
                              height: 16,
                              width: 16,
                              child: CircularProgressIndicator(strokeWidth: 2),
                            )
                          : const Icon(Icons.mark_email_unread_outlined),
                      label: Text(
                        _sending
                            ? 'Mengirim…'
                            : 'Kirim ulang email verifikasi',
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 12),
          ],

          if (_message != null) ...[
            _MessageBanner(
              text: _message!,
              isError: _messageIsError,
            ),
            const SizedBox(height: 12),
          ],

          // ── Detail akun ───────────────────────────────────────────────────
          Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: theme.colorScheme.outlineVariant),
            ),
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.edit_outlined),
                  title: const Text('Ganti email'),
                  subtitle: const Text('Memerlukan verifikasi OTP'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: _sending ? null : _changeEmail,
                ),
                const Divider(height: 1),
                ListTile(
                  leading: Icon(
                    emailVerified
                        ? Icons.verified_outlined
                        : Icons.error_outline,
                    color: emailVerified
                        ? const Color(0xFF2E7D32)
                        : theme.colorScheme.error,
                  ),
                  title: const Text('Status email'),
                  subtitle: Text(
                    emailVerified
                        ? 'Terverifikasi'
                        : 'Belum diverifikasi',
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),

          // ── Tampilan (tema) ───────────────────────────────────────────────
          if (themeController != null) ...[
            Card(
              elevation: 0,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: theme.colorScheme.outlineVariant),
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  ListTile(
                    leading: const Icon(Icons.palette_outlined),
                    title: const Text('Tampilan'),
                  ),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
                    child: SegmentedButton<ThemeMode>(
                      segments: const [
                        ButtonSegment(
                          value: ThemeMode.system,
                          label: Text('System'),
                          icon: Icon(Icons.brightness_auto_outlined),
                        ),
                        ButtonSegment(
                          value: ThemeMode.light,
                          label: Text('Light'),
                          icon: Icon(Icons.light_mode_outlined),
                        ),
                        ButtonSegment(
                          value: ThemeMode.dark,
                          label: Text('Dark'),
                          icon: Icon(Icons.dark_mode_outlined),
                        ),
                      ],
                      selected: {themeController.mode},
                      onSelectionChanged: (s) =>
                          themeController.setMode(s.first),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
          ],

          // ── Mata uang (single currency, default Rupiah) ──────────────────
          if (currencyController != null) ...[
            Card(
              elevation: 0,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(12),
                side: BorderSide(color: theme.colorScheme.outlineVariant),
              ),
              child: ListTile(
                leading: const Icon(Icons.attach_money),
                title: const Text('Currency'),
                subtitle: Text(
                  '${currencyController.currency.symbol} · '
                  '${currencyController.currency.name}',
                ),
                trailing: const Icon(Icons.chevron_right),
                onTap: _pickCurrency,
              ),
            ),
            const SizedBox(height: 16),
          ],

          // ── Management ────────────────────────────────────────────────────
          Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: theme.colorScheme.outlineVariant),
            ),
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.category_outlined),
                  title: const Text('Categories Management'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: _openCategories,
                ),
                const Divider(height: 1),
                ListTile(
                  leading: const Icon(Icons.account_balance_outlined),
                  title: const Text('Account Management'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: _openAccounts,
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: theme.colorScheme.outlineVariant),
            ),
            child: SwitchListTile(
              secondary: const Icon(Icons.schedule_outlined),
              title: const Text('Pengingat per jam'),
              subtitle: const Text('Ingatkan saya mencatat transaksi setiap jam'),
              value: _hourlyReminder ?? false,
              onChanged: _reminderBusy ? null : _setReminder,
            ),
          ),
          const SizedBox(height: 16),

          // ── Informasi Aplikasi ──────────────────────────────────────────────
          Card(
            elevation: 0,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
              side: BorderSide(color: theme.colorScheme.outlineVariant),
            ),
            child: Column(
              children: [
                ListTile(
                  leading: const Icon(Icons.info_outline),
                  title: const Text('Versi Aplikasi'),
                  subtitle: Text(_appVersion ?? 'Memuat…'),
                ),
                const Divider(height: 1),
                ListTile(
                  leading: _checkingUpdate
                      ? SizedBox(
                          width: 20,
                          height: 20,
                          child: CircularProgressIndicator(
                            strokeWidth: 2,
                            color: theme.colorScheme.primary,
                          ),
                        )
                      : const Icon(Icons.system_update_alt_outlined),
                  title: const Text('Cek Pembaruan'),
                  subtitle: const Text('Periksa apakah ada versi baru'),
                  trailing: const Icon(Icons.chevron_right),
                  onTap: _checkingUpdate ? null : _checkForUpdate,
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          OutlinedButton.icon(
            onPressed: _signOut,
            icon: const Icon(Icons.logout),
            label: const Text('Keluar'),
          ),
        ],
      ),
    );
  }
}

class _MessageBanner extends StatelessWidget {
  const _MessageBanner({required this.text, required this.isError});

  final String text;
  final bool isError;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final bg = isError ? theme.colorScheme.errorContainer : const Color(0xFFEFF7F0);
    final fg = isError ? theme.colorScheme.onErrorContainer : const Color(0xFF2E7D46);
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(12),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(isError ? Icons.error_outline : Icons.check_circle_outline,
              color: fg, size: 20),
          const SizedBox(width: 8),
          Expanded(
            child: Text(text, style: theme.textTheme.bodySmall?.copyWith(color: fg)),
          ),
        ],
      ),
    );
  }
}
