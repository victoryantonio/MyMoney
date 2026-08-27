/// Management akun (dari tab Profil) — setara v1 Kotlin
/// `AccountManagementScreen` (ARCHITECTURE.md §4.4).
///
/// Tambah akun (nama, bank, saldo awal); edit nama/bank; nonaktifkan —
/// saat saldo ≠ 0 wajib memilih akun tujuan (saldo dipindah via transaksi
/// balancing di backend).
library;

import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../models/transaction_models.dart';

class AccountsScreen extends StatefulWidget {
  const AccountsScreen({super.key});

  @override
  State<AccountsScreen> createState() => _AccountsScreenState();
}

class _AccountsScreenState extends State<AccountsScreen> {
  late final ApiClient _api = ApiClient.instance(Supabase.instance.client);

  bool _loading = true;
  String? _error;
  List<AccountModel> _accounts = [];

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final accounts = await _api.fetchAccounts(includeInactive: true);
      if (!mounted) return;
      setState(() {
        _accounts = accounts;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  Future<void> _openAdd() async {
    final formKey = GlobalKey<FormState>();
    final nameCtrl = TextEditingController();
    final bankCtrl = TextEditingController();
    final balanceCtrl = TextEditingController(text: '0');

    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Tambah Akun'),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: nameCtrl,
                decoration: const InputDecoration(
                  labelText: 'Nama akun',
                  border: OutlineInputBorder(),
                ),
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Nama wajib diisi' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: bankCtrl,
                decoration: const InputDecoration(
                  labelText: 'Nama bank (opsional)',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: balanceCtrl,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: const InputDecoration(
                  labelText: 'Saldo awal',
                  prefixText: 'Rp ',
                  border: OutlineInputBorder(),
                ),
                validator: (v) {
                  final n = double.tryParse((v ?? '').replaceAll('.', ''));
                  if (n == null || n < 0) return 'Saldo tidak valid';
                  return null;
                },
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Batal'),
          ),
          FilledButton(
            onPressed: () async {
              if (!formKey.currentState!.validate()) return;
              final name = nameCtrl.text.trim();
              final bank = bankCtrl.text.trim();
              final balance =
                  double.tryParse(balanceCtrl.text.replaceAll('.', '')) ?? 0;
              final messenger = ScaffoldMessenger.of(context);
              Navigator.of(context).pop(true);
              try {
                await _api.createAccount(
                  accountName: name,
                  bankName: bank.isEmpty ? null : bank,
                  initialBalance: balance,
                );
                messenger.showSnackBar(
                  const SnackBar(content: Text('Akun ditambahkan')),
                );
                _load();
              } on ApiException catch (e) {
                messenger.showSnackBar(
                  SnackBar(content: Text(e.message)),
                );
              }
            },
            child: const Text('Simpan'),
          ),
        ],
      ),
    );
    if (saved == null) {
      // ditutup tanpa simpan
    }
  }

  Future<void> _openEdit(AccountModel account) async {
    final formKey = GlobalKey<FormState>();
    final nameCtrl = TextEditingController(text: account.accountName);
    final bankCtrl = TextEditingController(text: account.bankName ?? '');

    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Edit ${account.accountName}'),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: nameCtrl,
                decoration: const InputDecoration(
                  labelText: 'Nama akun',
                  border: OutlineInputBorder(),
                ),
                validator: (v) =>
                    (v == null || v.trim().isEmpty) ? 'Nama wajib diisi' : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: bankCtrl,
                decoration: const InputDecoration(
                  labelText: 'Nama bank (opsional)',
                  border: OutlineInputBorder(),
                ),
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Batal'),
          ),
          FilledButton(
            onPressed: () async {
              if (!formKey.currentState!.validate()) return;
              final name = nameCtrl.text.trim();
              final bank = bankCtrl.text.trim();
              final messenger = ScaffoldMessenger.of(context);
              Navigator.of(context).pop(true);
              try {
                await _api.updateAccount(
                  account.id,
                  accountName: name,
                  bankName: bank.isEmpty ? null : bank,
                );
                messenger.showSnackBar(
                  const SnackBar(content: Text('Akun diperbarui')),
                );
                _load();
              } on ApiException catch (e) {
                messenger.showSnackBar(
                  SnackBar(content: Text(e.message)),
                );
              }
            },
            child: const Text('Simpan'),
          ),
        ],
      ),
    );
    if (saved == null) {
      // ditutup tanpa simpan
    }
  }

  Future<void> _deactivate(AccountModel account) async {
    // Konfirmasi awal.
    final confirm = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Nonaktifkan akun?'),
        content: Text(
          'Akun "${account.accountName}" tidak akan muncul di daftar pilihan '
          'transaksi baru.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Batal'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: Theme.of(context).colorScheme.error,
            ),
            onPressed: () => Navigator.of(context).pop(true),
            child: const Text('Nonaktifkan'),
          ),
        ],
      ),
    );
    if (confirm != true) return;
    if (!mounted) return;

    final messenger = ScaffoldMessenger.of(context);

    String? targetId;
    if (account.currentBalance.abs() > 0.001) {
      // Saldo ≠ 0 → wajib pilih akun tujuan (saldo dipindah).
      final targets = _accounts
          .where((a) => a.id != account.id && a.isActive)
          .toList();
      if (targets.isEmpty) {
        messenger.showSnackBar(
          const SnackBar(
            content: Text(
              'Saldo akun ini belum 0 — buat akun aktif lain dulu untuk '
              'memindahkan saldo.',
            ),
          ),
        );
        return;
      }
      final chosen = await showDialog<String>(
        context: context,
        builder: (context) => SimpleDialog(
          title: Text(
            'Pindahkan saldo ${formatRupiah(account.currentBalance)} ke:',
          ),
          children: [
            for (final t in targets)
              SimpleDialogOption(
                onPressed: () => Navigator.of(context).pop(t.id),
                child: Text(t.label),
              ),
          ],
        ),
      );
      if (chosen == null) return;
      if (!mounted) return;
      targetId = chosen;
    }

    try {
      await _api.deactivateAccount(account.id, targetAccountId: targetId);
      messenger.showSnackBar(
        const SnackBar(content: Text('Akun dinonaktifkan')),
      );
      _load();
    } on ApiException catch (e) {
      messenger.showSnackBar(
        SnackBar(content: Text(e.message)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Akun')),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openAdd,
        icon: const Icon(Icons.add),
        label: const Text('Tambah'),
      ),
      body: _buildBody(context),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.cloud_off, size: 48),
              const SizedBox(height: 12),
              Text(_error!, textAlign: TextAlign.center),
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: _load,
                icon: const Icon(Icons.refresh),
                label: const Text('Coba lagi'),
              ),
            ],
          ),
        ),
      );
    }

    if (_accounts.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.account_balance_outlined, size: 56),
              const SizedBox(height: 12),
              const Text('Belum ada akun'),
              const SizedBox(height: 4),
              Text(
                'Tambahkan akun kas/bank untuk mulai mencatat',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      );
    }

    final active = _accounts.where((a) => a.isActive).toList();
    final inactive = _accounts.where((a) => !a.isActive).toList();

    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        physics: const AlwaysScrollableScrollPhysics(),
        padding: const EdgeInsets.fromLTRB(16, 8, 16, 96),
        children: [
          if (active.isNotEmpty) ...[
            for (final a in active)
              _AccountCard(
                account: a,
                onEdit: () => _openEdit(a),
                onDeactivate: () => _deactivate(a),
              ),
          ],
          if (inactive.isNotEmpty) ...[
            const SizedBox(height: 16),
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Text(
                'Nonaktif',
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: Theme.of(context).colorScheme.onSurfaceVariant,
                      fontWeight: FontWeight.w700,
                    ),
              ),
            ),
            for (final a in inactive)
              _AccountCard(
                account: a,
                onEdit: null,
                onDeactivate: null,
              ),
          ],
        ],
      ),
    );
  }
}

