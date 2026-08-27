/// Dashboard (setara v1 Kotlin DashboardScreen.kt, DESIGN.md §8).
///
/// Urutan card (kiri→kanan): Total Saldo → Income/Expense/Net → Arus Kas
/// (line chart) → Breakdown Kategori (donut + daftar + transaksi terbaru).
///
/// Data dari backend REST (`GET /api/reports/summary`, `/trend`,
/// `/api/accounts`, `/api/categories`, `/api/transactions`) —
/// Flutter = thin client, semua agregasi di SQL backend (ARCHITECTURE §3.1).
library;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/api_client.dart';
import '../core/app_colors.dart';
import '../core/format.dart';
import '../models/report_models.dart';
import '../models/transaction_models.dart';
import '../widgets/trend_chart.dart';
import 'receipt_screen.dart';
import 'transaction_list_screen.dart';
import 'transaction_form_screen.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key, required this.supabase, this.refreshToken = 0});

  final SupabaseClient supabase;
  final int refreshToken;

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  late final ApiClient _api = ApiClient.instance(widget.supabase);

  String _period = 'month'; // 'today' | 'week' | 'month' | 'custom'
  bool _loading = true;
  String? _error;

  ReportSummary? _summary;
  ReportTrend? _trend;
  int? _selectedIndex;

  // Data pelengkap dashboard (best-effort — kegagalan tidak menggagalkan layar).
  List<AccountModel> _accounts = [];
  List<CategoryModel> _categories = [];
  // Transaksi terbaru (1 halaman, ringan) untuk section "Transaksi Terbaru".
  List<TransactionModel> _recentTx = [];
  // Semua transaksi (max 2000) untuk filter akun client-side — di-load LAZY
  // hanya saat dropdown filter akun dibuka pertama kali (fix lag: dashboard
  // tidak lagi men-download semua transaksi setiap kali dibuka).
  List<TransactionModel> _allTx = [];
  bool _allTxLoaded = false;
  bool _allTxLoading = false;

  // Rentang periode kustom (From/To) — dipakai saat `_period == 'custom'`.
  DateTime? _customStart;
  DateTime? _customEnd;

  // Filter akun (client-side, seperti v1). Kosong = semua akun.
  final Set<String> _selectedAccountIds = {};

  String? _selectedCategoryName;
  bool _amountsHidden = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void didUpdateWidget(DashboardScreen oldWidget) {
    super.didUpdateWidget(oldWidget);
    if (oldWidget.refreshToken != widget.refreshToken) _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _selectedIndex = null;
    });
    try {
      // Report utama (summary + trend) & data sekunder diambil PARALEL
      // untuk memotong waktu tunggu (fiks lag menu lambat).
      final results = await Future.wait<Object?>([
        _api.fetchSummary(
          period: _period,
          start: _customStartIso,
          end: _customEndIso,
        ),
        _api.fetchTrend(
          period: _period,
          start: _customStartIso,
          end: _customEndIso,
        ),
        _loadSupplements(),
      ]);
      if (!mounted) return;
      setState(() {
        _summary = results[0] as ReportSummary;
        _trend = results[1] as ReportTrend;
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

  /// Kirim start/end hanya saat periode kustom.
  String? get _customStartIso =>
      _period == 'custom' ? _fmtDate(_customStart) : null;
  String? get _customEndIso => _period == 'custom' ? _fmtDate(_customEnd) : null;

  static String _fmtDate(DateTime? d) {
    if (d == null) return '';
    return '${d.year.toString().padLeft(4, '0')}-'
        '${d.month.toString().padLeft(2, '0')}-'
        '${d.day.toString().padLeft(2, '0')}';
  }

  /// Data sekunder (akun + kategori + 1 halaman transaksi terbaru) diambil
  /// PARALEL dengan report utama. Kegagalan tidak memblokir layar (best-effort).
  /// Semua transaksi TIDAK di-fetch di sini (lazy — lihat `_ensureAllTxLoaded`).
  Future<void> _loadSupplements() async {
    try {
      final accounts = _api.fetchAccounts();
      final categories = _api.fetchCategories();
      final recent = _api.fetchTransactions(); // 1 halaman (20 item), ringan
      final futures = <Future<Object?>>[accounts, categories, recent];
      // Kalau filter akun sudah pernah dipakai, refresh cache-nya juga
      // (best-effort, paralel — tidak memperlambat layar).
      if (_allTxLoaded) {
        futures.add(_api.fetchAllTransactions());
      }
      final results = await Future.wait<Object?>(futures);
      if (!mounted) return;
      setState(() {
        _accounts = results[0] as List<AccountModel>;
        _categories = results[1] as List<CategoryModel>;
        _recentTx = (results[2] as TransactionListResult).items;
        if (_allTxLoaded) {
          _allTx = results[3] as List<TransactionModel>;
        }
      });
    } on ApiException {
      // Biarkan data lama; dashboard utama tetap tampil.
    }
  }

  /// Muat SEMUA transaksi (cursor loop, max 2000) secara lazy — pertama kali
  /// dipanggil saat dropdown filter akun dibuka. Hasil di-cache; refresh
  /// berikutnya terjadi via `_loadSupplements` saat `_allTxLoaded`.
  Future<void> _ensureAllTxLoaded() async {
    if (_allTxLoaded || _allTxLoading) return;
    _allTxLoading = true;
    try {
      final allTx = await _api.fetchAllTransactions();
      if (!mounted) return;
      setState(() {
        _allTx = allTx;
        _allTxLoaded = true;
        _allTxLoading = false;
      });
    } on ApiException {
      if (!mounted) return;
      setState(() => _allTxLoading = false); // izinkan retry
    }
  }

  void _changePeriod(String period) {
    if (period == _period) return;
    setState(() => _period = period);
    _load();
  }

  void _applyCustomRange(DateTime start, DateTime end) {
    setState(() {
      _customStart = start;
      _customEnd = end;
      _period = 'custom';
    });
    _load();
  }

  /// null = semua akun; non-null = subset yang difilter.
  Set<String>? get _activeAccountFilter =>
      _selectedAccountIds.isEmpty ? null : _selectedAccountIds;

  void _toggleAccount(String id) {
    setState(() {
      if (_selectedAccountIds.isEmpty) {
        // Dari "semua" → pilih semua kecuali yang ditoggle (deselect satu).
        _selectedAccountIds
          ..clear()
          ..addAll(_accounts.map((a) => a.id).where((x) => x != id));
      } else if (_selectedAccountIds.contains(id)) {
        _selectedAccountIds.remove(id);
      } else {
        _selectedAccountIds.add(id);
      }
    });
  }

  void _selectAllAccounts() {
    setState(() => _selectedAccountIds.clear());
  }

  void _openTransactionList(String? type) {
    final transactions = _filteredTxs
        .where((tx) => type == null || tx.type == type)
        .toList();
    Navigator.of(context).push(
      MaterialPageRoute<void>(
        builder: (_) => TransactionListScreen(
          title: type == 'income'
              ? 'Income'
              : type == 'expense'
                  ? 'Expense'
                  : 'Net transactions',
          transactions: transactions,
          categoryNames: {for (final c in _categories) c.id: c.name},
          accountLabels: {for (final a in _accounts) a.id: a.label},
          onTransactionTap: _editTransaction,
        ),
      ),
    );
  }

  double get _totalBalance =>
      _accounts.fold(0, (sum, a) => sum + a.currentBalance);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Dashboard')),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _buildBody(context),
      ),
      floatingActionButton: _DashboardFABs(
        onScan: _openReceiptScanner,
        onAdd: _addTransaction,
      ),
    );
  }

  void _openReceiptScanner() {
    Navigator.of(context).push(
      MaterialPageRoute<bool>(
        builder: (_) => ReceiptScreen(api: _api),
      ),
    ).then((changed) {
      if (changed == true) _load();
    });
  }

  void _addTransaction() {
    Navigator.of(context).push(
      MaterialPageRoute<bool>(
        builder: (_) => TransactionFormScreen(api: _api),
      ),
    ).then((changed) {
      if (changed == true) _load();
    });
  }

  void _editTransaction(TransactionModel tx) {
    Navigator.of(context).push(
      MaterialPageRoute<bool>(
        builder: (_) => TransactionFormScreen(api: _api, transaction: tx),
      ),
    ).then((changed) {
      if (changed == true) _load();
    });
  }

  Widget _buildBody(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return _ErrorView(message: _error!, onRetry: _load);
    }
    final summary = _summary;
    final trend = _trend;
    if (summary == null || trend == null) {
      return const Center(child: Text('Data tidak tersedia'));
    }

    final categoryNames = {
      for (final c in _categories) c.id: c.name,
    };

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _PeriodSelector(
          period: _period,
          customStart: _customStart,
          customEnd: _customEnd,
          onChanged: _changePeriod,
          onCustomRange: _applyCustomRange,
        ),
        const SizedBox(height: 8),
        _AccountFilterDropdown(
          accounts: _accounts,
          selectedAccountIds: _selectedAccountIds,
          onToggle: _toggleAccount,
          onSelectAll: _selectAllAccounts,
          onOpen: _ensureAllTxLoaded,
        ),
        const SizedBox(height: 12),
        _BalanceCard(
          totalBalance: _totalBalance,
          amountsHidden: _amountsHidden,
          onToggleHidden: () =>
              setState(() => _amountsHidden = !_amountsHidden),
        ),
        const SizedBox(height: 12),
        _SummaryCards(
          summary: summary,
          amountsHidden: _amountsHidden,
          filteredIncome: _filteredIncome,
          filteredExpense: _filteredExpense,
          filteredNet: _filteredIncome - _filteredExpense,
          accountFilterActive: _activeAccountFilter != null,
          onIncomeTap: () => _openTransactionList('income'),
          onExpenseTap: () => _openTransactionList('expense'),
          onNetTap: () => _openTransactionList(null),
        ),
        const SizedBox(height: 12),
        _TrendCard(
          trend: trend,
          selectedIndex: _selectedIndex,
          onPointTap: (i) => setState(() => _selectedIndex = i),
          filteredPoints: _filteredTrendPoints,
          accountFilterActive: _activeAccountFilter != null,
        ),
        const SizedBox(height: 12),
        _CategoryBreakdownCard(
          summary: summary,
          recentTransactions: _recentTx,
          categoryNames: categoryNames,
          selectedCategoryName: _selectedCategoryName,
          onCategorySelect: (name) => setState(() {
            _selectedCategoryName =
                _selectedCategoryName == name ? null : name;
          }),
          onTransactionTap: _editTransaction,
          donutIncome: _filteredIncome,
          donutExpense: _filteredExpense,
          accountFilterActive: _activeAccountFilter != null,
        ),
      ],
    );
  }

  // ── Filter akun client-side (setara v1) ─────────────────────────────────

  List<TransactionModel> get _accountFilteredTxs {
    final active = _activeAccountFilter;
    if (active == null) return _allTx;
    return _allTx.where((tx) => active.contains(tx.accountId)).toList();
  }

  /// Period boundaries untuk filter client-side (date-only).
  DateTime get _periodStart {
    final now = DateTime.now();
    switch (_period) {
      case 'today':
        return DateTime(now.year, now.month, now.day);
      case 'week':
        final monday = now.subtract(Duration(days: now.weekday - 1));
        return DateTime(monday.year, monday.month, monday.day);
      case 'custom':
        return _customStart == null ? DateTime(now.year, now.month, 1) : _customStart!;
      default: // month
        return DateTime(now.year, now.month, 1);
    }
  }

  DateTime get _periodEnd {
    final now = DateTime.now();
    switch (_period) {
      case 'today':
        return DateTime(now.year, now.month, now.day);
      case 'week':
      case 'month':
        return DateTime(now.year, now.month, now.day);
      case 'custom':
        return _customEnd == null ? DateTime(now.year, now.month, now.day) : _customEnd!;
      default:
        return DateTime(now.year, now.month, now.day);
    }
  }

  bool _inPeriod(DateTime d) {
    final start = _periodStart;
    final end = _periodEnd;
    final day = DateTime(d.year, d.month, d.day);
    return !day.isBefore(start) && !day.isAfter(end);
  }

  /// Transaksi periode + akun terpilih (client-side).
  List<TransactionModel> get _filteredTxs => _accountFilteredTxs
      .where((tx) => _inPeriod(tx.transactionDate))
      .toList();

  double get _filteredIncome => _filteredTxs
      .where((tx) => tx.type == 'income')
      .fold(0, (s, tx) => s + tx.totalAmount);

  double get _filteredExpense => _filteredTxs
      .where((tx) => tx.type == 'expense')
      .fold(0, (s, tx) => s + tx.totalAmount);

  /// Tren harian client-side saat filter akun aktif: bucket per tanggal.
  List<TrendPoint> get _filteredTrendPoints {
    if (_activeAccountFilter == null) return _trend?.points ?? const [];
    final buckets = <DateTime, List<double>>{};
    for (final tx in _filteredTxs) {
      final day = DateTime(
        tx.transactionDate.year,
        tx.transactionDate.month,
        tx.transactionDate.day,
      );
      final pair = buckets.putIfAbsent(day, () => [0, 0]);
      if (tx.type == 'expense') {
        pair[1] += tx.totalAmount;
      } else {
        pair[0] += tx.totalAmount;
      }
    }
    final keys = buckets.keys.toList()..sort();
    return [
      for (final k in keys)
        TrendPoint(
          date: k,
          income: buckets[k]![0],
          expense: buckets[k]![1],
        ),
    ];
  }
}

