/// Form transaksi manual (tambah & edit) — setara v1 Kotlin
/// `TransactionFormScreen`. Juga dipakai dari dashboard saat tap transaksi
/// terbaru. Kembali dengan `Navigator.pop(true)` bila ada perubahan.
///
/// Mode edit: `transaction != null` → prefill semua field + PUT di save.
/// Items opsional: saat ada item, total otomatis = Σ(qty × price).
library;

import 'package:flutter/material.dart';

import '../core/api_client.dart';
import '../core/format.dart';
import '../models/transaction_models.dart';

class TransactionFormScreen extends StatefulWidget {
  const TransactionFormScreen({
    super.key,
    required this.api,
    this.transaction,
  });

  final ApiClient api;

  /// Saat diisi → mode edit (PUT). Jika null → mode tambah (POST).
  final TransactionModel? transaction;

  @override
  State<TransactionFormScreen> createState() => _TransactionFormScreenState();
}

class _TransactionFormScreenState extends State<TransactionFormScreen> {
  final _formKey = GlobalKey<FormState>();

  late final bool _isEdit = widget.transaction != null;

  String _type = 'expense';
  late final TextEditingController _amountCtrl;
  late final TextEditingController _merchantCtrl;
  late final TextEditingController _noteCtrl;
  DateTime _date = DateTime.now();

  final List<ReceiptItemModel> _items = [];
  List<CategoryModel> _categories = [];
  List<AccountModel> _accounts = [];

  String? _categoryId;
  String? _accountId;
  bool _loadingOptions = true;
  String? _optionsError;
  bool _saving = false;

  double get _itemsTotal => _items.fold(0, (sum, i) => sum + i.lineTotal);

  bool get _amountFromItems => _items.isNotEmpty;

  @override
  void initState() {
    super.initState();
    final tx = widget.transaction;
    _type = tx?.type ?? 'expense';
    _amountCtrl = TextEditingController(text: tx == null ? '' : _fmt(tx.totalAmount));
    _merchantCtrl = TextEditingController(text: tx?.merchant ?? '');
    _noteCtrl = TextEditingController(text: tx?.note ?? '');
    _date = tx?.transactionDate ?? DateTime.now();
    _categoryId = tx?.categoryId;
    _accountId = tx?.accountId;
    if (tx != null) {
      _items.addAll(
        tx.items
            .map(
              (i) => ReceiptItemModel(name: i.name, qty: i.qty, price: i.price),
            )
            .toList(),
      );
    }
    _loadOptions();
  }

  String _fmt(double v) =>
      v == v.roundToDouble() ? v.toStringAsFixed(0) : v.toStringAsFixed(2);

  @override
  void dispose() {
    _amountCtrl.dispose();
    _merchantCtrl.dispose();
    _noteCtrl.dispose();
    super.dispose();
  }

