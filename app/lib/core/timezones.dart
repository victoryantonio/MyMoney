/// Utilitas timezone (Req 5).
///
/// Storage SELALU UTC (`transaction_date` = timestamptz). Yang disimpan sebagai
/// "interpretasi" adalah NAMA timezone per-transaksi (`transactions.timezone`),
/// di-snapshot saat transaksi dibuat — jadi mengganti setelan timezone tidak
/// menggeser tanggal transaksi lama.
///
/// Flutter core tidak mengekspos identifier IANA perangkat, jadi default
/// timezone diperkirakan dari offset UTC sekarang + kode negara perangkat.
library;

import 'dart:ui';

import 'package:timezone/data/latest.dart' as tzdata;
import 'package:timezone/timezone.dart' as tz;

/// Nilai default kolom `profiles.timezone` (sinkron dengan backend).
const String fallbackTimezone = 'Asia/Jakarta';

bool _initialized = false;

/// Muat database IANA sekali di startup (idempoten).
void initializeTimezoneDatabase() {
  if (_initialized) return;
  tzdata.initializeTimeZones();
  _initialized = true;
}

/// Instant UTC → wall-clock di [timezoneName].
///
/// Nama kosong/tidak dikenal → `fallbackTimezone`, lalu terakhir offset
/// perangkat, supaya tampilan tetap masuk akal.
DateTime inTimezone(DateTime instant, String? timezoneName) {
  initializeTimezoneDatabase();
  final utc = instant.toUtc();
  for (final name in [timezoneName, fallbackTimezone]) {
    if (name == null || name.isEmpty) continue;
    final location = tz.timeZoneDatabase.locations[name];
    if (location != null) return tz.TZDateTime.from(utc, location);
  }
  return instant.toLocal();
}

/// Apakah [timezoneName] nama IANA yang dikenal?
bool isKnownTimezone(String timezoneName) {
  initializeTimezoneDatabase();
  return tz.timeZoneDatabase.locations.containsKey(timezoneName);
}

/// Semua nama timezone IANA, terurut — untuk picker yang bisa dicari.
List<String> allTimezoneNames() {
  initializeTimezoneDatabase();
  final names = tz.timeZoneDatabase.locations.keys
      .where((n) => n.contains('/') || n == 'UTC')
      .toList()
    ..sort();
  return names;
}

/// Label ringkas: `Asia/Jakarta (UTC+07:00)`.
String timezoneLabel(String timezoneName) {
  initializeTimezoneDatabase();
  final location = tz.timeZoneDatabase.locations[timezoneName];
  if (location == null) return timezoneName;
  final offset = tz.TZDateTime.now(location).timeZoneOffset;
  final sign = offset.isNegative ? '-' : '+';
  final abs = offset.abs();
  final hh = abs.inHours.toString().padLeft(2, '0');
  final mm = (abs.inMinutes % 60).toString().padLeft(2, '0');
  return '$timezoneName (UTC$sign$hh:$mm)';
}

/// Perkiraan nama timezone perangkat (default saat onboarding).
///
/// Tidak ada API Flutter resmi yang memberi identifier IANA, jadi:
///   1. offset UTC sekarang dicocokkan dengan kandidat negara perangkat,
///   2. lalu dengan daftar umum,
///   3. terakhir dengan seluruh database.
/// User selalu bisa menggantinya di menu Profile.
String guessDeviceTimezoneName() {
  initializeTimezoneDatabase();
  final utcNow = DateTime.now().toUtc();
  final offset = DateTime.now().timeZoneOffset;
  final country = _deviceCountryCode();

  for (final name in [...?_byCountry[country], ..._genericOrder]) {
    final location = tz.timeZoneDatabase.locations[name];
    if (location == null) continue;
    if (tz.TZDateTime.from(utcNow, location).timeZoneOffset == offset) return name;
  }
  for (final entry in tz.timeZoneDatabase.locations.entries) {
    if (tz.TZDateTime.from(utcNow, entry.value).timeZoneOffset == offset) {
      return entry.key;
    }
  }
  return fallbackTimezone;
}

