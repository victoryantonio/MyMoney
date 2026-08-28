/// Screen "Scan Nota" (REQUIREMENTS US-07..US-10) — setara
/// `ReceiptCaptureScreen` v1 Kotlin, tapi OCR via backend (vision LLM
/// DeepSeek, `POST /api/receipts/ocr`) bukan ML Kit on-device —
/// konsisten dengan arsitektur: backend = single source of truth.
///
/// Flow: pilih sumber (kamera/galeri) → preview → proses OCR → form review
/// (merchant, tipe, tanggal, items, kategori, akun — bisa diedit, US-08) →
/// simpan via `POST /api/transactions`.
library;

import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../core/api_client.dart';
import '../models/transaction_models.dart';
import 'transaction_form_screen.dart';

/// Hasil pemilihan gambar (kamera/galeri) sebagai bytes siap upload.
class PickedReceiptImage {
  const PickedReceiptImage({required this.bytes, required this.name});

  final Uint8List bytes;
  final String name;
}

typedef ImagePickFn = Future<PickedReceiptImage?> Function(ImageSource source);

/// Implementasi default: kamera/galeri lewat `image_picker`.
Future<PickedReceiptImage?> _pickWithImagePicker(ImageSource source) async {
  final file = await ImagePicker().pickImage(
    source: source,
    imageQuality: 85,
    maxWidth: 1600,
  );
  if (file == null) return null;
  final bytes = await file.readAsBytes();
  return PickedReceiptImage(bytes: bytes, name: file.name);
}

enum _Stage { select, preview, review }

class ReceiptScreen extends StatefulWidget {
  const ReceiptScreen({super.key, required this.api, this.pickImage});

  final ApiClient api;

  /// Overridable untuk test; default = kamera/galeri asli.
  final ImagePickFn? pickImage;

  @override
  State<ReceiptScreen> createState() => _ReceiptScreenState();
}

class _ReceiptScreenState extends State<ReceiptScreen> {
  late final ImagePickFn _pickImage = widget.pickImage ?? _pickWithImagePicker;

  _Stage _stage = _Stage.select;
  Uint8List? _imageBytes;
  String _imageName = 'receipt.jpg';
  bool _processing = false;
  bool _saving = false;
  String? _error;

  // ── State form review (hasil OCR, bisa diedit) ────────────────────────────
  String _type = 'expense';
  String _merchant = '';
  DateTime _date = DateTime.now();
  final List<ReceiptItemModel> _items = [];
  final List<CategoryModel> _categories = [];
  final List<AccountModel> _accounts = [];
  String? _categoryId;
  String? _accountId;
  final bool _loadingOptions = false;
  String? _optionsError;