  Future<void> _loadOptions() async {
    setState(() {
      _loadingOptions = true;
      _optionsError = null;
    });
    try {
      final categories = await widget.api.fetchCategories(type: _type);
      final accounts = await widget.api.fetchAccounts();
      if (!mounted) return;
      setState(() {
        _categories = categories;
        _accounts = accounts;
        _loadingOptions = false;
      });
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() {
        _optionsError = e.message;
        _loadingOptions = false;
      });
    }
  }

  void _changeType(String type) {
    if (type == _type) return;
    setState(() {
      _type = type;
      _categoryId = null; // kategori beda tipe — reset pilihan
    });
    _loadOptions();
  }

  void _syncAmountFromItems() {
    if (_items.isNotEmpty) {
      _amountCtrl.text = _fmt(_itemsTotal);
    }
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

  void _addItem() {
    final item = ReceiptItemModel(name: '', qty: 1, price: 0);
    _editItem(item, isNew: true);
  }

  Future<void> _editItem(ReceiptItemModel item, {required bool isNew}) async {
    final nameCtrl = TextEditingController(text: item.name);
    final qtyCtrl = TextEditingController(text: _fmt(item.qty));
    final priceCtrl = TextEditingController(text: _fmt(item.price));
    final formKey = GlobalKey<FormState>();

    final saved = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(isNew ? 'Tambah item' : 'Edit item'),
        content: Form(
          key: formKey,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextFormField(
                controller: nameCtrl,
                decoration: const InputDecoration(labelText: 'Nama item'),
                validator: (v) => (v == null || v.trim().isEmpty)
                    ? 'Nama item wajib diisi'
                    : null,
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: qtyCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Jumlah (qty)'),
                validator: (v) {
                  final n = double.tryParse(v ?? '');
                  if (n == null || n <= 0) return 'Jumlah harus > 0';
                  return null;
                },
              ),
              const SizedBox(height: 12),
              TextFormField(
                controller: priceCtrl,
                keyboardType: TextInputType.number,
                decoration: const InputDecoration(labelText: 'Harga satuan'),
                validator: (v) {
                  final n = double.tryParse(v ?? '');
                  if (n == null || n < 0) return 'Harga tidak valid';
                  return null;
                },
              ),
            ],
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(context).pop(false),
            child: const Text('Batal'),
          ),
          FilledButton(
            onPressed: () {
              if (formKey.currentState!.validate()) {
                item
                  ..name = nameCtrl.text.trim()
                  ..qty = double.parse(qtyCtrl.text)
                  ..price = double.parse(priceCtrl.text);
                Navigator.of(context).pop(true);
              }
            },
            child: const Text('Simpan'),
          ),
        ],
      ),
    );

    if (saved == true) {
      setState(() {
        if (isNew) _items.add(item);
        _syncAmountFromItems();
      });
    }
  }

  Future<void> _removeItem(ReceiptItemModel item) async {
    setState(() => _items.remove(item));
    _syncAmountFromItems();
  }

  Future<void> _save() async {
    if (!_formKey.currentState!.validate()) return;
    final amount = double.tryParse(_amountCtrl.text.replaceAll('.', '')) ?? 0;
    if (amount <= 0) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Nominal harus lebih dari 0')),
      );
      return;
    }
    if (_categoryId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Pilih kategori terlebih dahulu')),
      );
      return;
    }
    if (_accountId == null) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(content: Text('Pilih akun terlebih dahulu')),
      );
      return;
    }

    setState(() => _saving = true);
    try {
      final merchant = _merchantCtrl.text.trim();
      final note = _noteCtrl.text.trim();
      if (_isEdit) {
        await widget.api.updateTransaction(
          widget.transaction!.id,
          type: _type,
          totalAmount: amount,
          categoryId: _categoryId,
          accountId: _accountId,
          merchant: merchant.isEmpty ? null : merchant,
          note: note.isEmpty ? null : note,
          transactionDate: _date,
          items: _items.map((i) => i).toList(),
        );
      } else {
        await widget.api.createTransaction(
          type: _type,
          totalAmount: amount,
          categoryId: _categoryId!,
          accountId: _accountId!,
          merchant: merchant.isEmpty ? null : merchant,
          note: note.isEmpty ? null : note,
          transactionDate: _date,
          items: _items.map((i) => i).toList(),
        );
      }
      if (!mounted) return;
      Navigator.of(context).pop(true);
    } on ApiException catch (e) {
      if (!mounted) return;
      setState(() => _saving = false);
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.message)),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final categories = _categories
        .where((c) => c.type == _type)
        .where((c) => c.isActive)
        .toList();
    final accounts = _accounts.where((a) => a.isActive).toList();
    final categoryValid = categories.any((c) => c.id == _categoryId);
    final accountValid = accounts.any((a) => a.id == _accountId);

    return Scaffold(
      appBar: AppBar(
        title: Text(_isEdit ? 'Edit Transaksi' : 'Transaksi Baru'),
        actions: [
          IconButton(
            tooltip: 'Simpan',
            onPressed: _saving ? null : _save,
            icon: _saving
                ? const SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(strokeWidth: 2),
                  )
                : const Icon(Icons.check),
          ),
        ],
      ),
      body: SafeArea(
        child: Form(
          key: _formKey,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              // ── Tipe ───────────────────────────────────────────────────────
              SegmentedButton<String>(
                segments: const [
                  ButtonSegment(
                    value: 'expense',
                    label: Text('Pengeluaran'),
                    icon: Icon(Icons.arrow_downward),
                  ),
                  ButtonSegment(
                    value: 'income',
                    label: Text('Pemasukan'),
                    icon: Icon(Icons.arrow_upward),
                  ),
                ],
                selected: {_type},
                onSelectionChanged: _saving
                    ? null
                    : (s) => _changeType(s.first),
              ),
              const SizedBox(height: 16),

              // ── Nominal ────────────────────────────────────────────────────
              TextFormField(
                controller: _amountCtrl,
                enabled: !_amountFromItems,
                keyboardType: const TextInputType.numberWithOptions(
                  decimal: true,
                ),
                decoration: InputDecoration(
                  labelText: 'Nominal',
                  prefixText: 'Rp ',
                  helperText: _amountFromItems
                      ? 'Otomatis dari total item'
                      : null,
                  border: const OutlineInputBorder(),
                ),
                validator: (v) {
                  if (_amountFromItems) return null;
                  final n = double.tryParse((v ?? '').replaceAll('.', ''));
                  if (n == null || n <= 0) return 'Nominal harus lebih dari 0';
                  return null;
                },
              ),
              const SizedBox(height: 16),

              // ── Kategori & akun ────────────────────────────────────────────
              if (_loadingOptions)
                const Padding(
                  padding: EdgeInsets.symmetric(vertical: 12),
                  child: Center(child: CircularProgressIndicator()),
                )
              else if (_optionsError != null)
                Column(
                  children: [
                    Text(
                      _optionsError!,
                      style: TextStyle(color: theme.colorScheme.error),
                    ),
                    TextButton(
                      onPressed: _loadOptions,
                      child: const Text('Coba lagi'),
                    ),
                  ],
                )
              else ...[
                DropdownButtonFormField<String>(
                  initialValue:
                      categoryValid ? _categoryId : null,
                  decoration: const InputDecoration(
                    labelText: 'Kategori',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    for (final c in categories)
                      DropdownMenuItem(value: c.id, child: Text(c.name)),
                  ],
                  onChanged: _saving
                      ? null
                      : (v) => setState(() => _categoryId = v),
                ),
                if (_categoryId != null && !categoryValid)
                  Padding(
                    padding: const EdgeInsets.only(top: 4),
                    child: Text(
                      'Kategori sebelumnya tidak tersedia — pilih kategori lain.',
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: theme.colorScheme.error,
                      ),
                    ),
                  ),
                const SizedBox(height: 16),
                DropdownButtonFormField<String>(
                  initialValue: accountValid ? _accountId : null,
                  decoration: const InputDecoration(
                    labelText: 'Akun',
                    border: OutlineInputBorder(),
                  ),
                  items: [
                    for (final a in accounts)
                      DropdownMenuItem(value: a.id, child: Text(a.label)),
                  ],
                  onChanged:
                      _saving ? null : (v) => setState(() => _accountId = v),
                ),
              ],
              const SizedBox(height: 16),

              // ── Merchant, tanggal, catatan ─────────────────────────────────
              TextFormField(
                controller: _merchantCtrl,
                decoration: const InputDecoration(
                  labelText: 'Merchant / keterangan',
                  border: OutlineInputBorder(),
                ),
              ),
              const SizedBox(height: 16),
              InkWell(
                onTap: _pickDate,
                borderRadius: BorderRadius.circular(4),
                child: InputDecorator(
                  decoration: const InputDecoration(
                    labelText: 'Tanggal',
                    border: OutlineInputBorder(),
                    suffixIcon: Icon(Icons.calendar_today_outlined),
                  ),
                  child: Text(formatDateDetail(_date)),
                ),
              ),
              const SizedBox(height: 16),
              TextFormField(
                controller: _noteCtrl,
                maxLines: 3,
                decoration: const InputDecoration(
                  labelText: 'Catatan (opsional)',
                  border: OutlineInputBorder(),
                  alignLabelWithHint: true,
                ),
              ),
              const SizedBox(height: 24),

              // ── Items editor (opsional) ────────────────────────────────────
              Row(
                children: [
                  Text(
                    'Items',
                    style: theme.textTheme.titleSmall
                        ?.copyWith(fontWeight: FontWeight.w700),
                  ),
                  const Spacer(),
                  TextButton.icon(
                    onPressed: _saving ? null : _addItem,
                    icon: const Icon(Icons.add, size: 18),
                    label: const Text('Tambah item'),
                  ),
                ],
              ),
              if (_items.isEmpty)
                Text(
                  'Opsional — gunakan untuk nota beritem. Total otomatis dihitung.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurfaceVariant,
                  ),
                )
              else
                Card(
                  margin: EdgeInsets.zero,
                  elevation: 0,
                  shape: RoundedRectangleBorder(
                    borderRadius: BorderRadius.circular(12),
                    side: BorderSide(color: theme.colorScheme.outlineVariant),
                  ),
                  child: Column(
                    children: [
                      for (final item in _items)
                        ListTile(
                          dense: true,
                          title: Text(item.name),
                          subtitle: Text(
                            '${_fmt(item.qty)} × ${formatRupiah(item.price)}',
                          ),
                          trailing: Row(
                            mainAxisSize: MainAxisSize.min,
                            children: [
                              Text(
                                formatRupiah(item.lineTotal),
                                style: const TextStyle(
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                              IconButton(
                                icon: const Icon(Icons.edit_outlined, size: 18),
                                onPressed: _saving
                                    ? null
                                    : () => _editItem(item, isNew: false),
                              ),
                              IconButton(
                                icon: const Icon(Icons.delete_outline, size: 18),
                                onPressed:
                                    _saving ? null : () => _removeItem(item),
                              ),
                            ],
                          ),
                        ),
                      const Divider(height: 1),
                      ListTile(
                        dense: true,
                        title: const Text(
                          'Total',
                          style: TextStyle(fontWeight: FontWeight.w700),
                        ),
                        trailing: Text(
                          formatRupiah(_itemsTotal),
                          style: const TextStyle(fontWeight: FontWeight.w800),
                        ),
                      ),
                    ],
                  ),
                ),
              const SizedBox(height: 24),

              FilledButton.icon(
                onPressed: _saving ? null : _save,
                icon: const Icon(Icons.save_outlined),
                label: Text(_isEdit ? 'Simpan Perubahan' : 'Simpan Transaksi'),
              ),
              const SizedBox(height: 16),
            ],
          ),
        ),
      ),
    );
  }
}
