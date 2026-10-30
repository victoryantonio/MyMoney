/// Layar "Pending" — daftar baris mutasi yang belum balance dengan transaksi
/// tercatat, menunggu keputusan user.
///
/// Kenapa layar ini ada: "Matching Mutasi" tidak pernah menyimpan hasil bacaan
/// LLM langsung sebagai transaksi (CODING_RULES §2.4). Baris yang belum cocok
/// masuk `pending_transactions`. Sebelumnya user diberi tahu untuk membuka
/// "menu Pending" yang belum pernah ada, sehingga baris tersebut menggantung.
///
/// Layar ini dibuka dari tombol **Matching** di layar hasil Matching Mutasi
/// (dan bisa dibuka ulang kapan saja). Setiap baris punya dua aksi:
///   * **Konfirmasi** → `POST /api/pending/{id}/confirm` → transaksi nyata
///   * **Batalkan**   → `POST /api/pending/{id}/cancel`  → baris dibuang
///
/// Tombol **Konfirmasi Semua** (ikon centang ganda di header) menjalankan aksi
/// konfirmasi untuk seluruh baris sekaligus, satu permintaan per baris, setelah
/// user menyetujui dialog konfirmasi.
///
/// Menekan **Back** (ikon panah kiri / back sistem) saat masih ada baris yang
/// belum diputuskan memunculkan peringatan *"Apakah anda yakin ingin
/// meninggalkan halaman ini? Data tidak akan disimpan"* — tanpa itu, baris
/// pending tertinggal tanpa pernah dikonfirmasi.
///
/// Baris yang tidak pernah disentuh tidak akan menumpuk: backend membuang
/// pending kedaluwarsa dan pending lama saat user mengunggah mutasi baru.
library;

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../models/pending_models.dart';

class PendingReviewScreen extends StatefulWidget {
  const PendingReviewScreen({
    super.key,
    required this.api,
    this.initialIds,
    this.title = 'Pending',
    this.onChanged,
    this.onResolved,
  });

  final ApiClient api;

  /// Id pending yang ingin ditonjolkan lebih dulu (hasil unggahan terakhir).
  /// Tetap diambil dari server agar isinya selalu sinkron.
  final List<String>? initialIds;

  final String title;

  /// Dipanggil setiap kali satu baris dikonfirmasi/dibatalkan — pemanggil bisa
  /// menyegarkan dashboard tanpa menunggu layar ini ditutup.
  final VoidCallback? onChanged;

  /// Dipanggil dengan id baris yang sudah **selesai** (dikonfirmasi atau
  /// dibatalkan). Pemanggil memakainya untuk berhenti menghitung baris itu
  /// sebagai pending yang masih menunggu.
  final ValueChanged<String>? onResolved;

  @override
  State<PendingReviewScreen> createState() => _PendingReviewScreenState();
}

class _PendingReviewScreenState extends State<PendingReviewScreen> {
  List<PendingTransactionModel> _items = const [];
  bool _loading = true;
  String? _error;

  /// Id yang sedang diproses — tombol baris itu dinonaktifkan sementara.
  final Set<String> _busy = {};

  /// Ada minimal satu baris yang sudah dikonfirmasi/dibatalkan.
  bool _changed = false;

  /// Sedang menjalankan "Konfirmasi Semua" (tombol header).
  bool _confirmingAll = false;

