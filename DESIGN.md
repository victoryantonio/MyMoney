# DESIGN.md — MyMoney (UI/UX)

## 1. Prinsip Desain

MyMoney adalah *personal tool* — bukan produk SaaS yang harus "menjual diri" ke pengguna baru setiap saat. Desainnya harus terasa seperti **buku catatan pribadi yang rapi**, bukan dashboard korporat atau aplikasi yang berusaha terlihat "canggih". Tiga prinsip:

1. **Tenang, bukan mencolok.** Data finansial itu personal dan kadang bikin cemas — desain harus menenangkan, bukan menambah noise visual.
2. **Angka adalah bintang utama.** Semua elemen desain lain (warna, tipografi, layout) melayani keterbacaan angka, bukan bersaing dengan angka.
3. **Personality lewat detail kecil, bukan dekorasi besar.** Kehangatan datang dari pilihan warna, tipografi, dan micro-copy — bukan dari ilustrasi generik atau gradient dekoratif.

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

Menjauh dari default MD3 (ungu/biru generic). Basis: **warm neutral** dengan aksen **terracotta/clay** (hangat, personal, asosiasi "tanah/nyata" — kontras dari biru korporat/fintech generic) dan **sage green** untuk indikator positif (bukan hijau terang generic "growth app").

### Light Mode

| Token | Hex | Penggunaan |
|---|---|---|
| `surface` | `#FBF7F2` | Background utama — krem hangat, bukan putih steril |
| `surface-variant` | `#F0E9E0` | Card, container sekunder |
| `on-surface` | `#2B2622` | Teks utama — coklat gelap hangat, bukan hitam pekat |
| `on-surface-variant` | `#6B6259` | Teks sekunder, caption |
| `primary` | `#B4552F` | Terracotta/clay — CTA utama, elemen brand |
| `primary-container` | `#F4DCC9` | Background untuk elemen primary yang lembut |
| `income` | `#5B7A5E` | Sage green — indikator pemasukan |
| `expense` | `#A8503C` | Rust/brick — indikator pengeluaran (lebih hangat dari merah alarm khas) |
| `outline` | `#DCD2C4` | Border, divider |

### Dark Mode

| Token | Hex | Penggunaan |
|---|---|---|
| `surface` | `#1E1B18` | Background utama — coklat gelap hangat, bukan hitam pekat/abu netral |
| `surface-variant` | `#2A2521` | Card, container sekunder |
| `on-surface` | `#EDE6DD` | Teks utama |
| `on-surface-variant` | `#B5AA9C` | Teks sekunder |
| `primary` | `#E08A5C` | Terracotta lebih terang untuk kontras di dark mode |
| `primary-container` | `#5C3620` | Background elemen primary |
| `income` | `#8FAF8E` | Sage green versi terang |
| `expense` | `#D18871` | Rust versi terang |
| `outline` | `#443E37` | Border, divider |

**Kenapa bukan biru/hijau terang generic**: hampir semua aplikasi finance (Mint, YNAB, GoPay, dsb) memakai biru korporat atau hijau terang "growth". Terracotta + sage adalah pilihan sadar untuk terasa **personal/human**, sesuai arah "hangat-personal" yang Anda pilih — bukan meniru identitas visual fintech korporat.

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
| Konfirmasi transaksi | "Awesome! Your transaction has been recorded! 🎉" | "Tercatat: Rp5.000 — Makanan" |
| Error parsing | "Oops! Something went wrong! Please try again 😅" | "Tidak bisa baca nota ini. Coba foto ulang atau input manual." |
| Empty state | "Start your financial journey today!" | "Belum ada transaksi bulan ini." |
| Konfirmasi hapus | "Are you sure you want to delete this?" | "Hapus transaksi ini? Tidak bisa dibatalkan." |

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