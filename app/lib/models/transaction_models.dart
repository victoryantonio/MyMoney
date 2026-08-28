/// Model untuk fitur transaksi & Scan Nota (OCR receipt).
///
/// Backend mengirim Decimal sebagai string JSON (mis. "21000") — semua
/// konversi angka lewat [_toDouble] agar tahan terhadap `num` maupun `String`.
library;

/// Konversi nilai JSON (num | String) menjadi double.
double _toDouble(dynamic v) {
  if (v is num) return v.toDouble();
  return double.tryParse(v?.toString() ?? '') ?? 0;
}

DateTime _toDateTime(dynamic v) {
  final s = v?.toString();
  if (s == null || s.isEmpty) return DateTime.now();
  return DateTime.tryParse(s) ?? DateTime.now();
}

class CategoryModel {
  const CategoryModel({
    required this.id,
    required this.name,
    required this.type,
    required this.isDefault,
    required this.isActive,
  });

  final String id;
  final String name;
  final String type; // 'income' | 'expense'
  final bool isDefault;
  final bool isActive;

  factory CategoryModel.fromJson(Map<String, dynamic> json) => CategoryModel(
        id: json['id'] as String,
        name: json['name'] as String,
        type: json['type'] as String,
        isDefault: json['is_default'] as bool? ?? false,
        isActive: json['is_active'] as bool? ?? true,
      );
}

class AccountModel {
  const AccountModel({
    required this.id,
    required this.accountName,
    required this.accountType,
    required this.initialBalance,
    required this.currentBalance,
    required this.netBalance,
    required this.isActive,
  });

  final String id;
  final String accountName;
  final String accountType; // 'cash' | 'ewallet' | 'bank'
  final double initialBalance;
  final double currentBalance;
  final double netBalance;
  final bool isActive;

  /// Label ramah: 'Cash', 'BCA · Bank', 'GoPay · E-Wallet', dst.
  String get label {
    const names = {'cash': 'Cash', 'ewallet': 'E-Wallet', 'bank': 'Bank'};
    final t = names[accountType] ?? accountType;
    return accountType == 'cash' ? accountName : '$accountName · $t';
  }

  factory AccountModel.fromJson(Map<String, dynamic> json) => AccountModel(
        id: json['id'] as String,
        accountName: json['account_name'] as String,
        accountType: json['account_type'] as String? ?? 'cash',
        initialBalance: _toDouble(json['initial_balance']),
        currentBalance: _toDouble(json['current_balance']),
        netBalance: _toDouble(json['net_balance']),
        isActive: json['is_active'] as bool? ?? true,
      );
}

/// Satu baris item hasil OCR nota (bisa diedit — US-08).
class ReceiptItemModel {
  ReceiptItemModel({
    required this.name,
    required this.qty,
    required this.price,
    this.lineTotalOverride,
  });

  String name;
  double qty;
  double price;
  double? lineTotalOverride;

  double get lineTotal => lineTotalOverride ?? qty * price;

  factory ReceiptItemModel.fromJson(Map<String, dynamic> json) => ReceiptItemModel(
        name: json['name'] as String,
        qty: _toDouble(json['qty']),
        price: _toDouble(json['price']),
        lineTotalOverride: json['line_total'] == null
          ? null
          : _toDouble(json['line_total']),
      );

  Map<String, dynamic> toJson() => {
        'name': name,
        'qty': qty,
        'price': price,
      };
}

/// Hasil parse foto nota (POST /api/receipts/ocr).
class ParsedReceipt {
  const ParsedReceipt({
    required this.type,
    required this.items,
    this.merchant,
    this.date,
    this.category,
    this.account,
  });

  final String type; // 'income' | 'expense'
  final String? merchant;
  final String? date; // yyyy-mm-dd
  final String? category;
  final String? account;
  final List<ReceiptItemModel> items;

  double get total => items.fold(0, (sum, i) => sum + i.lineTotal);

