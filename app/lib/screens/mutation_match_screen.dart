/// Screen "Matching Mutasi" (Req 9) — dibuka dari menu Dashboard → Upload.
///
/// Alur:
///   1. User memilih screenshot/foto mutasi bank, e-statement PDF, atau ekspor
///      CSV dan opsional menentukan akun.
///   2. Backend (`POST /api/mutations/match`) membaca mutasi via vision LLM,
///      lalu mencocokkan setiap baris dengan transaksi yang sudah tercatat
///      (nominal + arah dana + jarak tanggal + akun).
///   3. Hasil ditampilkan: pasangan yang cocok, dan mutasi yang belum tercatat
///      yang sudah dibuat sebagai *pending transaction* untuk dikonfirmasi user
///      (CODING_RULES §2.4 — hasil LLM tidak pernah langsung jadi transaksi).
///
/// Flutter = thin client: seluruh logika pembacaan & pencocokan ada di backend.
library;

import 'dart:async';
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../models/mutation_models.dart';
import '../models/transaction_models.dart';
import 'pending_review_screen.dart';

/// Hasil pemilihan berkas mutasi (screenshot/foto, PDF e-statement, atau CSV).
class PickedMutationFile {
  const PickedMutationFile({required this.bytes, required this.name});

  final Uint8List bytes;
  final String name;

  bool get isPdf => name.toLowerCase().endsWith('.pdf');

  bool get isCsv {
    final lower = name.toLowerCase();
    return lower.endsWith('.csv') || lower.endsWith('.txt') || lower.endsWith('.tsv');
  }

  /// Berkas non-gambar → pratinjau pakai ikon dokumen, bukan `Image.memory`.
  bool get isDocument => isPdf || isCsv;
}

/// Sumber berkas mutasi yang bisa dipilih user.
enum MutationSource {
  /// Kamera (screenshot langsung dari aplikasi bank).
  camera,

  /// Galeri/foto.
  gallery,

  /// Dokumen PDF e-statement dari penyimpanan.
  document,
}

/// Pengambil berkas — overridable di widget test (tanpa kamera/galeri nyata).
typedef MutationFilePickFn = Future<PickedMutationFile?> Function(MutationSource source);

/// Implementasi default: kamera/galeri lewat `image_picker`, PDF lewat
/// `file_picker` (`image_picker` tidak bisa memilih dokumen).
Future<PickedMutationFile?> _pickMutationFile(MutationSource source) async {
  if (source == MutationSource.document) return _pickStatementDocument();

  final file = await ImagePicker().pickImage(
    source: source == MutationSource.camera ? ImageSource.camera : ImageSource.gallery,
    imageQuality: 85,
    maxWidth: 2000,
  );
  if (file == null) return null;
  return PickedMutationFile(bytes: await file.readAsBytes(), name: file.name);
}

/// Pilih e-statement PDF dari penyimpanan perangkat.
Future<PickedMutationFile?> _pickStatementDocument() async {
  final result = await FilePicker.pickFiles(
    type: FileType.custom,
    allowedExtensions: const ['pdf'],
    withData: true,
    dialogTitle: 'Pilih e-statement PDF',
  );
  final picked = result?.files.singleOrNull;
  if (picked == null) return null;
  final bytes = picked.bytes;
  if (bytes == null || bytes.isEmpty) return null;
  return PickedMutationFile(bytes: bytes, name: picked.name);
}

enum _Stage { select, preview, result }

class MutationMatchScreen extends StatefulWidget {
  const MutationMatchScreen({
    super.key,
    required this.api,
    this.pickFile,
    this.onPendingCreated,
  });

  final ApiClient api;

  /// Overridable untuk test; default = kamera/galeri asli.
  final MutationFilePickFn? pickFile;

  /// Dipanggil setelah pending transaction dibuat (dashboard bisa menyegarkan
  /// daftar transaksi/pending).
  final VoidCallback? onPendingCreated;

  @override
  State<MutationMatchScreen> createState() => _MutationMatchScreenState();
}

class _MutationMatchScreenState extends State<MutationMatchScreen> {
  late final MutationFilePickFn _pickFile = widget.pickFile ?? _pickMutationFile;