/// FAB: ikon scan (kecil) + ikon tambah transaksi — keduanya icon-only,
/// tanpa teks "Scan Nota" (permintaan user). Ditumpuk vertikal.
class _DashboardFABs extends StatelessWidget {
  const _DashboardFABs({required this.onScan, required this.onAdd});

  final VoidCallback onScan;
  final VoidCallback onAdd;

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        FloatingActionButton(
          heroTag: 'scan',
          tooltip: 'Scan Nota',
          onPressed: onScan,
          shape: const CircleBorder(),
          child: const Icon(Icons.document_scanner_outlined),
        ),
        const SizedBox(height: 12),
        FloatingActionButton(
          heroTag: 'add',
          tooltip: 'Tambah Transaksi',
          onPressed: onAdd,
          shape: const CircleBorder(),
          child: const Icon(Icons.add),
        ),
      ],
    );
  }
}

/// Pilihan periode: Hari Ini / Minggu Ini / Bulan Ini / Kustom (setara v1).
/// Kustom menampilkan baris From/To + tombol Apply.
class _PeriodSelector extends StatelessWidget {
  const _PeriodSelector({
    required this.period,
    required this.customStart,
    required this.customEnd,
    required this.onChanged,
    required this.onCustomRange,
  });

  final String period;
  final DateTime? customStart;
  final DateTime? customEnd;
  final ValueChanged<String> onChanged;
  final void Function(DateTime start, DateTime end) onCustomRange;

