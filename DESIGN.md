# DESIGN.md — MyMoney (UI/UX)

## 1. Prinsip Desain

MyMoney bergeser dari arah "hangat-personal" ke **tenang-profesional** — mendekati bahasa visual institusi finansial tepercaya (bank, aplikasi investasi), tapi tetap menghindari pola generic yang membuat aplikasi finance terasa seperti template (lihat §2, checklist tidak berubah, tetap wajib).

1. **Tenang, bukan mencolok.** (tidak berubah)
2. **Angka adalah bintang utama.** (tidak berubah)
3. **Kepercayaan lewat kejelasan, bukan dekorasi.** Kesan profesional dibangun dari konsistensi visual dan kejelasan informasi — bukan ornamen atau ilustrasi yang berusaha terlihat "canggih".

## 2. Anti-Pattern Checklist — "AI Slop" yang WAJIB Dihindari

Checklist ini dipakai setiap kali review desain baru, sebelum di-approve:

- [ ] **Tidak ada gradient ungu-biru default** (`#6366F1 → #8B5CF6` dan variasinya) — ini warna paling sering muncul dari tool generatif AI karena "statistically safe", bukan karena cocok dengan brand.
- [ ] **Tidak ada emoji menggantikan icon system** (🚀💰📊 ditempel di header/tombol). Icon pakai Material Symbols yang konsisten, bukan emoji.
- [ ] **Tidak ada glassmorphism/blur dekoratif tanpa fungsi.** Blur hanya dipakai kalau ada alasan fungsional (misal modal overlay), bukan sebagai gaya visual kosong.
- [ ] **Tidak ada shadow besar + rounded-corner ekstrem di semua elemen tanpa hierarki.** Elevation dipakai terarah (lihat §5), bukan ditempel merata.
- [ ] **Tidak ada copy bergaya landing page marketing** ("Empower your financial journey! ✨"). Ini tool personal — copy harus terdengar seperti Anda bicara ke diri sendiri, bukan pitch produk.
- [ ] **Tidak pakai font default tanpa alasan** (Inter dipilih "karena semua orang pakai", tanpa pertimbangan karakter brand).
- [ ] **Tidak ada bento-grid dashboard yang dipaksakan** kalau data Anda tidak benar-benar butuh layout itu.

## 3. Palet Warna