  double get _total => _items.fold(0, (sum, i) => sum + i.lineTotal);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Scan Nota')),
      body: SafeArea(
        child: switch (_stage) {
          _Stage.select => _buildSelect(),
          _Stage.preview => _buildPreview(),
          _Stage.review => _buildReview(),
        },
      ),
    );
  }

  // ── Stage 1: pilih sumber gambar ──────────────────────────────────────────

  Widget _buildSelect() {
    return Padding(
      padding: const EdgeInsets.all(24),
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Icon(
            Icons.receipt_long_outlined,
            size: 64,
            color: Theme.of(context).colorScheme.primary,
          ),
          const SizedBox(height: 16),
          Text(
            'Foto nota untuk dicatat otomatis',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.titleMedium,
          ),
          const SizedBox(height: 8),
          Text(
            'Ambil foto atau pilih dari galeri. Sistem akan membaca merchant, tanggal, dan rincian item — kamu bisa mengeditnya sebelum disimpan.',
            textAlign: TextAlign.center,
            style: Theme.of(context).textTheme.bodySmall,
          ),
          const SizedBox(height: 32),
          FilledButton.icon(
            onPressed: () => _pick(ImageSource.camera),
            icon: const Icon(Icons.camera_alt_outlined),
            label: const Text('Ambil Foto'),
          ),
          const SizedBox(height: 12),
          OutlinedButton.icon(
            onPressed: () => _pick(ImageSource.gallery),
            icon: const Icon(Icons.photo_library_outlined),
            label: const Text('Pilih dari Galeri'),
          ),
          if (_error != null) ...[
            const SizedBox(height: 16),
            _ErrorBanner(message: _error!),
          ],
        ],
      ),
    );
  }

  // ── Stage 2: preview + proses OCR ─────────────────────────────────────────

  Widget _buildPreview() {
    final bytes = _imageBytes;
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          Expanded(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(12),
              child: bytes == null
                  ? const Center(child: CircularProgressIndicator())
                  : Image.memory(bytes, fit: BoxFit.contain),
            ),
          ),
          const SizedBox(height: 16),
          if (_processing)
            const Center(child: CircularProgressIndicator())
          else ...[
            FilledButton.icon(
              onPressed: _runOcr,
              icon: const Icon(Icons.document_scanner_outlined),
              label: const Text('Proses OCR'),
            ),
            const SizedBox(height: 8),
            OutlinedButton.icon(
              onPressed: () => setState(() {
                _imageBytes = null;
                _stage = _Stage.select;
                _error = null;
              }),
              icon: const Icon(Icons.refresh),
              label: const Text('Ambil Ulang'),
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

  // ── Stage 3: review/edit hasil OCR ────────────────────────────────────────

  Widget _buildReview() {
    final categories = _categories.where((c) => c.type == _type && c.isActive);
    return Form(
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Detail Transaksi',
              style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 12),

          // Merchant
          TextFormField(
            decoration: const InputDecoration(
              labelText: 'Merchant / Toko',
              border: OutlineInputBorder(),
            ),
            initialValue: _merchant,
            onChanged: (v) => _merchant = v,
          ),
          const SizedBox(height: 12),

          // Tipe + tanggal
          Row(
            children: [
              Expanded(
                child: SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'expense', label: Text('Pengeluaran')),
                    ButtonSegment(value: 'income', label: Text('Pemasukan')),
                  ],
                  selected: {_type},
                  onSelectionChanged: (s) => _onTypeChanged(s.first),
                ),
              ),
              const SizedBox(width: 12),
              OutlinedButton.icon(
                onPressed: _pickDate,
                icon: const Icon(Icons.calendar_today_outlined, size: 18),
                label: Text(_formatDate(_date)),
              ),
            ],
          ),
          const SizedBox(height: 12),

          // Items
          Text('Items', style: Theme.of(context).textTheme.titleSmall),
          const SizedBox(height: 8),
          for (var i = 0; i < _items.length; i++) ...[
            _ItemEditorRow(
              key: ValueKey('item-$i'),
              item: _items[i],
              onChanged: () => setState(() {}),
              onRemove: () => setState(() => _items.removeAt(i)),
            ),
            const SizedBox(height: 8),
          ],
          OutlinedButton.icon(
            onPressed: () => setState(() {
              _items.add(ReceiptItemModel(name: '', qty: 1, price: 0));
            }),
            icon: const Icon(Icons.add),
            label: const Text('Tambah Item'),
          ),

          const SizedBox(height: 8),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Total', style: Theme.of(context).textTheme.titleMedium),
              Text(
                _formatMoney(_total),
                style: Theme.of(context).textTheme.titleMedium?.copyWith(
                      color: Theme.of(context).colorScheme.primary,
                      fontWeight: FontWeight.bold,
                    ),
              ),
            ],
          ),
          const SizedBox(height: 16),

          // Kategori & akun
          if (_loadingOptions)
            const Center(child: CircularProgressIndicator())
          else if (_optionsError != null)
            _ErrorBanner(message: _optionsError!)
          else ...[
            DropdownButtonFormField<String>(
              key: const ValueKey('category'),
              initialValue: _categoryId,
              decoration: const InputDecoration(
                labelText: 'Kategori',
                border: OutlineInputBorder(),
              ),
              items: [
                for (final c in categories)
                  DropdownMenuItem(value: c.id, child: Text(c.name)),
              ],
              onChanged: (v) => setState(() => _categoryId = v),
            ),
            const SizedBox(height: 12),
            DropdownButtonFormField<String>(
              key: const ValueKey('account'),
              initialValue: _accountId,
              decoration: const InputDecoration(
                labelText: 'Akun',
                border: OutlineInputBorder(),
              ),
              items: [
                for (final a in _accounts.where((a) => a.isActive))
                  DropdownMenuItem(value: a.id, child: Text(a.label)),
              ],
              onChanged: (v) => setState(() => _accountId = v),
            ),
            const SizedBox(height: 20),
            FilledButton.icon(
              onPressed: _saving ? null : _save,
              icon: const Icon(Icons.save_outlined),
              label: Text(_saving ? 'Menyimpan…' : 'Simpan Transaksi'),
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

  // ── Aksi ──────────────────────────────────────────────────────────────────

  Future<void> _pick(ImageSource source) async {
    setState(() => _error = null);
    try {
      final picked = await _pickImage(source);
      if (picked == null || !mounted) return;
      setState(() {
        _imageBytes = picked.bytes;
        _imageName = picked.name;
        _stage = _Stage.preview;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() => _error = 'Tidak dapat membuka kamera/galeri. Coba lagi.');
    }
  }

  Future<void> _runOcr() async {
    final bytes = _imageBytes;
    if (bytes == null) return;
    setState(() {
      _processing = true;
      _error = null;
    });
    try {
      final parsed = await widget.api.parseReceipt(bytes, _imageName);
      if (!mounted) return;
      Navigator.of(context).pushReplacement(
        MaterialPageRoute<void>(
          builder: (_) => TransactionFormScreen(
            api: widget.api,
            initialType: parsed.type,
            initialMerchant: parsed.merchant,
            initialDate: DateTime.tryParse(parsed.date ?? ''),
            initialItems: parsed.items,
          ),
        ),
      );
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _processing = false;
        _error = e.message;
      });
    }
  }

  String? _matchCategory(String? name, List<CategoryModel> categories) {
    final active = categories.where((c) => c.isActive && c.type == _type);
    if (name != null && name.isNotEmpty) {
      final n = name.toLowerCase();
      for (final c in active) {
        if (c.name.toLowerCase() == n) return c.id;
      }
    }
    // Fallback: kategori default global, lalu kategori aktif pertama.
    for (final c in active) {
      if (c.isDefault) return c.id;
    }
    return active.isEmpty ? null : active.first.id;
  }

  void _onTypeChanged(String type) {
    setState(() {
      _type = type;
      // Pilih ulang kategori yang cocok dengan tipe baru.
      _categoryId = _matchCategory(null, _categories);
    });
  }

  Future<void> _pickDate() async {
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: DateTime(2000),
      lastDate: DateTime.now().add(const Duration(days: 1)),
    );
    if (picked != null) setState(() => _date = picked);
  }

  Future<void> _save() async {
    final validItems = _items.where((i) => i.name.trim().isNotEmpty && i.price > 0).toList();
    if (validItems.isEmpty) {
      setState(() => _error = 'Minimal satu item dengan nama dan harga valid.');
      return;
    }
    if (_categoryId == null || _accountId == null) {
      setState(() => _error = 'Pilih kategori dan akun terlebih dahulu.');
      return;
    }
    setState(() {
      _saving = true;
      _error = null;
    });
    try {
      await widget.api.createTransaction(
        type: _type,
        totalAmount: _total,
        categoryId: _categoryId!,
        accountId: _accountId!,
        merchant: _merchant.trim().isEmpty ? null : _merchant.trim(),
        transactionDate: _date,
        items: validItems,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Transaksi berhasil disimpan.')),
      );
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _saving = false;
        _error = e.message;
      });
    }
  }

  String _formatMoney(double v) {
    final s = v.toStringAsFixed(0).replaceAllMapped(
          RegExp(r'(\d)(?=(\d{3})+$)'),
          (m) => '${m[1]}.',
        );
    return 'Rp$s';
  }

  String _formatDate(DateTime d) {
    const months = [
      'Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun',
      'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des',
    ];
    return '${d.day} ${months[d.month - 1]} ${d.year}';
  }
}