String _deviceCountryCode() {
  try {
    final locale = PlatformDispatcher.instance.locale;
    return (locale.countryCode ?? '').toUpperCase();
  } catch (_) {
    return '';
  }
}

/// Kandidat per kode negara (ISO-3166 alpha-2) — supaya zona yang berbagi
/// offset sama (mis. WITA +8 vs Singapore +8) dipilih sesuai negara perangkat.
const _byCountry = <String, List<String>>{
  'ID': ['Asia/Jakarta', 'Asia/Pontianak', 'Asia/Makassar', 'Asia/Jayapura'],
  'SG': ['Asia/Singapore'],
  'MY': ['Asia/Kuala_Lumpur', 'Asia/Kuching'],
  'BN': ['Asia/Brunei'],
  'TH': ['Asia/Bangkok'],
  'VN': ['Asia/Ho_Chi_Minh'],
  'PH': ['Asia/Manila'],
  'IN': ['Asia/Kolkata'],
  'JP': ['Asia/Tokyo'],
  'KR': ['Asia/Seoul'],
  'CN': ['Asia/Shanghai', 'Asia/Urumqi'],
  'HK': ['Asia/Hong_Kong'],
  'TW': ['Asia/Taipei'],
  'AU': [
    'Australia/Perth',
    'Australia/Adelaide',
    'Australia/Darwin',
    'Australia/Brisbane',
    'Australia/Sydney',
    'Australia/Melbourne',
    'Australia/Hobart',
  ],
  'AE': ['Asia/Dubai'],
  'SA': ['Asia/Riyadh'],
  'EG': ['Africa/Cairo'],
  'ZA': ['Africa/Johannesburg'],
  'GB': ['Europe/London'],
  'NL': ['Europe/Amsterdam'],
  'DE': ['Europe/Berlin'],
  'FR': ['Europe/Paris'],
  'ES': ['Europe/Madrid'],
  'IT': ['Europe/Rome'],
  'TR': ['Europe/Istanbul'],
  'RU': ['Europe/Moscow', 'Asia/Novosibirsk', 'Asia/Vladivostok'],
  'US': [
    'America/New_York',
    'America/Chicago',
    'America/Denver',
    'America/Los_Angeles',
    'America/Anchorage',
    'Pacific/Honolulu',
  ],
  'CA': [
    'America/Toronto',
    'America/Vancouver',
    'America/Edmonton',
    'America/Winnipeg',
    'America/Halifax',
  ],
  'BR': ['America/Sao_Paulo', 'America/Manaus'],
  'MX': ['America/Mexico_City', 'America/Tijuana'],
  'NZ': ['Pacific/Auckland'],
};

/// Urutan umum saat kode negara tidak dikenali.
const _genericOrder = <String>[
  'Asia/Jakarta',
  'Asia/Makassar',
  'Asia/Jayapura',
  'Asia/Singapore',
  'Asia/Kuala_Lumpur',
  'Asia/Bangkok',
  'Asia/Manila',
  'Asia/Ho_Chi_Minh',
  'Asia/Shanghai',
  'Asia/Hong_Kong',
  'Asia/Taipei',
  'Asia/Seoul',
  'Asia/Tokyo',
  'Asia/Kolkata',
  'Asia/Dubai',
  'Australia/Perth',
  'Australia/Sydney',
  'Europe/London',
  'Europe/Amsterdam',
  'Europe/Berlin',
  'Europe/Paris',
  'Europe/Moscow',
  'America/New_York',
  'America/Chicago',
  'America/Denver',
  'America/Los_Angeles',
  'America/Sao_Paulo',
  'Africa/Cairo',
  'Africa/Johannesburg',
  'Pacific/Auckland',
  'UTC',
];
