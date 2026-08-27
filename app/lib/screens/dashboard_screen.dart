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
import 'transaction_form_screen.dart';

class DashboardScreen extends ConsumerStatefulWidget {
  const DashboardScreen({super.key, required this.supabase});

  final SupabaseClient supabase;

  @override
  ConsumerState<DashboardScreen> createState() => _DashboardScreenState();
}

class _DashboardScreenState extends ConsumerState<DashboardScreen> {
  late final ApiClient _api = ApiClient.instance(widget.supabase);

  String _period = 'month'; // 'week' | 'month'
  bool _loading = true;
  String? _error;

  ReportSummary? _summary;
  ReportTrend? _trend;
  int? _selectedIndex;

  // Data pelengkap dashboard (best-effort — kegagalan tidak menggagalkan layar).
  List<AccountModel> _accounts = [];
  List<CategoryModel> _categories = [];
  List<TransactionModel> _recentTx = [];

  String? _selectedCategoryName;
  bool _amountsHidden = false;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
      _selectedIndex = null;
    });
    try {
      final summary = await _api.fetchSummary(period: _period);
      final trend = await _api.fetchTrend(period: _period);
      if (!mounted) return;
      setState(() {
        _summary = summary;
        _trend = trend;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
    await _loadSupplements();
  }

  Future<void> _loadSupplements() async {
    try {
      final accounts = await _api.fetchAccounts();
      final categories = await _api.fetchCategories();
      final recent = await _api.fetchTransactions();
      if (!mounted) return;
      setState(() {
        _accounts = accounts;
        _categories = categories;
        _recentTx = recent.items;
      });
    } on ApiException {
      // Biarkan data lama; dashboard utama tetap tampil.
    }
  }

  void _changePeriod(String period) {
    if (period == _period) return;
    setState(() => _period = period);
    _load();
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
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _openReceiptScanner,
        icon: const Icon(Icons.document_scanner_outlined),
        label: const Text('Scan Nota'),
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
          onChanged: _changePeriod,
        ),
        const SizedBox(height: 12),
        _BalanceCard(
          totalBalance: _totalBalance,
          amountsHidden: _amountsHidden,
          onToggleHidden: () =>
              setState(() => _amountsHidden = !_amountsHidden),
        ),
        const SizedBox(height: 12),
        _SummaryCards(summary: summary, amountsHidden: _amountsHidden),
        const SizedBox(height: 12),
        _TrendCard(
          trend: trend,
          selectedIndex: _selectedIndex,
          onPointTap: (i) => setState(() => _selectedIndex = i),
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
        ),
      ],
    );
  }
}

class _PeriodSelector extends StatelessWidget {
  const _PeriodSelector({required this.period, required this.onChanged});

  final String period;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return SegmentedButton<String>(
      segments: const [
        ButtonSegment(value: 'week', label: Text('7 hari')),
        ButtonSegment(value: 'month', label: Text('Bulan ini')),
      ],
      selected: {period},
      onSelectionChanged: (s) => onChanged(s.first),
    );
  }
}

/// Ringkasan Income / Expense / Net (kiri→kanan, setara v1).
class _SummaryCards extends StatelessWidget {
  const _SummaryCards({
    required this.summary,
    required this.amountsHidden,
  });

  final ReportSummary summary;
  final bool amountsHidden;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: _SummaryCard(
            label: 'Income',
            value: formatRupiah(summary.totalIncome),
            color: AppColors.income(context),
            icon: Icons.arrow_upward,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _SummaryCard(
            label: 'Expense',
            value: formatRupiah(summary.totalExpense),
            color: AppColors.expense(context),
            icon: Icons.arrow_downward,
          ),
        ),
        const SizedBox(width: 12),
        Expanded(
          child: _SummaryCard(
            label: 'Net',
            value: formatRupiah(summary.net),
            color: AppColors.net(context),
            icon: Icons.balance,
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
  });

  final String label;
  final String value;
  final Color color;
  final IconData icon;

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
                value,
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
  });

  final ReportTrend trend;
  final int? selectedIndex;
  final ValueChanged<int> onPointTap;

  @override
  Widget build(BuildContext context) {
    final points = trend.points;
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
  });

  final ReportSummary summary;
  final List<TransactionModel> recentTransactions;
  final Map<String, String> categoryNames;
  final String? selectedCategoryName;
  final ValueChanged<String> onCategorySelect;
  final ValueChanged<TransactionModel> onTransactionTap;

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
              income: summary.totalIncome,
              expense: summary.totalExpense,
              net: summary.net,
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