/// Baris item yang bisa diedit: nama, qty, harga satuan, dan tombol hapus.
class _ItemEditorRow extends StatefulWidget {
  const _ItemEditorRow({
    super.key,
    required this.item,
    required this.onChanged,
    required this.onRemove,
  });

  final ReceiptItemModel item;
  final VoidCallback onChanged;
  final VoidCallback onRemove;

  @override
  State<_ItemEditorRow> createState() => _ItemEditorRowState();
}

class _ItemEditorRowState extends State<_ItemEditorRow> {
  late final TextEditingController _name =
      TextEditingController(text: widget.item.name);
  late final TextEditingController _qty =
      TextEditingController(text: _num(widget.item.qty));
  late final TextEditingController _price =
      TextEditingController(text: _num(widget.item.price));

  static String _num(double v) =>
      v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toString();

  @override
  void dispose() {
    _name.dispose();
    _qty.dispose();
    _price.dispose();
    super.dispose();
  }

  void _update() {
    widget.item.lineTotalOverride = null;
    widget.item.name = _name.text.trim();
    widget.item.qty = double.tryParse(_qty.text.replaceAll(',', '.')) ?? 0;
    widget.item.price = double.tryParse(_price.text.replaceAll(',', '.')) ?? 0;
    widget.onChanged();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Expanded(
          flex: 3,
          child: TextField(
            controller: _name,
            decoration: const InputDecoration(
              labelText: 'Nama item',
              border: OutlineInputBorder(),
              isDense: true,
            ),
            onChanged: (_) => _update(),
          ),
        ),
        const SizedBox(width: 8),
        SizedBox(
          width: 64,
          child: TextField(
            controller: _qty,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Qty',
              border: OutlineInputBorder(),
              isDense: true,
            ),
            onChanged: (_) => _update(),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          flex: 2,
          child: TextField(
            controller: _price,
            keyboardType: TextInputType.number,
            decoration: const InputDecoration(
              labelText: 'Harga',
              border: OutlineInputBorder(),
              isDense: true,
            ),
            onChanged: (_) => _update(),
          ),
        ),
        IconButton(
          tooltip: 'Hapus item',
          onPressed: widget.onRemove,
          icon: const Icon(Icons.delete_outline),
        ),
      ],
    );
  }
}

class _ErrorBanner extends StatelessWidget {
  const _ErrorBanner({required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: Theme.of(context).colorScheme.errorContainer,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          Icon(Icons.error_outline,
              color: Theme.of(context).colorScheme.onErrorContainer),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              message,
              style: TextStyle(
                color: Theme.of(context).colorScheme.onErrorContainer,
              ),
            ),
          ),
        ],
      ),
    );
  }
}
