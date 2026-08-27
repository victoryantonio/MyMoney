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
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/theme_controller.dart';
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

class ProfileScreen extends StatefulWidget {
  const ProfileScreen({
    super.key,
    required this.supabase,
    this.info,
    this.resendVerification,
    this.themeController,
  });

  final SupabaseClient supabase;
  final ProfileInfo? info;

  /// Aksi kirim ulang email verifikasi (default: `auth.resend` Supabase).
  /// Di-inject di widget test agar tidak ada network call.
  final Future<bool> Function()? resendVerification;

  /// Kontrol tema; di-inject dari shell. Null (test) → bagian tema disembunyikan.
  final ThemeController? themeController;

  @override
  State<ProfileScreen> createState() => _ProfileScreenState();
}

class _ProfileScreenState extends State<ProfileScreen> {
  bool _sending = false;
  String? _message;
  bool _messageIsError = false;

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

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final info = _info;
    final initial = info.displayName.isNotEmpty
        ? info.displayName[0].toUpperCase()
        : '?';
    final themeController = widget.themeController;

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
                      info.email,
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
          if (!info.emailVerified) ...[
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
                  leading: const Icon(Icons.alternate_email),
                  title: const Text('Email'),
                  subtitle: Text(info.email),
                ),
                const Divider(height: 1),
                ListTile(
                  leading: Icon(
                    info.emailVerified
                        ? Icons.verified_outlined
                        : Icons.error_outline,
                    color: info.emailVerified
                        ? const Color(0xFF2E7D32)
                        : theme.colorScheme.error,
                  ),
                  title: const Text('Status email'),
                  subtitle: Text(
                    info.emailVerified
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