  static const _options = [
    (value: 'today', label: 'Today'),
    (value: 'week', label: 'This Week'),
    (value: 'month', label: 'This Month'),
    (value: 'custom', label: 'Custom'),
  ];

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Container(
          width: double.infinity,
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            color: scheme.surfaceContainerHighest,
            borderRadius: BorderRadius.circular(8),
          ),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final opt in _options) ...[
                  if (opt != _options.first) const SizedBox(width: 4),
                  _PeriodChip(
                    label: opt.label,
                    selected: period == opt.value,
                    onTap: () => onChanged(opt.value),
                  ),
                ],
              ],
            ),
          ),
        ),
        if (period == 'custom') ...[
          const SizedBox(height: 8),
          _CustomRangeRow(
            start: customStart,
            end: customEnd,
            onApply: onCustomRange,
          ),
        ],
      ],
    );
  }
}

class _PeriodChip extends StatelessWidget {
  const _PeriodChip({
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
        constraints: const BoxConstraints(minWidth: 84),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: selected ? scheme.primaryContainer : Colors.transparent,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          label,
          style: Theme.of(context).textTheme.labelLarge?.copyWith(
                color: selected ? scheme.primary : scheme.onSurfaceVariant,
                fontWeight: selected ? FontWeight.w700 : FontWeight.w500,
              ),
          maxLines: 1,
        ),
      ),
    );
  }
}