  factory ParsedReceipt.fromJson(Map<String, dynamic> json) => ParsedReceipt(
        type: json['type'] as String,
        merchant: json['merchant'] as String?,
        date: json['date'] as String?,
        category: json['category'] as String?,
        account: json['account'] as String?,
        items: (json['items'] as List<dynamic>? ?? const [])
            .map((e) => ReceiptItemModel.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

/// Satu item dalam transaksi tersimpan (GET /api/transactions).
class TransactionItem {
  const TransactionItem({
    required this.id,
    required this.name,
    required this.qty,
    required this.price,
  });

  final String id;
  final String name;
  final double qty;
  final double price;

  double get lineTotal => qty * price;

  factory TransactionItem.fromJson(Map<String, dynamic> json) => TransactionItem(
        id: json['id'] as String,
        name: json['name'] as String,
        qty: _toDouble(json['qty']),
        price: _toDouble(json['price']),
      );
}

/// Satu transaksi tersimpan (TransactionResponse backend).
class TransactionModel {
  const TransactionModel({
    required this.id,
    required this.type,
    required this.totalAmount,
    required this.categoryId,
    required this.accountId,
    required this.source,
    required this.transactionDate,
    required this.createdAt,
    this.originalCurrency = 'IDR',
    this.exchangeRate = 1.0,
    this.toAccountId,
    this.merchant,
    this.note,
    this.confidence,
    this.receiptImageUrl,
    this.items = const [],
  });

  final String id;
  final String type; // 'income' | 'expense' | 'transfer'
  // SELALU dalam IDR — basis laporan/saldo (migrasi 0009).
  final double totalAmount;
  /// Mata uang asli saat input (ISO 4217, default 'IDR').
  final String originalCurrency;
  /// 1 unit originalCurrency berapa IDR (default 1).
  final double exchangeRate;
  final String? categoryId; // null untuk transfer
  final String accountId;
  final String? toAccountId; // hanya terisi saat type == 'transfer'
  final String? merchant;
  final String source;
  final String? note;
  final String? confidence;
  final String? receiptImageUrl;
  final DateTime transactionDate;
  final DateTime createdAt;
  final List<TransactionItem> items;

  /// Nominal asli di mata uang asal (totalAmount dibagi kurs).
  double get originalAmount =>
      exchangeRate > 0 ? totalAmount / exchangeRate : totalAmount;

  factory TransactionModel.fromJson(Map<String, dynamic> json) =>
      TransactionModel(
        id: json['id'] as String,
        type: json['type'] as String,
        totalAmount: _toDouble(json['total_amount']),
        originalCurrency: json['original_currency'] as String? ?? 'IDR',
        exchangeRate: _toDouble(json['exchange_rate'] ?? 1),
        categoryId: json['category_id'] as String?,
        accountId: json['account_id'] as String,
        toAccountId: json['to_account_id'] as String?,
        merchant: json['merchant'] as String?,
        source: json['source'] as String? ?? 'app',
        note: json['note'] as String?,
        confidence: json['confidence'] as String?,
        receiptImageUrl: json['receipt_image_url'] as String?,
        transactionDate: _toDateTime(json['transaction_date']),
        createdAt: _toDateTime(json['created_at']),
        items: (json['items'] as List<dynamic>? ?? const [])
            .map((e) => TransactionItem.fromJson(e as Map<String, dynamic>))
            .toList(),
      );
}

/// Halaman hasil GET /api/transactions (keyset pagination).
class TransactionListResult {
  const TransactionListResult({
    required this.items,
    required this.totalCount,
    this.nextCursor,
  });

  final List<TransactionModel> items;
  final String? nextCursor;
  final int totalCount;

  bool get hasMore => nextCursor != null;

  factory TransactionListResult.fromJson(Map<String, dynamic> json) =>
      TransactionListResult(
        items: (json['items'] as List<dynamic>? ?? const [])
            .map((e) => TransactionModel.fromJson(e as Map<String, dynamic>))
            .toList(),
        nextCursor: json['next_cursor'] as String?,
        totalCount: json['total_count'] as int? ?? 0,
      );
}
