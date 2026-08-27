/// Dashboard (Fase 4): ringkasan bulan berjalan + line chart trend
/// (income vs expense) + panel detail pada TAP SINGKAT titik chart.
///
/// Data dari backend REST (`GET /api/reports/summary` & `/trend`) —
/// Flutter = thin client, semua agregasi di SQL backend (ARCHITECTURE §3.1).
library;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../models/report_models.dart';
import '../widgets/trend_chart.dart';

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
  }

  void _changePeriod(String period) {
    if (period == _period) return;
    setState(() => _period = period);
    _load();
  }

  void _logout() async {
    await widget.supabase.auth.signOut();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('My Money!'),
        actions: [
          IconButton(
            tooltip: 'Keluar',
            icon: const Icon(Icons.logout),
            onPressed: _logout,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _load,
        child: _buildBody(context),
      ),
    );
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

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _PeriodSelector(
          period: _period,
          onChanged: _changePeriod,
        ),
        const SizedBox(height: 12),
        _SummaryCards(summary: summary),
        const SizedBox(height: 16),
        _TrendCard(
          trend: trend,
          selectedIndex: _selectedIndex,
          onPointTap: (i) => setState(() => _selectedIndex = i),
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

class _SummaryCards extends StatelessWidget {
  const _SummaryCards({required this.summary});

  final ReportSummary summary;

  @override
  Widget build(BuildContext context) {
    final net = summary.net;
    return Row(
      children: [
        Expanded(
          child: _SummaryCard(
            label: 'Net',
            value: formatRupiah(net),
            color: net >= 0 ? const Color(0xFF2E7D32) : const Color(0xFFC62828),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _SummaryCard(
            label: 'Pemasukan',
            value: formatRupiah(summary.totalIncome),
            color: const Color(0xFF2E7D32),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          child: _SummaryCard(
            label: 'Pengeluaran',
            value: formatRupiah(summary.totalExpense),
            color: const Color(0xFFC62828),
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
  });

  final String label;
  final String value;
  final Color color;

  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.zero,
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 14),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              label,
              style: Theme.of(context).textTheme.labelSmall,
            ),
            const SizedBox(height: 4),
            FittedBox(
              fit: BoxFit.scaleDown,
              child: Text(
                value,
                style: TextStyle(
                  fontSize: 16,
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
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: const [
                _LegendDot(color: Color(0xFF2E7D32), label: 'Pemasukan'),
                SizedBox(width: 12),
                _LegendDot(color: Color(0xFFC62828), label: 'Pengeluaran'),
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
      ('Pemasukan', formatRupiah(p.income), const Color(0xFF2E7D32)),
      ('Pengeluaran', formatRupiah(p.expense), const Color(0xFFC62828)),
      (
        'Net',
        formatRupiahSigned(net),
        net >= 0 ? const Color(0xFF2E7D32) : const Color(0xFFC62828),
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
