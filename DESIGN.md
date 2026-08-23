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

### 8.3 Riwayat Transaksi
- List dengan grouping per tanggal, nominal rata kanan pakai monospace agar sejajar.
- Warna nominal: `income` (sage) untuk pemasukan, `expense` (rust) untuk pengeluaran — bukan hijau/merah terang standar.

### 8.4 Report/Dashboard
- Chart kategori (donut/bar sederhana, bukan chart 3D atau gradient-heavy).
- Palet chart mengambil dari token warna kategori yang konsisten, bukan warna random per kategori.

### 8.5 Manajemen Akun
- List akun dengan saldo computed real-time.
- Toggle nonaktifkan akun memicu alur pemindahan saldo (sesuai `REQUIREMENTS.md` US-22) — tampilkan sebagai bottom sheet konfirmasi, bukan dialog kecil yang mudah ter-skip tanpa dibaca.

## 9. Implementasi Teknis (Jetpack Compose)

```kotlin
// Contoh definisi color scheme custom, bukan default MD3
val MyMoneyLightColorScheme = lightColorScheme(
    primary = Color(0xFFB4552F),
    primaryContainer = Color(0xFFF4DCC9),
    surface = Color(0xFFFBF7F2),
    surfaceVariant = Color(0xFFF0E9E0),
    onSurface = Color(0xFF2B2622),
    onSurfaceVariant = Color(0xFF6B6259),
    outline = Color(0xFFDCD2C4)
)

val MyMoneyDarkColorScheme = darkColorScheme(
    primary = Color(0xFFE08A5C),
    primaryContainer = Color(0xFF5C3620),
    surface = Color(0xFF1E1B18),
    surfaceVariant = Color(0xFF2A2521),
    onSurface = Color(0xFFEDE6DD),
    onSurfaceVariant = Color(0xFFB5AA9C),
    outline = Color(0xFF443E37)
)

// Warna income/expense sebagai custom token terpisah (MD3 tidak punya token bawaan untuk ini)
data class MyMoneyExtendedColors(
    val income: Color,
    val expense: Color
)
```

Font di-load via `FontFamily` custom (Manrope + IBM Plex Mono dari Google Fonts), diterapkan lewat `Typography` custom di `MaterialTheme`, bukan default MD3 typography.