  _Stage _stage = _Stage.select;
  PickedMutationFile? _file;
  bool _processing = false;
  String? _error;

  MutationMatchResult? _result;

  List<AccountModel> _accounts = [];
  String? _accountId; // null = semua akun

  @override
  void initState() {
    super.initState();
    _loadAccounts();
  }

  Future<void> _loadAccounts() async {
    try {
      final accounts = await widget.api.fetchAccounts();
      if (!mounted) return;
      setState(() => _accounts = accounts.where((a) => a.isActive).toList());
    } catch (_) {
      // Best-effort: tanpa daftar akun, pencocokan berjalan lintas akun.
    }
  }

  Future<void> _pick(MutationSource source) async {
    final picked = await _pickFile(source);
    if (picked == null) return;
    setState(() {
      _file = picked;
      _error = null;
      _result = null;
      _stage = _Stage.preview;
    });
  }

  Future<void> _run() async {
    final file = _file;
    if (file == null) return;
    setState(() {
      _processing = true;
      _error = null;
    });
    try {
      final result = await widget.api.matchMutations(
        bytes: file.bytes,
        filename: file.name,
        accountId: _accountId,
      );
      if (!mounted) return;
      if (result.createdPendingIds.isNotEmpty) widget.onPendingCreated?.call();
      setState(() {
        _result = result;
        _processing = false;
        _stage = _Stage.result;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _processing = false;
        _error = e.message;
      });
    }
  }

  void _reset() {
    // Sisa pending dari unggahan ini dibuang dulu — hasilnya tidak bisa
    // dijangkau lagi setelah layar di-reset.
    unawaited(_discardUnconfirmedPendings());
    setState(() {
      _file = null;
      _result = null;
      _error = null;
      _stage = _Stage.select;
    });
  }

  /// Batalkan (best-effort) semua pending yang dibuat oleh unggahan ini.
  ///
  /// Baris yang sudah dikonfirmasi/dibatalkan lewat layar Matching akan
  /// menghasilkan 404 — diabaikan. Tidak ada `setState` di sini karena bisa
  /// dipanggil saat layar sedang ditinggalkan.
  Future<void> _discardUnconfirmedPendings() async {
    final ids = _result?.createdPendingIds ?? const <String>[];
    if (ids.isEmpty) return;
    for (final id in ids) {
      try {
        await widget.api.cancelPending(id);
      } on ApiException {
        // Sudah dikonfirmasi/dibatalkan, atau jaringan bermasalah: backend
        // masih punya pembersihan sendiri (kedaluwarsa + unggahan berikutnya).
      }
    }
  }

  /// Tombol **Matching** — buka layar Pending untuk baris yang belum cocok.
  ///
  /// Hasil unggahan ini sudah tersimpan sebagai `pending_transaction` di
  /// backend, jadi layar Pending memuatnya dari server (selalu sinkron) dan
  /// baris terbaru ditampilkan lebih dulu.
  Future<void> _openPendingReview() async {
    final createdIds = _result?.createdPendingIds ?? const <String>[];
    var changed = false;
    await Navigator.of(context).push<bool>(
      MaterialPageRoute<bool>(
        builder: (_) => PendingReviewScreen(
          api: widget.api,
          initialIds: createdIds,
          title: 'Matching — Pending',
          onChanged: () {
            changed = true;
            widget.onPendingCreated?.call();
          },
        ),
      ),
    );
    if (changed && mounted) {
      // Baris sudah dipindahkan ke transaksi / dibuang di layar Pending —
      // tampilkan ringkasan terbaru agar tidak menyesatkan.
      widget.onPendingCreated?.call();
    }
  }

