import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'core/config.dart';
import 'core/notification_service.dart';
import 'core/providers.dart';
import 'core/theme_controller.dart';
import 'screens/auth_screen.dart';
import 'screens/main_shell.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final themeController = await ThemeController.load();

  if (!AppConfig.isConfigured) {
    // Tanpa config: hanya hint setup (tidak ada network).
    runApp(
      ProviderScope(
        overrides: [
          themeControllerProvider.overrideWith((ref) => themeController),
        ],
        child: const MyMoneyApp(supabaseAvailable: false),
      ),
    );
    return;
  }

  await Supabase.initialize(
    url: AppConfig.supabaseUrl,
    publishableKey: AppConfig.supabaseAnonKey,
  );
  await NotificationService.instance.init();

  runApp(
    ProviderScope(
      overrides: [
        themeControllerProvider.overrideWith((ref) => themeController),
      ],
      child: const MyMoneyApp(supabaseAvailable: true),
    ),
  );
}

class MyMoneyApp extends ConsumerWidget {
  const MyMoneyApp({super.key, required this.supabaseAvailable});

  final bool supabaseAvailable;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final themeMode = ref.watch(themeControllerProvider).mode;
    return MaterialApp(
      title: 'My Money',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF3B5B8C), // dusty slate blue (DESIGN.md)
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      darkTheme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF3B5B8C),
          brightness: Brightness.dark,
        ),
        useMaterial3: true,
      ),
      themeMode: themeMode,
      home: supabaseAvailable ? const AuthGate() : const _SetupHint(),
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    final client = Supabase.instance.client;
    return StreamBuilder<AuthState>(
      stream: client.auth.onAuthStateChange,
      builder: (context, snapshot) {
        final session = client.auth.currentSession;
        if (session != null) {
          return MainShell(supabase: client);
        }
        return const AuthScreen();
      },
    );
  }
}

class _SetupHint extends StatelessWidget {
  const _SetupHint();

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, size: 48),
              const SizedBox(height: 12),
              const Text('Supabase not configured'),
              const SizedBox(height: 8),
              Text(
                'Jalankan dengan:\n'
                'flutter run --dart-define=SUPABASE_URL=... '
                '--dart-define=SUPABASE_ANON_KEY=...',
                textAlign: TextAlign.center,
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }
}
