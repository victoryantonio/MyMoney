/// Picker zona waktu (Req 5) — bottom sheet dengan pencarian.
///
/// Dipakai di form onboarding (pilihan pertama saat login) dan di menu
/// Profil (ubah kapan saja). Daftar nama IANA diambil dari paket `timezone`.
library;

import 'package:flutter/material.dart';

import '../core/timezones.dart';

/// Tampilkan bottom sheet pilih zona waktu. Mengembalikan nama IANA yang
/// dipilih, atau null bila dibatalkan.
Future<String?> showTimezonePickerSheet(
  BuildContext context, {
  required String current,
}) {
  return showModalBottomSheet<String>(
    context: context,
    showDragHandle: true,
    isScrollControlled: true,
    builder: (context) => _TimezonePickerSheet(current: current),
  );
}

class _TimezonePickerSheet extends StatefulWidget {
  const _TimezonePickerSheet({required this.current});

  final String current;

  @override
  State<_TimezonePickerSheet> createState() => _TimezonePickerSheetState();
}

class _TimezonePickerSheetState extends State<_TimezonePickerSheet> {
  final _controller = TextEditingController();
  late List<String> _all;
  late List<String> _filtered;

  @override
  void initState() {
    super.initState();
    _all = allTimezoneNames();
    _filtered = _all;
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onSearch(String value) {
    final q = value.trim().toLowerCase();
    setState(() {
      _filtered = q.isEmpty
          ? _all
          : _all
              .where((name) =>
                  name.toLowerCase().contains(q) ||
                  timezoneLabel(name).toLowerCase().contains(q))
              .toList();
    });
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final height = MediaQuery.of(context).size.height * 0.8;
    return SafeArea(
      child: SizedBox(
        height: height,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              child: Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  'Pilih Zona Waktu',
                  style: theme.textTheme.titleMedium
                      ?.copyWith(fontWeight: FontWeight.w700),
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 16),
              child: TextField(
                controller: _controller,
                autofocus: false,
                onChanged: _onSearch,
                decoration: const InputDecoration(
                  hintText: 'Cari kota atau negara…',
                  prefixIcon: Icon(Icons.search),
                  border: OutlineInputBorder(),
                  isDense: true,
                ),
              ),
            ),
            const SizedBox(height: 8),
            Expanded(
              child: _filtered.isEmpty
                  ? const Center(child: Text('Tidak ada zona waktu cocok.'))
                  : ListView.builder(
                      itemCount: _filtered.length,
                      itemBuilder: (context, index) {
                        final name = _filtered[index];
                        final selected = name == widget.current;
                        return ListTile(
                          dense: true,
                          title: Text(name),
                          subtitle: Text(_offsetText(name)),
                          trailing: selected
                              ? Icon(Icons.check_circle,
                                  color: theme.colorScheme.primary)
                              : null,
                          onTap: () => Navigator.of(context).pop(name),
                        );
                      },
                    ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Hanya bagian offset-nya: `UTC+07:00` (nama sudah jadi judul baris).
String _offsetText(String name) {
  final label = timezoneLabel(name);
  final start = label.indexOf(' (');
  return start == -1 ? label : label.substring(start + 2, label.length - 1);
}