  /// Progres konfirmasi massal: sudah diproses / total target.
  int _confirmProgress = 0;
  int _confirmTotal = 0;

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
      final items = await widget.api.fetchPendingTransactions();
      if (!mounted) return;
      setState(() {
        // Baris dari unggahan terakhir diletakkan di atas agar mudah ditemukan.
        final highlight = widget.initialIds;
        if (highlight != null && highlight.isNotEmpty) {
          final wanted = highlight.toSet();
          items.sort((a, b) {
            final aIn = wanted.contains(a.id) ? 0 : 1;
            final bIn = wanted.contains(b.id) ? 0 : 1;
            return aIn.compareTo(bIn);
          });
        }
        _items = items;
        _loading = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _loading = false;
        _error = e.message;
      });
    }
  }

  Future<void> _confirm(PendingTransactionModel item) async {
    if (_confirmingAll || _busy.contains(item.id)) return;
    setState(() => _busy.add(item.id));
    try {
      await widget.api.confirmPending(item.id);
      if (!mounted) return;
      setState(() {
        _items = _items.where((row) => row.id != item.id).toList();
        _busy.remove(item.id);
        _changed = true;
      });
      widget.onResolved?.call(item.id);
      widget.onChanged?.call();
      _snack('Transaksi tersimpan: ${formatRupiah(item.totalAmount)}');
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _busy.remove(item.id));
      _snack(e.message, error: true);
      // Pending bisa saja sudah kedaluwarsa / hilang → segarkan daftar.
      await _load();
    }
  }

  Future<void> _cancel(PendingTransactionModel item) async {
    if (_confirmingAll || _busy.contains(item.id)) return;
    setState(() => _busy.add(item.id));
    try {
      await widget.api.cancelPending(item.id);
      if (!mounted) return;
      setState(() {
        _items = _items.where((row) => row.id != item.id).toList();
        _busy.remove(item.id);
        _changed = true;
      });
      widget.onResolved?.call(item.id);
      widget.onChanged?.call();
      _snack('Baris dihapus — tidak ada transaksi yang dibuat');
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _busy.remove(item.id));
      _snack(e.message, error: true);
      await _load();
    }
  }

  /// Minta persetujuan sebelum menyimpan semua baris sebagai transaksi nyata.
  Future<bool?> _askConfirmAll(int count) {
    return showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Konfirmasi semua baris?'),
        content: Text(
          '$count baris akan disimpan sebagai transaksi nyata. '
          'Tindakan ini tidak bisa dibatalkan.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Batal'),
          ),
          FilledButton(
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Ya, konfirmasi semua'),
          ),
        ],
      ),
    );
  }

  /// Konfirmasi **semua** baris sekaligus — aksi tombol centang di header.
  ///
  /// Dikirim satu per satu (`POST /api/pending/{id}/confirm`) supaya satu baris
  /// yang bermasalah (mis. sudah kedaluwarsa / hilang) tidak menggagalkan
  /// sisanya, dan supaya `onResolved` tetap dipanggil per id sehingga pemanggil
  /// bisa memperbarui hitungan pending-nya.
  Future<void> _confirmAll() async {
    if (_confirmingAll || _busy.isNotEmpty || _items.isEmpty) return;

    final targets = _items.where((row) => !_busy.contains(row.id)).toList();
    if (targets.isEmpty) return;

    final approved = await _askConfirmAll(targets.length);
    if (approved != true) return;
    if (!mounted) return;

    setState(() {
      _confirmingAll = true;
      _confirmProgress = 0;
      _confirmTotal = targets.length;
    });

    final confirmed = <String>{};
    String? firstError;
    var processed = 0;

    for (final item in targets) {
      try {
        await widget.api.confirmPending(item.id);
        confirmed.add(item.id);
        widget.onResolved?.call(item.id);
      } on ApiException catch (e) {
        firstError ??= e.message;
      }
      processed++;
      if (!mounted) return;
      setState(() => _confirmProgress = processed);
    }

    if (!mounted) return;
    setState(() {
      _items = _items.where((row) => !confirmed.contains(row.id)).toList();
      _confirmingAll = false;
      _confirmProgress = 0;
      _confirmTotal = 0;
      _changed = _changed || confirmed.isNotEmpty;
    });

    if (confirmed.isNotEmpty) widget.onChanged?.call();

    if (firstError == null) {
      _snack('${confirmed.length} transaksi tersimpan');
      return;
    }
    if (confirmed.isEmpty) {
      _snack('Gagal mengonfirmasi: $firstError', error: true);
    } else {
      _snack(
        '${confirmed.length} tersimpan, ${targets.length - confirmed.length} '
        'gagal: $firstError',
        error: true,
      );
    }
    // Sebagian gagal → ambil ulang daftar dari server agar isinya akurat.
    await _load();
  }

  void _snack(String message, {bool error = false}) {
    final messenger = ScaffoldMessenger.maybeOf(context);
    if (messenger == null) return;
    messenger.showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: error
            ? Theme.of(context).colorScheme.error
            : Theme.of(context).colorScheme.primary,
      ),
    );
  }

  /// Apakah meninggalkan layar ini berpotensi "kehilangan" pekerjaan?
  ///
  /// Selama masih ada baris pending yang belum dikonfirmasi/dibatalkan,
  /// meninggalkan layar berarti baris itu tetap menggantung — jadi user perlu
  /// diberi peringatan lebih dulu.
  bool get _hasUnconfirmedRows => _items.isNotEmpty || _busy.isNotEmpty;

  /// Dialog "Apakah anda yakin ingin meninggalkan halaman ini?".
  ///
  /// Mengembalikan `true` bila user memilih **Ya** (boleh keluar).
  Future<bool> _confirmLeave() async {
    final choice = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => AlertDialog(
        title: const Text('Tinggalkan halaman?'),
        content: const Text(
          'Apakah anda yakin ingin meninggalkan halaman ini? '
          'Data tidak akan disimpan',
        ),
        actions: [
          TextButton(
            key: const Key('leave-no'),
            onPressed: () => Navigator.of(dialogContext).pop(false),
            child: const Text('Tidak'),
          ),
          FilledButton(
            key: const Key('leave-yes'),
            onPressed: () => Navigator.of(dialogContext).pop(true),
            child: const Text('Ya'),
          ),
        ],
      ),
    );
    return choice ?? false;
  }

  /// Handler tombol Back (ikon panah kiri) sekaligus gesture/back sistem.
  Future<void> _handleBack() async {
    if (_confirmingAll) {
      _snack('Tunggu konfirmasi massal selesai…');
      return;
    }
    final navigator = Navigator.of(context);
    if (_hasUnconfirmedRows && !await _confirmLeave()) return;
    if (!mounted) return;
    // `_changed` diteruskan ke pemanggil agar dashboard bisa menyegarkan data.
    navigator.pop(_changed);
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      // Selama masih ada baris yang belum diputuskan, pop dicegat lebih dulu
      // supaya user melihat peringatan "data tidak akan disimpan".
      canPop: !_hasUnconfirmedRows,
      onPopInvokedWithResult: (didPop, _) async {
        if (didPop) return;
        if (_confirmingAll) {
          _snack('Tunggu konfirmasi massal selesai…');
          return;
        }
        final navigator = Navigator.of(context);
        if (!await _confirmLeave()) return;
        if (!mounted) return;
        navigator.pop(_changed);
      },
      child: Scaffold(
        appBar: AppBar(
          title: Text(widget.title),
          // BackButton eksplisit: hasil pop membawa `_changed` supaya layar
          // pemanggil tahu ada transaksi baru tanpa harus memuat ulang.
          leading: BackButton(onPressed: _handleBack),
          actions: [
            IconButton(
              tooltip: 'Muat ulang',
              onPressed: _loading ? null : _load,
              icon: const Icon(Icons.refresh),
            ),
          ],
        ),
        // Tombol kembali mengembalikan `true` bila ada baris yang berubah, agar
        // dashboard bisa menyegarkan saldo/daftar transaksi.
        body: SafeArea(child: _buildBody()),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) return const Center(child: CircularProgressIndicator());

    if (_error != null) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.cloud_off_outlined,
              size: 48,
              color: Theme.of(context).colorScheme.error,
            ),
            const SizedBox(height: 12),
            Text(_error!, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: _load,
              icon: const Icon(Icons.refresh),
              label: const Text('Coba Lagi'),
            ),
          ],
        ),
      );
    }

    if (_items.isEmpty) {
      return Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.task_alt,
              size: 48,
              color: Theme.of(context).colorScheme.primary,
            ),
            const SizedBox(height: 12),
            Text(
              'Tidak ada transaksi pending',
              style: Theme.of(context).textTheme.titleMedium,
              textAlign: TextAlign.center,
            ),
            const SizedBox(height: 8),
            Text(
              'Semua baris mutasi yang terbaca sudah dikonfirmasi. '
              'Unggah mutasi baru dari Dashboard → Matching Mutasi.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodySmall,
            ),
          ],
        ),
      );
    }

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
          child: Row(
            children: [
              Expanded(
                child: Text(
                  '${_items.length} baris menunggu konfirmasi',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
              ),
              const SizedBox(width: 8),
              // Ikon centang = tombol "konfirmasikan semua" (bukan sekadar
              // hiasan/tombol kembali — kembali ada di AppBar).
              FilledButton.icon(
                onPressed: _confirmingAll ? null : _confirmAll,
                icon: const Icon(Icons.done_all),
                label: Text(
                  _confirmingAll ? 'Mengonfirmasi…' : 'Konfirmasi Semua',
                ),
              ),
            ],
          ),
        ),
        if (_confirmingAll)
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                LinearProgressIndicator(
                  value: _confirmTotal == 0
                      ? null
                      : _confirmProgress / _confirmTotal,
                ),
                const SizedBox(height: 4),
                Text(
                  'Mengonfirmasi $_confirmProgress dari $_confirmTotal baris…',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
            ),
          ),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16),
          child: Text(
            'Baris berikut belum balance dengan transaksi mana pun. '
            'Konfirmasi untuk menyimpannya sebagai transaksi, atau batalkan '
            'agar baris ini dibuang.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ),
        const SizedBox(height: 8),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.fromLTRB(16, 8, 16, 24),
            itemCount: _items.length,
            itemBuilder: (context, index) => _pendingCard(_items[index]),
          ),
        ),
      ],
    );
  }

  Widget _pendingCard(PendingTransactionModel item) {
    // Saat "Konfirmasi Semua" berjalan, tombol per baris disembunyikan agar
    // tidak ada permintaan ganda ke baris yang sama.
    final busy = _confirmingAll || _busy.contains(item.id);
    final scheme = Theme.of(context).colorScheme;
    final directionColor = item.isExpense ? Colors.red : Colors.green;
    final details = <String>[
      if (item.categoryName != null) item.categoryName!,
      if (item.accountName != null) item.accountName!,
    ];

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Icon(
                  item.isExpense ? Icons.arrow_upward : Icons.arrow_downward,
                  color: directionColor,
                ),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    item.label,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                    style: const TextStyle(fontWeight: FontWeight.w600),
                  ),
                ),
                const SizedBox(width: 8),
                Text(
                  formatRupiah(item.totalAmount),
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
              ],
            ),
            if (item.note != null && item.note!.trim().isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4, left: 32),
                child: Text(
                  item.note!,
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ),
            Padding(
              padding: const EdgeInsets.only(top: 4, left: 32),
              child: Text(
                [
                  item.isExpense ? 'Dana keluar' : 'Dana masuk',
                  if (details.isNotEmpty) details.join(' · '),
                ].join(' · '),
                style: Theme.of(context).textTheme.labelSmall,
              ),
            ),
            if (item.transactionDate != null)
              Padding(
                padding: const EdgeInsets.only(top: 2, left: 32),
                child: Text(
                  // Tanggal+jam ASLI dari mutasi bank — inilah yang akan
                  // tersimpan sebagai waktu transaksi, bukan waktu konfirmasi.
                  'Tanggal transaksi: '
                  '${formatDateDetail(item.transactionDate!)} '
                  '${formatClock(item.transactionDate!)}',
                  style: Theme.of(context).textTheme.labelSmall,
                ),
              ),
            const SizedBox(height: 8),
            if (busy)
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 8),
                child: LinearProgressIndicator(),
              )
            else
              Row(
                mainAxisAlignment: MainAxisAlignment.end,
                children: [
                  TextButton.icon(
                    onPressed: () => _cancel(item),
                    icon: Icon(Icons.delete_outline, color: scheme.error),
                    label: Text(
                      'Batalkan',
                      style: TextStyle(color: scheme.error),
                    ),
                  ),
                  const SizedBox(width: 8),
                  FilledButton.icon(
                    onPressed: () => _confirm(item),
                    icon: const Icon(Icons.check),
                    label: const Text('Konfirmasi'),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}