class _AccountCard extends StatelessWidget {
  const _AccountCard({
    required this.account,
    required this.onEdit,
    required this.onDeactivate,
  });

  final AccountModel account;
  final VoidCallback? onEdit;
  final VoidCallback? onDeactivate;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final positive = account.currentBalance >= 0;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: theme.colorScheme.outlineVariant),
      ),
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: theme.colorScheme.primaryContainer,
          child: Icon(
            Icons.account_balance_outlined,
            color: theme.colorScheme.primary,
          ),
        ),
        title: Row(
          children: [
            Flexible(
              child: Text(
                account.accountName,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(fontWeight: FontWeight.w600),
              ),
            ),
            if (!account.isActive) ...[
              const SizedBox(width: 6),
              Chip(
                label: const Text('Nonaktif'),
                labelStyle: const TextStyle(fontSize: 11),
                visualDensity: VisualDensity.compact,
                materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ],
          ],
        ),
        subtitle: Text(
          account.bankName?.isNotEmpty == true
              ? account.bankName!
              : 'Saldo awal ${formatRupiah(account.initialBalance)}',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              formatRupiah(account.currentBalance),
              style: TextStyle(
                fontWeight: FontWeight.w700,
                color: positive
                    ? theme.colorScheme.onSurface
                    : theme.colorScheme.error,
              ),
            ),
            if (onEdit != null) ...[
              const SizedBox(width: 4),
              PopupMenuButton<String>(
                onSelected: (v) {
                  if (v == 'edit') onEdit!();
                  if (v == 'deactivate') onDeactivate!();
                },
                itemBuilder: (context) => [
                  PopupMenuItem(
                    value: 'edit',
                    child: const ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(Icons.edit_outlined),
                      title: Text('Edit'),
                    ),
                  ),
                  PopupMenuItem(
                    value: 'deactivate',
                    child: const ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: Icon(Icons.block),
                      title: Text('Nonaktifkan'),
                    ),
                  ),
                ],
              ),
            ],
          ],
        ),
      ),
    );
  }
}