/// Baris rentang kustom From/To + tombol Apply (setara v1 CustomRangeRow).
/// Pilihan rentang kustom (v1 parity): chip From/To menyimpan tanggal
/// pending di state lokal, hanya tombol **Apply** yang commit (memanggil
/// `onApply` → ganti periode + reload). Memilih tanggal tidak memicu reload.
class _CustomRangeRow extends StatefulWidget {
  const _CustomRangeRow({
    required this.start,
    required this.end,
    required this.onApply,
  });

  final DateTime? start;
  final DateTime? end;
  final void Function(DateTime start, DateTime end) onApply;

  @override
  State<_CustomRangeRow> createState() => _CustomRangeRowState();
}

class _CustomRangeRowState extends State<_CustomRangeRow> {
  late DateTime? _pendingStart = widget.start;
  late DateTime? _pendingEnd = widget.end;

  @override
  void didUpdateWidget(_CustomRangeRow oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Sinkronkan chip dengan nilai ter-commit dari parent (mis. setelah Apply
    // atau setelah swap start/end) — tanpa mengganggu pending state saat user
    // baru memilih tanggal di picker.
    if (oldWidget.start != widget.start || oldWidget.end != widget.end) {
      _pendingStart = widget.start;
      _pendingEnd = widget.end;
    }
  }

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(8),
      decoration: BoxDecoration(
        color: scheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Expanded(
            child: _DateChip(
              label: _pendingStart == null ? 'From' : _fmt(_pendingStart!),
              onTap: () => _pickDate(context, isFrom: true),
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: _DateChip(
              label: _pendingEnd == null ? 'To' : _fmt(_pendingEnd!),
              onTap: () => _pickDate(context, isFrom: false),
            ),
          ),
          const SizedBox(width: 8),
          InkWell(
            onTap: (_pendingStart != null && _pendingEnd != null)
                ? () {
                    var s = _pendingStart!;
                    var e = _pendingEnd!;
                    if (s.isAfter(e)) {
                      final tmp = s;
                      s = e;
                      e = tmp;
                    }
                    widget.onApply(s, e);
                  }
                : null,
            borderRadius: BorderRadius.circular(8),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
              decoration: BoxDecoration(
                color: scheme.primaryContainer,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                'Apply',
                style: Theme.of(context).textTheme.labelLarge?.copyWith(
                      color: scheme.primary,
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _fmt(DateTime d) =>
      '${d.day.toString().padLeft(2, '0')}/'
      '${d.month.toString().padLeft(2, '0')}/'
      '${d.year}';

  Future<void> _pickDate(BuildContext context, {required bool isFrom}) async {
    final now = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: isFrom
          ? (_pendingStart ?? now.subtract(const Duration(days: 30)))
          : (_pendingEnd ?? now),
      firstDate: DateTime(now.year - 5),
      lastDate: now.add(const Duration(days: 365)),
    );
    if (picked != null && mounted) {
      setState(() {
        if (isFrom) {
          _pendingStart = picked;
        } else {
          _pendingEnd = picked;
        }
      });
    }
  }
}

class _DateChip extends StatelessWidget {
  const _DateChip({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
        alignment: Alignment.center,
        decoration: BoxDecoration(
          color: scheme.surface,
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          label,
          style: Theme.of(context).textTheme.labelLarge,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
      ),
    );
  }
}

/// Dropdown filter akun dengan checkbox (client-side, setara v1).
class _AccountFilterDropdown extends StatelessWidget {
  const _AccountFilterDropdown({
    required this.accounts,
    required this.selectedAccountIds,
    required this.onToggle,
    required this.onSelectAll,
    required this.onOpen,
  });

  final List<AccountModel> accounts;
  final Set<String> selectedAccountIds;
  final ValueChanged<String> onToggle;
  final VoidCallback onSelectAll;
  /// Dipanggil saat dropdown dibuka — trigger lazy-load semua transaksi.
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    final allSelected =
        selectedAccountIds.isEmpty || selectedAccountIds.length >= accounts.length;

    return MenuAnchor(
      builder: (context, controller, child) {
        return Material(
          color: Colors.transparent,
          child: InkWell(
            onTap: () {
              onOpen();
              if (controller.isOpen) {
                controller.close();
              } else {
                controller.open();
              }
            },
            borderRadius: BorderRadius.circular(8),
            child: Container(
              width: double.infinity,
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
              decoration: BoxDecoration(
                color: scheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(8),
              ),
              child: Row(
                children: [
                  Icon(Icons.account_balance_wallet_outlined,
                      size: 18, color: scheme.onSurfaceVariant),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      allSelected
                          ? 'Semua akun (${accounts.length})'
                          : '${selectedAccountIds.length} akun terpilih',
                      style: Theme.of(context).textTheme.bodyMedium,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                  Icon(Icons.arrow_drop_down, color: scheme.onSurfaceVariant),
                ],
              ),
            ),
          ),
        );
      },
      menuChildren: [
        _AccountMenuItem(
          label: 'Select all',
          checked: allSelected,
          bold: true,
          onTap: onSelectAll,
        ),
        const Divider(height: 1),
        for (final account in accounts)
          _AccountMenuItem(
            label: account.label,
            checked: selectedAccountIds.isEmpty || selectedAccountIds.contains(account.id),
            onTap: () => onToggle(account.id),
          ),
      ],
    );
  }
}

class _AccountMenuItem extends StatelessWidget {
  const _AccountMenuItem({
    required this.label,
    required this.checked,
    required this.onTap,
    this.bold = false,
  });

  final String label;
  final bool checked;
  final VoidCallback onTap;
  final bool bold;

  @override
  Widget build(BuildContext context) {
    return MenuItemButton(
      leadingIcon: SizedBox(
        width: 24,
        child: Icon(
          checked ? Icons.check_box : Icons.check_box_outline_blank,
          color: checked
              ? Theme.of(context).colorScheme.primary
              : Theme.of(context).colorScheme.onSurfaceVariant,
        ),
      ),
      onPressed: onTap,
      child: Text(
        label,
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              fontWeight: bold ? FontWeight.w700 : FontWeight.w400,
            ),
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
      ),
    );
  }
}

/// Ringkasan Income / Expense / Net (kiri→kanan, setara v1).
/// Saat filter akun aktif, nilai dihitung client-side dari transaksi terfilter.
class _SummaryCards extends StatelessWidget {
  const _SummaryCards({
    required this.summary,
    required this.amountsHidden,
    required this.filteredIncome,
    required this.filteredExpense,
    required this.filteredNet,
    required this.accountFilterActive,
    required this.onIncomeTap,
    required this.onExpenseTap,
    required this.onNetTap,
  });

  final ReportSummary summary;
  final bool amountsHidden;
  final double filteredIncome;
  final double filteredExpense;
  final double filteredNet;
  final bool accountFilterActive;
  final VoidCallback onIncomeTap;
  final VoidCallback onExpenseTap;
  final VoidCallback onNetTap;

  @override
  Widget build(BuildContext context) {
    final income = accountFilterActive ? filteredIncome : summary.totalIncome;
    final expense = accountFilterActive ? filteredExpense : summary.totalExpense;
    final net = accountFilterActive ? filteredNet : summary.net;
    return Row(
      children: [
        Expanded(
          child: _SummaryCard(
            label: 'Income',
            value: formatRupiah(income),
            color: AppColors.income(context),
            icon: Icons.arrow_upward,
            hidden: amountsHidden,
            onTap: onIncomeTap,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _SummaryCard(
            label: 'Expense',
            value: formatRupiah(expense),
            color: AppColors.expense(context),
            icon: Icons.arrow_downward,
            hidden: amountsHidden,
            onTap: onExpenseTap,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _SummaryCard(
            label: 'Net',
            value: formatRupiah(net),
            color: AppColors.net(context),
            icon: Icons.balance,
            hidden: amountsHidden,
            onTap: onNetTap,
          ),
        ),
      ],
    );
  }
}

class _SummaryCard extends StatelessWidget {
  const _SummaryCard({
    required this.label,
    required this.value,
    required this.color,
    required this.icon,
    required this.hidden,
    required this.onTap,
  });

  final String label;
  final String value;
  final Color color;
  final IconData icon;
  final bool hidden;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Container(
                  width: 28,
                  height: 28,
                  decoration: BoxDecoration(
                    color: Theme.of(context).colorScheme.primaryContainer,
                    shape: BoxShape.circle,
                  ),
                  child: Icon(icon, size: 16, color: color),
                ),
                const Spacer(),
                Text(
                  label,
                  style: Theme.of(context).textTheme.labelMedium,
                ),
              ],
            ),
            const SizedBox(height: 6),
            FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                hidden ? 'Rp ••••••' : value,
                style: TextStyle(
                  fontSize: 17,
                  fontWeight: FontWeight.w700,
                  color: color,
                ),
              ),
            ),
            ],
          ),
        ),
      ),
    );
  }
}