  /// Baris di bawah layar: satu tombol besar untuk menyelesaikan pending.
  Widget _buildMatchingBar() {
    final pendingCount = _result?.createdPendingIds.length ?? 0;
    return SafeArea(
      minimum: const EdgeInsets.fromLTRB(16, 8, 16, 16),
      child: FilledButton.icon(
        onPressed: _openPendingReview,
        icon: const Icon(Icons.rule_folder_outlined),
        label: Text(
          pendingCount > 0
              ? 'Matching — konfirmasi $pendingCount baris'
              : 'Matching',
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final showMatchingBar =
        _stage == _Stage.result && (_result?.unmatchedMutations.isNotEmpty ?? false);
    // Bila unggahan ini menghasilkan baris pending, keluar dari layar berarti
    // menutup satu-satunya jalan menuju baris tersebut. Jadi baris yang belum
    // dikonfirmasi dibuang lebih dulu supaya `pending_transactions` tetap bersih.
    final guardPendingOnExit =
        _stage == _Stage.result && (_result?.createdPendingIds.isNotEmpty ?? false);
    return PopScope(
      canPop: !guardPendingOnExit,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        final navigator = Navigator.of(context);
        await _discardUnconfirmedPendings();
        navigator.pop();
      },
      child: Scaffold(
        appBar: AppBar(title: const Text('Matching Mutasi')),
        body: SafeArea(
          child: switch (_stage) {
            _Stage.select => _buildSelect(),
            _Stage.preview => _buildPreview(),
            _Stage.result => _buildResult(),
          },
        ),
        bottomNavigationBar: showMatchingBar ? _buildMatchingBar() : null,
      ),
    );
  }

  // ── Stage 1: pilih berkas + akun ──────────────────────────────────────────

  Widget _buildSelect() {
    return ListView(
      padding: const EdgeInsets.all(24),
      children: [
        Icon(
          Icons.upload_file_outlined,
          size: 64,
          color: Theme.of(context).colorScheme.primary,
        ),
        const SizedBox(height: 16),
        Text(
          'Cocokkan mutasi bank dengan catatan',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.titleMedium,
        ),
        const SizedBox(height: 8),
        Text(
          'Unggah screenshot/foto mutasi (m-banking), e-statement PDF, atau ekspor CSV. Sistem membaca setiap baris mutasi, lalu memeriksa apakah nominalnya sudah balance dengan transaksi yang tercatat. '
          'Mutasi yang belum tercatat akan masuk sebagai transaksi pending untuk kamu konfirmasi.',
          textAlign: TextAlign.center,
          style: Theme.of(context).textTheme.bodySmall,
        ),
        const SizedBox(height: 24),
        if (_accounts.isNotEmpty)
          DropdownButtonFormField<String?>(
            initialValue: _accountId,
            decoration: const InputDecoration(
              labelText: 'Akun (opsional)',
              border: OutlineInputBorder(),
              helperText: 'Pilih akun yang mutasinya diunggah agar cocok lebih akurat',
            ),
            items: [
              const DropdownMenuItem<String?>(value: null, child: Text('Semua akun')),
              ..._accounts.map(
                (a) => DropdownMenuItem<String?>(value: a.id, child: Text(a.label)),
              ),
            ],
            onChanged: (value) => setState(() => _accountId = value),
          ),
        const SizedBox(height: 16),
        FilledButton.icon(
          onPressed: () => _pick(MutationSource.camera),
          icon: const Icon(Icons.camera_alt_outlined),
          label: const Text('Ambil Foto Mutasi'),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: () => _pick(MutationSource.gallery),
          icon: const Icon(Icons.photo_library_outlined),
          label: const Text('Pilih dari Galeri'),
        ),
        const SizedBox(height: 12),
        OutlinedButton.icon(
          onPressed: () => _pick(MutationSource.document),
          icon: const Icon(Icons.picture_as_pdf_outlined),
          label: const Text('Pilih PDF E-Statement'),
        ),
        if (_error != null) ...[
          const SizedBox(height: 16),
          _ErrorBanner(message: _error!),
        ],
      ],
    );
  }

  // ── Stage 2: pratinjau + jalankan pencocokan ──────────────────────────────

  Widget _buildPreview() {
    final file = _file;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: file == null || file.isDocument
                  ? Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(
                            file?.isPdf == true
                                ? Icons.picture_as_pdf_outlined
                                : Icons.description_outlined,
                            size: 56,
                          ),
                          const SizedBox(height: 8),
                          Text(file?.name ?? '-'),
                        ],
                      ),
                    )
                  : Image.memory(file.bytes, fit: BoxFit.contain),
            ),
          ),
          const SizedBox(height: 16),
          if (_processing)
            const Column(
              children: [
                CircularProgressIndicator(),
                SizedBox(height: 12),
                Text('Membaca & mencocokkan mutasi…'),
              ],
            )
          else ...[
            FilledButton.icon(
              onPressed: _run,
              icon: const Icon(Icons.playlist_add_check_circle_outlined),
              label: const Text('Cocokkan Mutasi'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: _reset,
              icon: const Icon(Icons.refresh),
              label: const Text('Pilih Ulang'),
            ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              _ErrorBanner(message: _error!),
            ],
          ],
        ],
      ),
    );
  }

  // ── Stage 3: hasil ────────────────────────────────────────────────────────

  Widget _buildResult() {
    final result = _result!;
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Ringkasan', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                _summaryRow('Baris mutasi terbaca', '${result.totalMutations}'),
                _summaryRow('Cocok dengan transaksi', '${result.matchedCount}'),
                _summaryRow(
                  'Belum tercatat',
                  '${result.unmatchedMutationCount} → dibuat pending',
                ),
                if (result.accountName != null)
                  _summaryRow('Akun', result.accountName!),
                if (result.unmatchedTransactionCount > 0)
                  _summaryRow(
                    'Transaksi belum ada di mutasi',
                    '${result.unmatchedTransactionCount}',
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        if (result.matches.isNotEmpty) ...[
          Text('Mutasi yang cocok', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          ...result.matches.map(_matchTile),
          const SizedBox(height: 16),
        ],
        if (result.unmatchedMutations.isNotEmpty) ...[
          Text(
            'Belum tercatat (pending)',
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 4),
          Text(
            'Baris berikut belum balance dengan transaksi mana pun. Sistem sudah memasukkannya sebagai transaksi pending — tekan tombol Matching di bawah untuk mengonfirmasi atau membatalkannya.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 8),
          ...result.unmatchedMutations.map(_unmatchedTile),
          const SizedBox(height: 16),
        ],
        if (result.matches.isEmpty && result.unmatchedMutations.isEmpty)
          const ListTile(
            leading: Icon(Icons.info_outline),
            title: Text('Tidak ada baris mutasi yang terbaca'),
          ),
        OutlinedButton.icon(
          onPressed: _reset,
          icon: const Icon(Icons.upload_file_outlined),
          label: const Text('Unggah Mutasi Lain'),
        ),
      ],
    );
  }

  Widget _summaryRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        children: [
          Expanded(child: Text(label)),
          Text(value, style: const TextStyle(fontWeight: FontWeight.w600)),
        ],
      ),
    );
  }

  Widget _matchTile(MutationMatchModel match) {
    final m = match.mutation;
    return Card(
      child: ListTile(
        leading: Icon(
          m.isDebit ? Icons.arrow_upward : Icons.arrow_downward,
          color: m.isDebit ? Colors.red : Colors.green,
        ),
        title: Text(m.description, maxLines: 2, overflow: TextOverflow.ellipsis),
        subtitle: Text(
          '${m.date ?? '-'}${m.time != null ? ' ${m.time}' : ''} · '
          '${formatRupiah(m.amount)} → '
          '${match.transactionMerchant ?? match.transactionType}'
          '${match.dayDiff != 0 ? ' (H+${match.dayDiff})' : ''}',
        ),
        trailing: Text(
          match.transactionType,
          style: Theme.of(context).textTheme.labelSmall,
        ),
      ),
    );
  }

  Widget _unmatchedTile(ParsedMutationModel mutation) {
    return Card(
      child: ListTile(
        leading: Icon(
          mutation.isDebit ? Icons.arrow_upward : Icons.arrow_downward,
          color: mutation.isDebit ? Colors.red : Colors.green,
        ),
        title: Text(mutation.description, maxLines: 2, overflow: TextOverflow.ellipsis),
        subtitle: Text(
          '${mutation.date ?? '-'}'
          '${mutation.time != null ? ' ${mutation.time}' : ''} · '
          '${mutation.isDebit ? 'Dana keluar' : 'Dana masuk'}',
        ),
        trailing: Text(formatRupiah(mutation.amount)),
      ),
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    final scheme = Theme.of(context).colorScheme;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: scheme.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline, color: scheme.onErrorContainer),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: TextStyle(color: scheme.onErrorContainer),
            ),
          ),
        ],
      ),
    );
  }
}
