/// Line chart trend (income vs expense) dengan interaksi TAP SINGKAT.
///
/// Aturan interaksi (permintaan user, Fase 4):
/// - Tap singkat pada titik → `onPointTap(index)` → panel detail langsung
///   menampilkan detail hari itu. TIDAK ada long-press.
/// - Long press / drag → DIABAIKAN sepenuhnya (tidak menampilkan apa pun).
///
/// Implementasi: `handleBuiltInTouches: false` mematikan tooltip bawaan
/// fl_chart (yang juga menyala saat long-press). Kita hanya merespons
/// `FlTapUpEvent`; event long-press tidak punya handler sama sekali.
library;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../core/app_colors.dart';
import '../core/format.dart';
import '../models/report_models.dart';

class TrendChart extends StatelessWidget {
  const TrendChart({
    super.key,
    required this.points,
    required this.selectedIndex,
    required this.onPointTap,
  });

  final List<TrendPoint> points;
  final int? selectedIndex;
  final ValueChanged<int> onPointTap;

  @override
  Widget build(BuildContext context) {
    if (points.isEmpty) {
      return const SizedBox(
        height: 220,
        child: Center(child: Text('Belum ada data pada periode ini')),
      );
    }

    final semuaNilai = <double>[
      for (final p in points) ...[p.income, p.expense],
    ];
    var minY = semuaNilai.reduce((a, b) => a < b ? a : b);
    var maxY = semuaNilai.reduce((a, b) => a > b ? a : b);
    if (minY == maxY) {
      minY -= 1;
      maxY += 1;
    }
    final pad = (maxY - minY) * 0.15;

    final scheme = Theme.of(context).colorScheme;
    final gridColor = scheme.outlineVariant.withValues(alpha: 0.4);

    return SizedBox(
      height: 240,
      child: LineChart(
        LineChartData(
          minX: 0,
          maxX: (points.length - 1).toDouble(),
          minY: minY - pad,
          maxY: maxY + pad,
          clipData: const FlClipData.all(),
          gridData: FlGridData(
            show: true,
            drawVerticalLine: false,
            horizontalInterval: _niceInterval(maxY - minY),
            getDrawingHorizontalLine: (value) => FlLine(
              color: gridColor,
              strokeWidth: 1,
            ),
          ),
          titlesData: FlTitlesData(
            topTitles: const AxisTitles(),
            rightTitles: const AxisTitles(),
            bottomTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 34,
                interval: _bottomInterval(points.length),
                getTitlesWidget: (value, meta) {
                  final i = value.round();
                  if (i < 0 || i >= points.length) {
                    return const SizedBox.shrink();
                  }
                  return Padding(
                    padding: const EdgeInsets.only(top: 6),
                    child: Text(
                      formatAxisLabel(points[i].date),
                      style: TextStyle(
                        fontSize: 9,
                        color: scheme.onSurfaceVariant,
                      ),
                      maxLines: 1,
                    ),
                  );
                },
              ),
            ),
            leftTitles: AxisTitles(
              sideTitles: SideTitles(
                showTitles: true,
                reservedSize: 58,
                interval: _niceInterval(maxY - minY),
                getTitlesWidget: (value, meta) {
                  if (value < minY || value > maxY) {
                    return const SizedBox.shrink();
                  }
                  return Padding(
                    padding: const EdgeInsets.only(right: 6),
                    child: Text(
                      _compact(value),
                      style: TextStyle(
                        fontSize: 9,
                        color: scheme.onSurfaceVariant,
                      ),
                      textAlign: TextAlign.right,
                      maxLines: 1,
                    ),
                  );
                },
              ),
            ),
          ),
          borderData: FlBorderData(
            show: true,
            border: Border(
              bottom: BorderSide(color: gridColor),
              left: BorderSide(color: gridColor),
            ),
          ),
          lineBarsData: [
            _bar(context, points, selectedIndex, income: true),
            _bar(context, points, selectedIndex, income: false),
          ],
          extraLinesData: selectedIndex == null
              ? const ExtraLinesData()
              : ExtraLinesData(
                  verticalLines: [
                    VerticalLine(
                      x: selectedIndex!.toDouble(),
                      color: gridColor,
                      strokeWidth: 1,
                      dashArray: const [4, 4],
                    ),
                  ],
                ),
          lineTouchData: LineTouchData(
            enabled: true,
            // Matikan tooltip bawaan (termasuk pemicu long-press).
            handleBuiltInTouches: false,
            touchCallback: (event, response) {
              // Hanya tap singkat. Long-press & drag tidak punya handler.
              if (event is! FlTapUpEvent) return;
              final spots = response?.lineBarSpots ?? const [];
              if (spots.isEmpty) return;
              final x = spots.first.x.round();
              if (x >= 0 && x < points.length) onPointTap(x);
            },
          ),
        ),
      ),
    );
  }

  static LineChartBarData _bar(
    BuildContext context,
    List<TrendPoint> points,
    int? selectedIndex, {
    required bool income,
  }) {
    final color = income
        ? AppColors.income(context)
        : AppColors.expense(context);
    final surface = Theme.of(context).colorScheme.surface;
    return LineChartBarData(
      spots: [
        for (var i = 0; i < points.length; i++)
          FlSpot(
            i.toDouble(),
            income ? points[i].income : points[i].expense,
          ),
      ],
      isCurved: false,
      color: color,
      barWidth: 2,
      dotData: FlDotData(
        show: true,
        getDotPainter: (spot, percent, barData, index) {
          final selected = index == selectedIndex;
          final dotColor = barData.color ?? color;
          return FlDotCirclePainter(
            radius: selected ? 5 : 2.5,
            color: selected ? dotColor : dotColor.withValues(alpha: 0.45),
            strokeWidth: selected ? 2 : 0,
            strokeColor: surface,
          );
        },
      ),
      belowBarData: BarAreaData(
        show: income,
        color: color.withValues(alpha: 0.08),
      ),
    );
  }

  /// Interval "cantik" untuk grid/sumbu: 1/2/5 × 10^n.
  static double _niceInterval(double range) {
    final double raw = range <= 0 ? 1.0 : range / 4;
    final exponent = _log10(raw.abs());
    final magnitude = _pow10(exponent);
    final base = raw / magnitude;
    double nice;
    if (base <= 1) {
      nice = 1;
    } else if (base <= 2) {
      nice = 2;
    } else if (base <= 5) {
      nice = 5;
    } else {
      nice = 10;
    }
    return nice * magnitude;
  }

  static double _bottomInterval(int n) {
    if (n <= 7) return 1;
    if (n <= 15) return 2;
    return (n / 6).ceilToDouble();
  }

  static int _log10(double value) {
    var exponent = 0;
    var current = value;
    while (current >= 10) {
      current /= 10;
      exponent++;
    }
    while (current < 1) {
      current *= 10;
      exponent--;
    }
    return exponent;
  }

  static double _pow10(int exponent) {
    var result = 1.0;
    if (exponent >= 0) {
      for (var i = 0; i < exponent; i++) {
        result *= 10;
      }
    } else {
      for (var i = 0; i > exponent; i--) {
        result /= 10;
      }
    }
    return result;
  }

  /// "Rp5rb", "Rp1,2jt", "Rp50jt" — label sumbu ringkas.
  static String _compact(double value) {
    final abs = value.abs();
    String s;
    if (abs >= 1000000000) {
      s = '${(value / 1000000000).toStringAsFixed(1)}M';
    } else if (abs >= 1000000) {
      s = '${(value / 1000000).toStringAsFixed(1)}jt';
    } else if (abs >= 1000) {
      s = '${(value / 1000).toStringAsFixed(0)}rb';
    } else {
      s = value.toStringAsFixed(0);
    }
    return s.replaceAll('.', ',');
  }
}
