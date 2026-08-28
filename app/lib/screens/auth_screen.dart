import 'dart:async';

import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:supabase_flutter/supabase_flutter.dart';

/// Layar Auth minimal (Fase 0 checkpoint): login/register via Supabase Auth.
/// Client bisa di-inject untuk widget test; default memakai Supabase.instance.
class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key, this.client});

  final SupabaseClient? client;

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _fullName = TextEditingController();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _fullNameFocus = FocusNode();
  final _passwordFocus = FocusNode();
  bool _isLogin = true;
  bool _loading = false;
  String? _error;
  String? _success;

  SupabaseClient get _client => widget.client ?? Supabase.instance.client;

  @override
  void dispose() {
    _fullName.dispose();
    _email.dispose();
    _password.dispose();
    _fullNameFocus.dispose();
    _passwordFocus.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final fullName = _fullName.text.trim();
    if (!_isLogin && fullName.isEmpty) {
      setState(() => _error = 'Full name is required.');
      return;
    }
    setState(() {
      _loading = true;
      _error = null;
      _success = null;
    });
    try {
      if (_isLogin) {
        await _client.auth.signInWithPassword(
          email: _email.text.trim(),
          password: _password.text,
        );
      } else {
        final res = await _client.auth.signUp(
          email: _email.text.trim(),
          password: _password.text,
          data: {'display_name': fullName},
        );
        if (res.session == null && res.user != null) {
          // GoTrue anti-enumeration: kalau email SUDAH terdaftar, respons
          // mengembalikan user dengan identities KOSONG & tanpa session —
          // dan TIDAK ada email verifikasi baru yang dikirim. Tolak.
          final isNewSignup = res.user!.identities?.isNotEmpty ?? false;
          if (!isNewSignup) {
            if (mounted) {
              setState(() {
                _error = 'Email sudah terdaftar. Silakan login dengan '
                    'password Anda.';
              });
            }
            return;
          }
          // Email baru + confirmation aktif: beri tahu user cek email.
          if (mounted) {
            setState(() {
              _success =
                  'Registration successful! Please check your email for verification before logging in.';
            });
          }
          return;
        }
      }
    } on AuthException catch (e) {
      if (mounted) setState(() => _error = e.message);
    } on http.ClientException {
      // DNS / koneksi gagal (mis. "Failed host lookup ... errno 7").
      if (mounted) {
        setState(() => _error =
            'Unable to connect to the server. Check your internet connection, then try again.');
      }
    } on TimeoutException {
      if (mounted) {
        setState(() => _error = 'The connection to the server timed out. Please try again.');
      }
    } catch (_) {
      if (mounted) {
        setState(() => _error = 'An unexpected error occurred. Please try again.');
      }
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 400),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                ClipRRect(
                  borderRadius: BorderRadius.circular(16),
                  child: Image.asset(
                    'assets/icon/icon.png',
                    width: 72,
                    height: 72,
                  ),
                ),
                const SizedBox(height: 8),
                Text(
                  'My Money',
                  textAlign: TextAlign.center,
                  style: Theme.of(context).textTheme.headlineMedium,
                ),
                const SizedBox(height: 24),
                if (!_isLogin) ...[
                  TextField(
                    controller: _fullName,
                    focusNode: _fullNameFocus,
                    textCapitalization: TextCapitalization.words,
                    textInputAction: TextInputAction.next,
                    onSubmitted: (_) => FocusScope.of(context).nextFocus(),
                    decoration: const InputDecoration(
                      labelText: 'Full Name',
                      border: OutlineInputBorder(),
                    ),
                  ),
                  const SizedBox(height: 12),
                ],
                TextField(
                  controller: _email,
                  keyboardType: TextInputType.emailAddress,
                  textInputAction: TextInputAction.next,
                  onSubmitted: (_) => _passwordFocus.requestFocus(),
                  decoration: const InputDecoration(
                    labelText: 'Email',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _password,
                  obscureText: true,
                  focusNode: _passwordFocus,
                  textInputAction: TextInputAction.done,
                  onSubmitted: (_) => _submit(),
                  decoration: const InputDecoration(
                    labelText: 'Password',
                    border: OutlineInputBorder(),
                  ),
                ),
                if (_error != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    _error!,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.error,
                    ),
                  ),
                ],
                if (_success != null) ...[
                  const SizedBox(height: 12),
                  Text(
                    _success!,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      color: Theme.of(context).colorScheme.primary,
                    ),
                  ),
                ],
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _loading ? null : _submit,
                  child: _loading
                      ? const SizedBox(
                          height: 18,
                          width: 18,
                          child: CircularProgressIndicator(strokeWidth: 2),
                        )
                      : Text(_isLogin ? 'Login' : 'Register'),
                ),
                TextButton(
                  onPressed: () => setState(() {
                    _isLogin = !_isLogin;
                    _error = null;
                    _success = null;
                  }),
                  child: Text(_isLogin
                      ? "Don't have an account yet? Register"
                      : "Already have an account? Login"),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
