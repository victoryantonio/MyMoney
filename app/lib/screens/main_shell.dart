/// Shell utama setelah login: bottom navigation 4 tab.
///
/// Setara v1 Kotlin `MainScreen.kt` — Dashboard / Transaksi / Profil.
/// Setiap tab punya Scaffold sendiri;
/// IndexedStack menjaga state setiap tab saat berpindah.
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/api_client.dart';
import '../core/providers.dart';
import '../core/theme_controller.dart';
import 'dashboard_screen.dart';
import 'profile_screen.dart';
import 'transaction_form_screen.dart';
import 'transactions_screen.dart';

class MainShell extends ConsumerStatefulWidget {
  const MainShell({super.key, required this.supabase});

  final SupabaseClient supabase;

  @override
  ConsumerState<MainShell> createState() => _MainShellState();
}

class _MainShellState extends ConsumerState<MainShell> {
  int _index = 0;
  int _dashboardRefreshToken = 0;
  final Set<int> _visitedTabs = {0};
  late final ApiClient _api = ApiClient.instance(widget.supabase);

  Widget _tab(int index, ThemeController themeController) {
    if (!_visitedTabs.contains(index)) return const SizedBox.shrink();
    switch (index) {
      case 0:
        return DashboardScreen(
          supabase: widget.supabase,
          refreshToken: _dashboardRefreshToken,
        );
      case 1:
        return const TransactionsScreen();
      case 2:
        return ProfileScreen(
          supabase: widget.supabase,
          themeController: themeController,
        );
    }
    return const SizedBox.shrink();
  }

  @override
  Widget build(BuildContext context) {
    final themeController = ref.watch(themeControllerProvider);
    return Scaffold(
      body: IndexedStack(
        index: _index,
        children: [
          for (var i = 0; i < 3; i++) _tab(i, themeController),
        ],
      ),
      floatingActionButton: FloatingActionButton(
        heroTag: 'global-add-transaction',
        tooltip: 'Tambah transaksi',
        onPressed: () => Navigator.of(context).push(
          MaterialPageRoute<void>(
            builder: (_) => TransactionFormScreen(api: _api),
          ),
        ),
        child: const Icon(Icons.add),
      ),
      bottomNavigationBar: NavigationBar(
        selectedIndex: _index,
        onDestinationSelected: (i) => setState(() {
          _visitedTabs.add(i);
          _index = i;
          if (i == 0) _dashboardRefreshToken++;
        }),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard),
            label: 'Dashboard',
          ),
          NavigationDestination(
            icon: Icon(Icons.receipt_long_outlined),
            selectedIcon: Icon(Icons.receipt_long),
            label: 'Transaksi',
          ),
          NavigationDestination(
            icon: Icon(Icons.person_outline),
            selectedIcon: Icon(Icons.person),
            label: 'Profil',
          ),
        ],
      ),
    );
  }
}
