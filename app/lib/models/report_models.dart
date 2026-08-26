/// Model data untuk endpoint report (GET /api/reports/summary & /trend).
///
/// Backend mengirim Decimal sebagai string JSON (mis. "40000.00") — parse
/// menjadi `double` untuk kemudahan render & perhitungan di client.
library;

class CategoryTotal {
  const CategoryTotal({
    required this.name,
    required this.type,
    required this.total,
  });

  final String name;
  final String type; // 'income' | 'expense'
  final double total;

  factory CategoryTotal.fromJson(Map<String, dynamic> json) => CategoryTotal(
        name: json['name'] as String,
        type: json['type'] as String,
        total: _toDouble(json['total']),
      );
}

class ReportSummary {
  const ReportSummary({
    required this.startDate,
    required this.endDate,
    required this.totalIncome,
    required this.totalExpense,
    required this.net,
    required this.categories,
  });

  final DateTime startDate;
  final DateTime endDate;
  final double totalIncome;
  final double totalExpense;
  final double net;
  final List<CategoryTotal> categories;

  factory ReportSummary.fromJson(Map<String, dynamic> json) => ReportSummary(
        startDate: DateTime.parse(json['start_date'] as String),
        endDate: DateTime.parse(json['end_date'] as String),
        totalIncome: _toDouble(json['total_income']),
        totalExpense: _toDouble(json['total_expense']),
        net: _toDouble(json['net']),
        categories: (json['categories'] as List<dynamic>? ?? const [])
            .map((e) => CategoryTotal.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

class TrendPoint {
  const TrendPoint({
    required this.date,
    required this.income,
    required this.expense,
  });

  final DateTime date;
  final double income;
  final double expense;

  /// Saldo bersih hari itu (income − expense).
  double get net => income - expense;

  factory TrendPoint.fromJson(Map<String, dynamic> json) => TrendPoint(
        date: DateTime.parse(json['date'] as String),
        income: _toDouble(json['income']),
        expense: _toDouble(json['expense']),
      );
}

class ReportTrend {
  const ReportTrend({
    required this.startDate,
    required this.endDate,
    required this.points,
  });

  final DateTime startDate;
  final DateTime endDate;
  final List<TrendPoint> points;

  factory ReportTrend.fromJson(Map<String, dynamic> json) => ReportTrend(
        startDate: DateTime.parse(json['start_date'] as String),
        endDate: DateTime.parse(json['end_date'] as String),
        points: (json['points'] as List<dynamic>? ?? const [])
            .map((e) => TrendPoint.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

double _toDouble(dynamic value) {
  if (value is num) return value.toDouble();
  return double.parse(value.toString());
}
