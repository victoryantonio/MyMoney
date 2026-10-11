/// Setelan profil user dari `GET/PATCH /api/profile` (Req 5).
///
/// `timezone` adalah preferensi IANA timezone user (mis. 'Asia/Jakarta').
/// `timezoneConfirmed` false → aplikasi menampilkan form pilih timezone
/// sekali di awal (nilai awal = timezone perangkat).
class ProfileSettings {
  const ProfileSettings({
    required this.timezone,
    required this.timezoneConfirmed,
    this.displayName,
  });

  final String timezone;
  final bool timezoneConfirmed;
  final String? displayName;

  factory ProfileSettings.fromJson(Map<String, dynamic> json) =>
      ProfileSettings(
        timezone: json['timezone'] as String? ?? 'Asia/Jakarta',
        timezoneConfirmed: json['timezone_confirmed'] as bool? ?? false,
        displayName: json['display_name'] as String?,
      );

  ProfileSettings copyWith({
    String? timezone,
    bool? timezoneConfirmed,
    String? displayName,
  }) => ProfileSettings(
    timezone: timezone ?? this.timezone,
    timezoneConfirmed: timezoneConfirmed ?? this.timezoneConfirmed,
    displayName: displayName ?? this.displayName,
  );
}