/// Total saldo semua akun (DESIGN.md §8.1) + toggle privasi (ikon mata).
class _BalanceCard extends StatelessWidget {
  const _BalanceCard({
    required this.totalBalance,
    required this.amountsHidden,
    required this.onToggleHidden,
  });

  final double totalBalance;
  final bool amountsHidden;
  final VoidCallback onToggleHidden;

  static const _masked = 'Rp ••••••';

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Text(
                  'Total Balance',
                  style: Theme.of(context).textTheme.labelMedium?.copyWith(
                        color: Theme.of(context).colorScheme.onSurfaceVariant,
                      ),
                ),
                const Spacer(),
                IconButton(
                  tooltip: amountsHidden ? 'Tampilkan saldo' : 'Sembunyikan saldo',
                  onPressed: onToggleHidden,
                  icon: Icon(
                    amountsHidden ? Icons.visibility_off : Icons.visibility,
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
                ),
              ],
            ),
            Text(
              amountsHidden ? _masked : formatRupiah(totalBalance),
              style: Theme.of(context).textTheme.headlineMedium?.copyWith(
                    fontWeight: FontWeight.w800,
                  ),
              maxLines: 1,
              overflow: TextOverflow.visible,
            ),
          ],
        ),
      ),
    );
  }
}

class _TrendCard extends StatelessWidget {
  const _TrendCard({
    required this.trend,
    required this.selectedIndex,
    required this.onPointTap,
    required this.filteredPoints,
    required this.accountFilterActive,
  });

