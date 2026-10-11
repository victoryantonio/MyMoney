/// Model hasil fitur "Matching Mutasi" (Req 9) — cermin dari
/// `MutationMatchResponse` di backend (`app/api/mutations.py`).
///
/// Backend mengirim Decimal sebagai string (pydantic v2) → parse lewat
/// [_toDouble].
library;

double _toDouble(Object? value) {
  if (value == null) return 0;
  if (value is num) return value.toDouble();
  return double.tryParse(value.toString()) ?? 0;
}

/// Satu baris mutasi bank hasil ekstraksi LLM.
class ParsedMutationModel {
  const ParsedMutationModel({
    this.date,
    this.time,
    required this.description,
    required this.amount,
    required this.direction,
  });

  /// `yyyy-MM-dd` (null bila tanggal tidak terbaca).
  final String? date;

  /// `HH:mm` (null bila jam tidak terbaca).
  final String? time;
  final String description;
  final double amount;

  /// `debit` (dana keluar) atau `credit` (dana masuk).
  final String direction;

  bool get isDebit => direction == 'debit';

  factory ParsedMutationModel.fromJson(Map<String, dynamic> json) =>
      ParsedMutationModel(
        date: json['date'] as String?,
        time: json['time'] as String?,
        description: json['description'] as String? ?? '',
        amount: _toDouble(json['amount']),
        direction: json['direction'] as String? ?? 'debit',
      );
}

/// Satu pasangan mutasi ↔ transaksi yang sudah tercatat di sistem.
class MutationMatchModel {
  const MutationMatchModel({
    required this.mutation,
    required this.transactionId,
    required this.transactionType,
    required this.transactionAmount,
    required this.transactionDate,
    this.transactionMerchant,
    required this.dayDiff,
    required this.amountDiff,
  });

  final ParsedMutationModel mutation;
  final String transactionId;
  final String transactionType; // income | expense | transfer
  final double transactionAmount;
  final String transactionDate;
  final String? transactionMerchant;

  /// Selisih hari antara tanggal mutasi dan tanggal transaksi.
  final int dayDiff;

  /// Selisih nominal (mutasi − transaksi) dalam rupiah.
  final double amountDiff;

  factory MutationMatchModel.fromJson(Map<String, dynamic> json) =>
      MutationMatchModel(
        mutation: ParsedMutationModel.fromJson(
          (json['mutation'] as Map<String, dynamic>?) ?? const {},
        ),
        transactionId: json['transaction_id'] as String? ?? '',
        transactionType: json['transaction_type'] as String? ?? 'expense',
        transactionAmount: _toDouble(json['transaction_amount']),
        transactionDate: json['transaction_date'] as String? ?? '',
        transactionMerchant: json['transaction_merchant'] as String?,
        dayDiff: (json['day_diff'] as num?)?.toInt() ?? 0,
        amountDiff: _toDouble(json['amount_diff']),
      );
}

/// Ringkasan satu proses Matching Mutasi.
class MutationMatchResult {
  const MutationMatchResult({
    this.accountId,
    this.accountName,
    this.sourceDescription,
    required this.totalMutations,
    required this.matchedCount,
    required this.unmatchedMutationCount,
    required this.unmatchedTransactionCount,
    required this.matches,
    required this.unmatchedMutations,
    required this.createdPendingIds,
  });

  final String? accountId;
  final String? accountName;

  /// Nama akun yang terbaca dari statement (hint), bila ada.
  final String? sourceDescription;
  final int totalMutations;
  final int matchedCount;
  final int unmatchedMutationCount;
  final int unmatchedTransactionCount;
  final List<MutationMatchModel> matches;

  /// Mutasi yang belum ada padanannya → otomatis dibuat sebagai
  /// `pending_transaction` (bukan transaksi final).
  final List<ParsedMutationModel> unmatchedMutations;
  final List<String> createdPendingIds;

  factory MutationMatchResult.fromJson(Map<String, dynamic> json) =>
      MutationMatchResult(
        accountId: json['account_id'] as String?,
        accountName: json['account_name'] as String?,
        sourceDescription: json['source_description'] as String?,
        totalMutations: (json['total_mutations'] as num?)?.toInt() ?? 0,
        matchedCount: (json['matched_count'] as num?)?.toInt() ?? 0,
        unmatchedMutationCount:
            (json['unmatched_mutation_count'] as num?)?.toInt() ?? 0,
        unmatchedTransactionCount:
            (json['unmatched_transaction_count'] as num?)?.toInt() ?? 0,
        matches: ((json['matches'] as List<dynamic>?) ?? const [])
            .whereType<Map<String, dynamic>>()
            .map(MutationMatchModel.fromJson)
            .toList(),
        unmatchedMutations:
            ((json['unmatched_mutations'] as List<dynamic>?) ?? const [])
                .whereType<Map<String, dynamic>>()
                .map(ParsedMutationModel.fromJson)
                .toList(),
        createdPendingIds:
            ((json['created_pending_ids'] as List<dynamic>?) ?? const [])
                .map((e) => e.toString())
                .toList(),
      );
}
