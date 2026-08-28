# Changelog — MyMoney

Semua perubahan penting aplikasi MyMoney dicatat di sini.
Format mengikuti [Keep a Changelog](https://keepachangelog.com/id-ID/1.1.0/).
Versi mengikuti [Semantic Versioning](https://semver.org/lang/id/).

## [1.1.0+2] — 2026-08-28

### Added
- **Multi-mata uang per transaksi** — setiap transaksi bisa memakai mata uang selain
  IDR (USD, EUR, SGD, dsb.); nominal disimpan dalam mata uang asli + nilai tukar
  terhadap IDR, dan total selalu dihitung dalam IDR.
- **Sistem Transfer antar akun** — pindahkan saldo antar akun (cash/e-wallet/bank)
  tanpa memengaruhi laporan pemasukan/pengeluaran.
- **Nama kategori unik per pengguna (case-insensitive)** — tidak bisa membuat
  dua kategori dengan nama sama (mis. "Makan" vs "makan") pada tipe yang sama.
- **Hardening produksi**:
  - Mode production aktif di backend (`APP_ENV=production`): dokumentasi API
    (`/docs`) disembunyikan, CORS dibatasi ke domain resmi.
  - Rate limit pada seluruh endpoint mutasi (transaksi 30/menit, kategori &
    akun 20/menit, OCR 10/menit).
  - Skrip backup database otomatis harian (pg_dump, rotasi 14 hari).
  - Release APK ditandatangani dengan keystore produksi (bukan debug).

### Fixed
- **Truncation SegmentedButton** (Pengeluaran/Pemasukan/Transfer terpotong) di
  form transaksi dan manajemen kategori — ikon segmen dihapus & `showSelectedIcon`
  dimatikan agar label tidak terpotong.
- **Dropdown mata uang** — hanya menampilkan kode mata uang (mis. `USD`) sehingga
  kolom nominal lebih lebar dan nyaman diisi.
- **Pesan konflik kategori** — membuat kategori yang sudah ada kini menampilkan
  "Kategori sudah ada" (409) alih-alih "Server Error 409"; pesan `detail` dari
  backend ditampilkan apa adanya di aplikasi.
- Kategori "Other" yang sudah tersedia (default) tidak perlu dibuat ulang —
  langsung dipilih dari daftar.

### Changed
- Nomor versi: `1.0.0+1` → `1.1.0+2`.

## [1.0.0+1] — rilis awal

- Aplikasi pencatat keuangan pribadi: dashboard, transaksi manual, scan nota
  (OCR), kategori, akun, laporan, dan bot Telegram.