  final ReportTrend trend;
  final int? selectedIndex;
  final ValueChanged<int> onPointTap;
  final List<TrendPoint> filteredPoints;
  final bool accountFilterActive;

  @override
  Widget build(BuildContext context) {
    final points =
        accountFilterActive ? filteredPoints : trend.points;
    return Card(
      margin: EdgeInsets.zero,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Cash Flow',
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 2),
            Text(
              'Tren harian pemasukan vs pengeluaran',
              style: Theme.of(context).textTheme.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.onSurfaceVariant,
                  ),
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                _LegendDot(color: AppColors.income(context), label: 'Income'),
                const SizedBox(width: 12),
                _LegendDot(color: AppColors.expense(context), label: 'Expense'),
              ],
            ),
            const SizedBox(height: 12),
            TrendChart(
              points: points,
              selectedIndex: selectedIndex,
              onPointTap: onPointTap,
            ),
            const SizedBox(height: 12),
            _DetailPanel(
              points: points,
              selectedIndex: selectedIndex,
            ),
          ],
        ),
      ),
    );
  }
}

class _LegendDot extends StatelessWidget {
  const _LegendDot({required this.color, required this.label});

  final Color color;
  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Container(
          width: 10,
          height: 10,
          decoration: BoxDecoration(color: color, shape: BoxShape.circle),
        ),
        const SizedBox(width: 6),
        Text(label, style: Theme.of(context).textTheme.bodySmall),
      ],
    );
  }
}

/// Panel detail titik yang ditekan (tap singkat). Kosong = hint.
class _DetailPanel extends StatelessWidget {
  const _DetailPanel({required this.points, required this.selectedIndex});

  final List<TrendPoint> points;
  final int? selectedIndex;

