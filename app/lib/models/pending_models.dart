/// Model `pending_transactions` — baris setengah jadi yang menunggu konfirmasi
/// user (CODING_RULES §2.4).
///
/// Cermin dari `PendingTransactionResponse` di backend
/// (`app/schemas/pending.py`). Dipakai layar "Matching" untuk menampilkan
/// mutasi bank yang belum balance dengan transaksi tercatat: user memilih
/// **Konfirmasi** (baru jadi transaksi nyata) atau **Batalkan**.
library;

double _toDouble(Object? value) {
  if (value == null) return 0;
  if (value is num) return value.toDouble();
  return double.tryParse(value.toString()) ?? 0;
}

DateTime? _toDate(Object? value) {
  if (value is! String || value.isEmpty) return null;
  return DateTime.tryParse(value)?.toLocal();
}

/// Satu baris pending yang belum dikonfirmasi.
class PendingTransactionModel {
  const PendingTransactionModel({
    required this.id,
    required this.action,
    required this.type,
    required this.totalAmount,
    required this.categoryId,
    this.categoryName,
    this.accountId,
    this.accountName,
    this.merchant,
    this.note,
    required this.source,
    this.confidence,
    this.rawInput,
    this.expiresAt,
    this.createdAt,
    this.transactionDate,
    this.timezone,
  });

  final String id;

  /// `create` (transaksi baru) atau `update` (mengubah transaksi yang ada).
  final String action;

  /// `income` atau `expense`.
  final String type;
  final double totalAmount;
  final String categoryId;
  final String? categoryName;
  final String? accountId;
  final String? accountName;
  final String? merchant;
  final String? note;
  final String source;
  final String? confidence;
  final String? rawInput;
  final DateTime? expiresAt;
  final DateTime? createdAt;

  /// Tanggal+jam transaksi ASLI dari mutasi bank (sudah dikonversi ke waktu
  /// lokal perangkat). Diisi backend untuk pending hasil Matching Mutasi; saat
  /// user mengonfirmasi, nilai ini dipakai apa adanya — bukan waktu konfirmasi.
  final DateTime? transactionDate;

  /// Nama zona waktu yang dipakai backend saat menafsirkan tanggal mutasi
  /// (mis. `Asia/Jakarta`).
  final String? timezone;

  /// `true` bila dana keluar — dipakai untuk warna & ikon arah.
  bool get isExpense => type == 'expense';

  /// Label yang enak dibaca untuk baris ini (merchant → catatan → kategori).
  String get label {
    final text = (merchant ?? '').trim();
    if (text.isNotEmpty) return text;
    final noteText = (note ?? '').trim();
    if (noteText.isNotEmpty) return noteText;
    return categoryName ?? 'Transaksi pending';
  }

  factory PendingTransactionModel.fromJson(Map<String, dynamic> json) =>
      PendingTransactionModel(
        id: json['id'] as String? ?? '',
        action: json['action'] as String? ?? 'create',
        type: json['type'] as String? ?? 'expense',
        totalAmount: _toDouble(json['total_amount']),
        categoryId: json['category_id'] as String? ?? '',
        categoryName: json['category_name'] as String?,
        accountId: json['account_id'] as String?,
        accountName: json['account_name'] as String?,
        merchant: json['merchant'] as String?,
        note: json['note'] as String?,
        source: json['source'] as String? ?? 'app',
        confidence: json['confidence'] as String?,
        rawInput: json['raw_input'] as String?,
        expiresAt: _toDate(json['expires_at']),
        createdAt: _toDate(json['created_at']),
        transactionDate: _toDate(json['transaction_date']),
        timezone: json['timezone'] as String?,
      );
}

/// Hasil konfirmasi satu pending — id transaksi nyata yang terbentuk.
class PendingConfirmResult {
  const PendingConfirmResult({
    required this.pendingId,
    required this.transactionId,
    required this.type,
    required this.totalAmount,
  });

  final String pendingId;
  final String transactionId;
  final String type;
  final double totalAmount;

  factory PendingConfirmResult.fromJson(Map<String, dynamic> json) =>
      PendingConfirmResult(
        pendingId: json['pending_id'] as String? ?? '',
        transactionId: json['transaction_id'] as String? ?? '',
        type: json['type'] as String? ?? 'expense',
        totalAmount: _toDouble(json['total_amount']),
      );
}