Berdasarkan keputusan final: **dusty blue / slate blue** sebagai primary.
Dipilih karena asosiasi psikologis paling kuat untuk "tenang dan tepercaya"
(diverifikasi dari penelitian warna di konteks finansial), tapi dalam nuansa
desaturated/muted — bukan biru cerah saturated generic (#2563EB khas fintech app).

### Light Mode

| Token | Hex | Penggunaan |
|---|---|---|
| `surface` | `#F5F7FA` | Background utama — putih dengan hint biru sangat halus |
| `surface-variant` | `#E8EDF5` | Card, container sekunder |
| `on-surface` | `#1A2233` | Teks utama — biru-hitam gelap |
| `on-surface-variant` | `#556070` | Teks sekunder, caption |
| `primary` | `#3B5B8C` | Dusty slate blue — CTA, brand, navigasi aktif |
| `primary-container` | `#D0DCF0` | Background lembut elemen primary |
| `income` | `#3D7A5F` | Sage green — sengaja beda keluarga warna dari primary |
| `expense` | `#A8503C` | Clay/rust — tetap dipertahankan, hangat, tidak alarm |
| `outline` | `#D0D8E8` | Border, divider |

### Dark Mode

| Token | Hex | Penggunaan |
|---|---|---|
| `surface` | `#131B27` | Background utama — biru gelap pekat |
| `surface-variant` | `#1C2738` | Card, container sekunder |
| `on-surface` | `#E2E8F5` | Teks utama |
| `on-surface-variant` | `#A0ABBE` | Teks sekunder |
| `primary` | `#7B9ED4` | Slate blue terang untuk kontras dark mode |
| `primary-container` | `#243554` | Background elemen primary |
| `income` | `#6AAF8E` | Sage green versi terang |
| `expense` | `#D18871` | Rust versi terang |
| `outline` | `#2C3D57` | Border, divider |

### Jetpack Compose — color scheme update

\`\`\`kotlin
val MyMoneyLightColorScheme = lightColorScheme(
    primary = Color(0xFF3B5B8C),
    primaryContainer = Color(0xFFD0DCF0),
    surface = Color(0xFFF5F7FA),
    surfaceVariant = Color(0xFFE8EDF5),
    onSurface = Color(0xFF1A2233),
    onSurfaceVariant = Color(0xFF556070),
    outline = Color(0xFFD0D8E8)
)

val MyMoneyDarkColorScheme = darkColorScheme(
    primary = Color(0xFF7B9ED4),
    primaryContainer = Color(0xFF243554),
    surface = Color(0xFF131B27),
    surfaceVariant = Color(0xFF1C2738),
    onSurface = Color(0xFFE2E8F5),
    onSurfaceVariant = Color(0xFFA0ABBE),
    outline = Color(0xFF2C3D57)
)
\`\`\`

## 4. Tipografi

Hindari Inter sebagai pilihan default tanpa alasan (masuk anti-pattern §2). Kombinasi dua font dengan peran berbeda:

| Elemen | Font | Alasan |
|---|---|---|
| **Heading & label** | **Manrope** (Google Fonts, gratis) | Geometris tapi hangat, tidak se-"corporate" Inter, cocok untuk judul & navigasi |
| **Angka nominal** | **IBM Plex Mono** (tabular figures) | Monospace membuat angka rapi sejajar di list transaksi/laporan — penting untuk keterbacaan data finansial, dan memberi karakter "presisi" yang beda dari teks biasa |
| **Body text** | **Manrope** (regular) | Konsisten dengan heading, cukup satu keluarga font untuk teks + judul |

**Skala tipografi (mengikuti token MD3, disesuaikan):**
- Display (saldo total di beranda): 32sp, Manrope SemiBold
- Headline (judul halaman): 22sp, Manrope SemiBold
- Title (nama transaksi/akun): 16sp, Manrope Medium
- Body: 14sp, Manrope Regular
- Nominal uang (di semua konteks): IBM Plex Mono Medium, ukuran mengikuti konteks (20sp untuk saldo card, 14sp untuk list)

## 5. Elevation & Spacing

- **Elevation dipakai terbatas dan bermakna**: Level 0 (flat) untuk background, Level 1 untuk card transaksi biasa, Level 3 hanya untuk modal/bottom sheet konfirmasi (aksi penting seperti konfirmasi hasil parsing LLM). Tidak ada shadow dekoratif di elemen yang tidak butuh ditonjolkan.
- **Corner radius**: 12dp untuk card (bukan pill-shape ekstrem 24dp+ yang sering muncul di UI generic), 8dp untuk button, 100% (full round) hanya untuk avatar/icon button.
- **Spacing grid**: kelipatan 4dp (4/8/12/16/24/32), konsisten dengan token spacing MD3.

## 6. Iconography

- **Material Symbols** (outlined style, bukan filled) — konsisten dengan ekosistem Android, tidak perlu custom icon set yang menambah effort desain besar tanpa manfaat proporsional.
- Icon kategori transaksi (Makanan, Transport, dll) pakai Material Symbols yang relevan, **bukan emoji** — supaya konsisten di light/dark mode dan tidak terasa "playful berlebihan" untuk konteks finansial.

## 7. Voice & Microcopy

Karena ini personal tool, bukan produk SaaS:

| Konteks | Hindari (AI slop) | Pakai |
|---|---|---|
| Konfirmasi transaksi | "Awesome! Recorded! 🎉" | "Tercatat: Rp5.000 — Makanan" (tidak berubah, tetap ringkas) |
| Error parsing | "Oops! 😅" | "Tidak bisa membaca nota ini. Coba foto ulang atau input manual." |
| Saldo rendah/anomali | (hindari nada alarmis "WARNING! Low balance!!") | "Saldo BCA: Rp150.000 — lebih rendah dari rata-rata bulan ini." (informatif, tidak menghakimi) |

Prinsip: **langsung, informatif, tanpa basa-basi motivasional.** Anda mencatat uang Anda sendiri — tidak perlu aplikasi menyemangati Anda seperti gym app.

## 8. Konsep Layar Kunci (Deskripsi, Bukan Wireframe Detail)

### 8.1 Beranda (Home)
- Saldo total (gabungan semua akun aktif) di atas — Display size, IBM Plex Mono.
- List akun individual dengan saldo masing-masing (card ringkas, tap untuk detail).
- Ringkasan pengeluaran/pemasukan bulan berjalan (angka, bukan chart besar — chart detail ada di halaman Report terpisah).
- Tombol input transaksi (FAB) — akses cepat manual/foto nota.

### 8.2 Input/Konfirmasi Transaksi
- Setelah parsing (teks/foto), tampilkan hasil sebagai **form editable**, bukan read-only — setiap field (nominal, kategori, akun, item) bisa dikoreksi langsung sebelum tap "Simpan".
- Confidence rendah (dari OCR) ditandai dengan badge warna `expense` (rust) kecil di dekat field terkait, bukan alert besar mengganggu.

### 8.3 Riwayat Transaksi (revisi)
- Grouping per tanggal relatif ("Hari Ini", "Kemarin", lalu tanggal eksplisit
  untuk >2 hari), bukan flat list tanpa header.
- Setiap grup: garis vertikal tipis (`outline` token, 2dp) di sisi kiri,
  dengan titik (dot, 8dp) di tiap item — warna dot mengikuti `income`/`expense`
  token, BUKAN warna generik hijau/merah terang.
- Card item: nama transaksi (Manrope Medium) + sumber/akun (caption,
  on-surface-variant) di kiri; nominal (IBM Plex Mono, rata kanan) di kanan.
- Tap item = expand inline (bukan navigasi ke halaman baru) menampilkan detail
  item/nota jika ada — interaksi ringan, bukan modal berat untuk aksi baca.

### 8.4 Report/Dashboard (revisi)
- Chart donut kategori: tap slice = filter list transaksi di bawahnya ke
  kategori tsb (state lokal, tidak perlu network call baru).
- Toggle periode (Today/Week/Month/Custom) sebagai segmented control dengan
  lebar tetap per opsi (lihat perbaikan bug §4 di bawah) — bukan Row bebas
  yang bisa wrap.
- Angka Income/Expense/Net: tetap IBM Plex Mono, WAJIB uji dengan nominal
  7 digit (Rp1.000.00) agar tidak terpotong di card sempit — ini root
  cause bug yang terlihat di build sekarang.

### 8.5 Manajemen Akun
- List akun dengan saldo computed real-time.
- Toggle nonaktifkan akun memicu alur pemindahan saldo (sesuai `REQUIREMENTS.md` US-22) — tampilkan sebagai bottom sheet konfirmasi, bukan dialog kecil yang mudah ter-skip tanpa dibaca.

## 9. Implementasi Teknis (REVISI — Flutter, menggantikan Jetpack Compose)

Token warna, tipografi, spacing, radius — **NILAI-NILAINYA TIDAK BERUBAH**
dari §3-5 (dusty blue/slate blue tetap dipertahankan sesuai keputusan
sebelumnya), hanya sintaks implementasi yang berubah ke Flutter ThemeData.

```dart
// lib/theme/app_theme.dart

class AppColors {
  // Light Mode
  static const surface = Color(0xFFF5F7FA);
  static const surfaceVariant = Color(0xFFE8EDF5);
  static const onSurface = Color(0xFF1A2233);
  static const onSurfaceVariant = Color(0xFF556070);
  static const primary = Color(0xFF3B5B8C);
  static const primaryContainer = Color(0xFFD0DCF0);
  static const income = Color(0xFF3D7A5F);
  static const expense = Color(0xFFA8503C);
  static const outline = Color(0xFFD0D8E8);

  // Dark Mode
  static const surfaceDark = Color(0xFF131B27);
  static const surfaceVariantDark = Color(0xFF1C2738);
  static const onSurfaceDark = Color(0xFFE2E8F5);
  static const onSurfaceVariantDark = Color(0xFFA0ABBE);
  static const primaryDark = Color(0xFF7B9ED4);
  static const primaryContainerDark = Color(0xFF243554);
  static const incomeDark = Color(0xFF6AAF8E);
  static const expenseDark = Color(0xFFD18871);
  static const outlineDark = Color(0xFF2C3D57);
}

final lightTheme = ThemeData(
  colorScheme: ColorScheme.light(
    primary: AppColors.primary,
    primaryContainer: AppColors.primaryContainer,
    surface: AppColors.surface,
    surfaceContainerHighest: AppColors.surfaceVariant,
    onSurface: AppColors.onSurface,
    onSurfaceVariant: AppColors.onSurfaceVariant,
    outline: AppColors.outline,
  ),
  textTheme: TextTheme(
    displayLarge: GoogleFonts.manrope(fontSize: 32, fontWeight: FontWeight.w600),
    headlineMedium: GoogleFonts.manrope(fontSize: 22, fontWeight: FontWeight.w600),
    titleMedium: GoogleFonts.manrope(fontSize: 16, fontWeight: FontWeight.w500),
    bodyMedium: GoogleFonts.manrope(fontSize: 14),
  ),
  cardTheme: CardThemeData(
    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    elevation: 1,
  ),
);

// Nominal uang: widget terpisah, selalu pakai IBM Plex Mono
class MoneyText extends StatelessWidget {
  final double amount;
  final double fontSize;
  const MoneyText({required this.amount, this.fontSize = 14, super.key});

  @override
  Widget build(BuildContext context) {
    return Text(
      formatRupiah(amount),
      style: GoogleFonts.ibmPlexMono(
        fontSize: fontSize,
        fontWeight: FontWeight.w500,
      ),
    );
  }
}
```

Package Flutter yang dipakai: `google_fonts` (Manrope + IBM Plex Mono,
menggantikan manual font loading Kotlin), `flutter_riverpod`, `dio`,
`supabase_flutter`, `fl_chart` (chart donut/bar untuk report).

Prinsip §1-2 (checklist anti-slop), §3-4 (warna/tipografi), §5 (elevation/
spacing), §6 (iconography — Material Symbols tetap dipakai via
`material_symbols_icons` package Flutter), §7 (voice/microcopy), §8
(konsep layar) — **SEMUA TIDAK BERUBAH**, hanya §9 implementasi teknis
yang diganti dari Kotlin ke Dart.

## 10. Prinsip Eksekusi Desain (Manual — Copilot-Compatible)

Setiap kali membuat/mengubah komponen UI, Copilot WAJIB mengikuti urutan ini,
bukan langsung menulis kode dari deskripsi visual:

1. **Fungsi dulu, bentuk kemudian.** Sebelum menulis Composable, jawab: data apa
   yang ditampilkan, aksi apa yang tersedia, urutan baca apa yang paling penting?
   Baru petakan ke layout. Dilarang mulai dari "buatkan card yang bagus".
2. **Reuse token sebelum membuat nilai baru.** Semua warna/spacing/radius WAJIB
   ambil dari `MyMoneyLightColorScheme`/`DarkColorScheme` dan skala spacing 4dp
   (§5). Nilai hex/dp baru hanya boleh ditambah lewat perubahan token resmi,
   bukan ditulis inline di Composable.
3. **Audit anti-slop sebelum PR** — jalankan checklist §2 sebagai self-review,
   bukan setelah reviewer menegur.
4. **Aksesibilitas bukan opsional**: kontras warna teks minimum WCAG AA
   (4.5:1 body text), target sentuh minimum 48dp, `contentDescription` wajib
   di semua icon interaktif non-dekoratif.
5. **Setiap elemen interaktif baru butuh justifikasi tertulis** (komentar kode
   singkat) kenapa ia ada — mencegah penambahan animasi/dekorasi tanpa fungsi
   (lihat §2 soal glassmorphism/shadow tanpa alasan).