  @override
  Widget build(BuildContext context) {
    if (selectedIndex == null ||
        selectedIndex! < 0 ||
        selectedIndex! >= points.length) {
      return Container(
        width: double.infinity,
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.black.withValues(alpha: 0.04),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Text(
          'Ketuk titik pada grafik untuk melihat detail hari itu',
          style: Theme.of(context).textTheme.bodySmall,
        ),
      );
    }

    final p = points[selectedIndex!];
    final net = p.net;
    final rows = <(String, String, Color)>[
      ('Income', formatRupiah(p.income), AppColors.income(context)),
      ('Expense', formatRupiah(p.expense), AppColors.expense(context)),
      (
        'Net',
        formatRupiahSigned(net),
        net >= 0 ? AppColors.income(context) : AppColors.expense(context),
      ),
    ];

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.primaryContainer.withValues(alpha: 0.35),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            formatDateDetail(p.date),
            style: Theme.of(context)
                .textTheme
                .titleSmall
                ?.copyWith(fontWeight: FontWeight.w700),
          ),
          const SizedBox(height: 8),
          for (final (label, value, color) in rows)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 2),
              child: Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  Text(label, style: Theme.of(context).textTheme.bodyMedium),
                  Text(
                    value,
                    style: TextStyle(
                      fontWeight: FontWeight.w600,
                      color: color,
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

/// Breakdown kategori: donut income vs expense + bar per kategori +
/// transaksi terbaru (terfilter saat kategori dipilih) — setara v1 §8.4.
class _CategoryBreakdownCard extends StatelessWidget {
  const _CategoryBreakdownCard({
    required this.summary,
    required this.recentTransactions,
    required this.categoryNames,
    required this.selectedCategoryName,
    required this.onCategorySelect,
    required this.onTransactionTap,
    required this.donutIncome,
    required this.donutExpense,
    required this.accountFilterActive,
  });

  final ReportSummary summary;
  final List<TransactionModel> recentTransactions;
  final Map<String, String> categoryNames;
  final String? selectedCategoryName;
  final ValueChanged<String> onCategorySelect;
  final ValueChanged<TransactionModel> onTransactionTap;
  final double donutIncome;
  final double donutExpense;
  final bool accountFilterActive;

  @override
  Widget build(BuildContext context) {
    final expenseCats =
        summary.categories.where((c) => c.type == 'expense').toList();
    final incomeCats =
        summary.categories.where((c) => c.type == 'income').toList();

    // Filter transaksi terbaru berdasarkan kategori terpilih (client-side).
    final nameOf = categoryNames;
    final filtered = selectedCategoryName == null
        ? recentTransactions
        : recentTransactions
            .where((tx) => nameOf[tx.categoryId] == selectedCategoryName)
            .toList();

    return Card(
      margin: EdgeInsets.zero,
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: BorderSide(color: Theme.of(context).colorScheme.outlineVariant),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'By Category',
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 12),
            _IncomeExpenseDonut(
              income: accountFilterActive ? donutIncome : summary.totalIncome,
              expense: accountFilterActive ? donutExpense : summary.totalExpense,
              net: (accountFilterActive ? donutIncome : summary.totalIncome) -
                  (accountFilterActive ? donutExpense : summary.totalExpense),
            ),
            const SizedBox(height: 12),

            if (expenseCats.isNotEmpty) ...[
              Text(
                'Expense',
                style: Theme.of(context)
                    .textTheme
                    .labelLarge
                    ?.copyWith(color: AppColors.expense(context)),
              ),
              const SizedBox(height: 4),
              ..._categoryRows(
                context,
                expenseCats,
                AppColors.expense(context),
              ),
            ],
            if (incomeCats.isNotEmpty) ...[
              const SizedBox(height: 8),
              Text(
                'Income',
                style: Theme.of(context)
                    .textTheme
                    .labelLarge
                    ?.copyWith(color: AppColors.income(context)),
              ),
              const SizedBox(height: 4),
              ..._categoryRows(
                context,
                incomeCats,
                AppColors.income(context),
              ),
            ],

            const SizedBox(height: 12),
            Divider(color: Theme.of(context).colorScheme.outlineVariant),
            const SizedBox(height: 12),

            Text(
              selectedCategoryName == null
                  ? 'Recent transactions'
                  : 'Transactions · $selectedCategoryName',
              style: Theme.of(context)
                  .textTheme
                  .titleMedium
                  ?.copyWith(fontWeight: FontWeight.w700),
            ),
            const SizedBox(height: 4),
            if (filtered.isEmpty)
              Padding(
                padding: const EdgeInsets.symmetric(vertical: 24),
                child: Center(
                  child: Text(
                    'No transactions in this period',
                    style: Theme.of(context).textTheme.bodySmall,
                  ),
                ),
              )
            else
              for (final tx in filtered.take(5))
                _RecentTransactionRow(
                  tx: tx,
                  categoryName: nameOf[tx.categoryId] ?? '—',
                  onTap: () => onTransactionTap(tx),
                ),
          ],
        ),
      ),
    );
  }

  List<Widget> _categoryRows(
    BuildContext context,
    List<CategoryTotal> cats,
    Color color,
  ) {
    final max = cats.map((c) => c.total).fold<double>(0, (a, b) => a > b ? a : b);
    return [
      for (final cat in cats)
        _CategoryRow(
          name: cat.name,
          total: cat.total,
          color: color,
          max: max,
          selected: selectedCategoryName == cat.name,
          onClick: () => onCategorySelect(cat.name),
        ),
    ];
  }
}

