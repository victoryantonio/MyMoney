# Changelog — MyMoney

All notable changes to the MyMoney app are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versioning follows [Semantic Versioning](https://semver.org/).

## [1.3.0+7] — 2026-09-14

### Added
- **Matching Mutasi (Req 9)** — Menu Upload di kanan atas Dashboard untuk
  mencocokkan mutasi bank dengan catatan. Backend membaca setiap baris mutasi
  (screenshot/foto via vision LLM atau ekspor CSV), lalu memeriksa apakah
  nominalnya sudah balance dengan transaksi tercatat (nominal + arah dana +
  jarak tanggal + akun). Mutasi yang belum tercatat otomatis dibuat sebagai
  *transaksi pending* untuk dikonfirmasi user.
- **Jam transaksi (Req 8)** — Form input transaksi kini punya kolom *Jam*
  sejajar dengan kolom *Tanggal*.
- **Filter tanggal (between) di menu Transaksi (Req 7)** — Batasi daftar
  transaksi pada rentang tanggal tertentu.
- **Pencarian transaksi (Req 6)** — Ikon magnifier di kanan atas menu Transaksi
  untuk mencari dari Merchant/keterangan maupun nama item.
- **Snapshot zona waktu per transaksi (Req 5)** — Storage tetap UTC, tetapi
  interpretasi/tampilan memakai zona waktu user yang di-*snapshot* saat
  transaksi dibuat. Zona waktu awal mengikuti setting HP (form saat pertama
  login) dan bisa diubah kapan saja di menu Profil.

### Fixed
- **Select All pada filter Dashboard (Req 2)** — Menekan "Select All" saat semua
  item sudah terpilih kini membatalkan semua pilihan (unselect all).
- **Chart cashflow per akun & transfer (Req 3)** — Transfer antar akun tidak lagi
  dihitung sebagai income/expense, dan filter akun kini juga menyertakan
  transaksi yang masuk ke akun tujuan sehingga saldo per akun konsisten dengan
  best practice akuntansi.
- **Bar percentage kategori terkunci (Req 4)** — Bar percentage di chart kategori
  tidak berubah saat salah satu kategori expense/income dipilih.

### Changed
- Version number: `1.2.2+6` → `1.3.0+7`.

## [1.2.2+6] — 2026-08-31

### Added
- **Informasi Aplikasi di Menu Profil** — Menambahkan informasi versi aplikasi secara dinamis (`package_info_plus`) dan tombol "Cek Pembaruan" pada tab Profil.

### Fixed
- **Filter Transaksi Kategori Transfer** — Transaksi transfer kini otomatis ditampilkan ketika akun asal (`accountId`) atau akun tujuan (`toAccountId`) dipilih pada filter akun.
- **UX Multi-Checklist Filter Dashboard** — Menu filter akun tidak lagi tertutup otomatis saat memilih/membatalkan pilihan akun (`closeOnActivate: false`), dan toggle "Select All" kini berfungsi dengan benar.
- **Robustness OCR Nota** — Prompt OCR Telegram ditingkatkan dengan fallback dummy item total bila baris produk buram tetapi nominal total terbaca (mencegah error "couldn't read nota").
- **Domain Konfigurasi Produksi** — Pembaruan URL bot & auth ke domain resmi.

### Changed
- Version number: `1.2.1+5` → `1.2.2+6`.

## [1.2.1+5] — 2026-08-28

### Changed
- **Format tanggal line chart** — label sumbu bawah kini menampilkan tanggal
  dulu baru bulan (mis. `12 Agu`, bukan `Agu 12`); tetap menyertakan tahun
  bila berbeda dari tahun berjalan.
- Version number: `1.2.0+4` → `1.2.1+5`.

## [1.2.0+4] — 2026-08-28

### Added
- **Filter & sortir menu Transaksi** — filter multi-checklist akun + kategori
  (ikon filter di AppBar, dengan badge jumlah pilihan) dan sortir berdasarkan
  tanggal (terbaru/terlama) maupun nominal (terbesar/terkecil); chip filter
  aktif tampil di atas daftar dan bisa dihapus satu per satu.
- **Edit saldo awal akun** — dialog edit akun kini menyertakan kolom "Saldo
  awal" (dengan helper saldo saat ini); mengubahnya langsung menyesuaikan
  current balance (initial + SUM transaksi).

### Changed
- **Daftar Income/Expense/Net dari dashboard** — halaman hasil tap summary
  card kini juga bisa difilter akun/kategori (multi-checklist) & disortir
  tanggal/nominal sehingga daftar lebih ringkas.
- Version number: `1.1.1+3` → `1.2.0+4`.

## [1.1.1+3] — 2026-08-28

### Fixed
- **Donut chart teks terpotong** — nilai net di tengah doughnut sekarang
  otomatis dikecilkan (FittedBox) sehingga nominal panjang tidak lagi terpotong.
- **Hide saldo ikut menyembunyikan donut** — saat mata saldo di-hide, nilai di
  tengah doughnut chart, total per kategori, dan nominal di recent transactions
  ikut tertutup (Rp ••••••) bersama income/expense.
- **Daftar transaksi tidak langsung update** — setelah tambah/edit transaksi,
  tab Transaksi kini langsung di-refresh (refresh token antar tab).
- **Thousand separator** — prefill nominal saat edit transaksi kini memakai
  format ribuan (mis. `1.500.000`), konsisten dengan input form.
- **Error "Transfer transactions do not use a category"** — saat mengubah
  transaksi menjadi transfer, kategori sekarang dikosongkan eksplisit di
  request sehingga tidak lagi memicu 422 dari backend.

### Changed
- **Recent transactions dashboard** — hanya menampilkan transaksi dalam periode
  aktif (Today = hanya "Hari ini", bukan tanggal lain); label tanggal memakai
  "Hari ini" / "Kemarin"; jumlah item dinaikkan dari 5 menjadi 10.
- **Optimasi performa** — transaksi terbaru dashboard difilter tanggal di
  SERVER (`date_from`/`date_to`), payload lebih kecil & dashboard lebih cepat.
- Version number: `1.1.0+2` → `1.1.1+3`.

## [1.1.0+2] — 2026-08-28

### Added
- **Multi-currency per transaction** — every transaction can use a currency
  other than IDR (USD, EUR, SGD, etc.); the amount is stored in the original
  currency plus its exchange rate to IDR, and totals are always computed in IDR.
- **Account transfer system** — move balances between accounts
  (cash/e-wallet/bank) without affecting income/expense reports.
- **Unique category names per user (case-insensitive)** — you can no longer
  create two categories with the same name (e.g. "Food" vs "food") in the same
  type.
- **Production hardening**:
  - Production mode enabled in the backend (`APP_ENV=production`): API docs
    (`/docs`) are hidden and CORS is restricted to the official domain.
  - Rate limiting on all mutation endpoints (transactions 30/min, categories &
    accounts 20/min, OCR 10/min).
  - Automated daily database backup script (pg_dump, 14-day rotation).
  - Release APK signed with the production keystore (no longer debug).

### Fixed
- **SegmentedButton truncation** (Expense/Income/Transfer clipped) in the
  transaction form and category management — segment icons removed &
  `showSelectedIcon` disabled so labels are no longer cut off.
- **Currency dropdown** — now shows only the currency code (e.g. `USD`) so the
  amount field is wider and easier to fill in.
- **Category conflict message** — creating an already-existing category now
  shows "Kategori sudah ada" (409) instead of "Server Error 409"; the backend's
  `detail` message is shown as-is in the app.
- The "Other" category that already exists (default) no longer needs to be
  recreated — just pick it from the list.

### Changed
- Version number: `1.0.0+1` → `1.1.0+2`.

## [1.0.0+1] — initial release

- Aplikasi pencatat keuangan pribadi: dashboard, transaksi manual, scan nota
  (OCR), kategori, akun, laporan, dan bot Telegram.