/// Donut income vs expense (dua segmen) dengan nilai net di tengah.
class _IncomeExpenseDonut extends StatelessWidget {
  const _IncomeExpenseDonut({
    required this.income,
    required this.expense,
    required this.net,
  });

  final double income;
  final double expense;
  final double net;

  @override
  Widget build(BuildContext context) {
    final total = income + expense;
    if (total <= 0) {
      return Padding(
        padding: const EdgeInsets.symmetric(vertical: 24),
        child: Center(
          child: Text(
            'No transactions in this period',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
      );
    }

    return Column(
      children: [
        SizedBox(
          height: 170,
          child: Stack(
            alignment: Alignment.center,
            children: [
              PieChart(
                PieChartData(
                  sectionsSpace: 0,
                  centerSpaceRadius: 42,
                  startDegreeOffset: -90,
                  sections: [
                    PieChartSectionData(
                      value: income,
                      color: AppColors.income(context),
                      radius: 36,
                      showTitle: false,
                    ),
                    PieChartSectionData(
                      value: expense,
                      color: AppColors.expense(context),
                      radius: 36,
                      showTitle: false,
                    ),
                  ],
                ),
              ),
              Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    formatRupiah(net),
                    style: Theme.of(context)
                        .textTheme
                        .titleMedium
                        ?.copyWith(fontWeight: FontWeight.w800),
                  ),
                  Text(
                    'Net',
                    style: Theme.of(context).textTheme.labelSmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                  ),
                ],
              ),
            ],
          ),
        ),
        const SizedBox(height: 8),
        Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            _LegendDot(color: AppColors.income(context), label: 'Income'),
            const SizedBox(width: 16),
            _LegendDot(color: AppColors.expense(context), label: 'Expense'),
          ],
        ),
      ],
    );
  }
}

/// Baris kategori — bar simetris (nama lebar tetap, track bar mengisi sisa).
class _CategoryRow extends StatelessWidget {
  const _CategoryRow({
    required this.name,
    required this.total,
    required this.color,
    required this.max,
    required this.selected,
    required this.onClick,
  });

  final String name;
  final double total;
  final Color color;
  final double max;
  final bool selected;
  final VoidCallback onClick;

  @override
  Widget build(BuildContext context) {
    final fraction = max <= 0 ? 0.0 : (total / max).clamp(0.0, 1.0);
    return InkWell(
      onTap: onClick,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 5),
        child: Row(
          children: [
            SizedBox(
              width: 120,
              child: Text(
                name,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                      fontWeight:
                          selected ? FontWeight.w700 : FontWeight.w500,
                    ),
              ),
            ),
            Expanded(
              child: Container(
                height: 8,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: selected ? 0.9 : 0.25),
                  borderRadius: BorderRadius.circular(4),
                ),
                alignment: Alignment.centerLeft,
                child: Container(
                  width: (fraction * 100).clamp(0.0, 100.0),
                  height: 8,
                  decoration: BoxDecoration(
                    color: color,
                    borderRadius: BorderRadius.circular(4),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            SizedBox(
              width: 90,
              child: Text(
                formatRupiah(total),
                textAlign: TextAlign.end,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Baris transaksi terbaru (tap → edit, setara v1).
class _RecentTransactionRow extends StatelessWidget {
  const _RecentTransactionRow({
    required this.tx,
    required this.categoryName,
    required this.onTap,
  });

  final TransactionModel tx;
  final String categoryName;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final isIncome = tx.type == 'income';
    final color = isIncome
        ? AppColors.income(context)
        : AppColors.expense(context);
    final subtitle = tx.merchant?.isNotEmpty == true
        ? tx.merchant!
        : tx.note?.isNotEmpty == true
            ? tx.note!
            : 'Transaksi manual';

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(8),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 8),
        child: Row(
          children: [
            CircleAvatar(
              radius: 16,
              backgroundColor: color.withValues(alpha: 0.15),
              child: Icon(
                isIncome ? Icons.arrow_upward : Icons.arrow_downward,
                size: 16,
                color: color,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    categoryName,
                    style: Theme.of(context)
                        .textTheme
                        .bodyMedium
                        ?.copyWith(fontWeight: FontWeight.w600),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                  Text(
                    subtitle,
                    style: Theme.of(context).textTheme.bodySmall?.copyWith(
                          color: Theme.of(context).colorScheme.onSurfaceVariant,
                        ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Text(
              '${isIncome ? '+' : '-'}${formatRupiah(tx.totalAmount)}',
              style: TextStyle(
                fontWeight: FontWeight.w600,
                color: color,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.cloud_off, size: 48),
            const SizedBox(height: 12),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: onRetry,
              icon: const Icon(Icons.refresh),
              label: const Text('Coba lagi'),
            ),
          ],
        ),
      ),
    );
  }
}
