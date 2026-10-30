# Changelog — MyMoney

All notable changes to the MyMoney app are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versioning follows [Semantic Versioning](https://semver.org/).

## [1.5.0+11] — 2026-11-02

### Fixed
- **Backend produksi masih menjalankan kode lama** — Perbaikan tanggal mutasi memang sudah ada
  di repositori sejak 1.4.2, tetapi container produksi belum dibangun ulang dan migrasi `0013`
  belum diterapkan, sehingga transaksi tetap tersimpan pada waktu konfirmasi. Container sudah
  di-`build` ulang dan `alembic upgrade head` dijalankan (0012 → 0013). **Tanpa langkah ini,
  perubahan kode apa pun tidak akan terlihat di aplikasi.**

### Added
- **Hapus massal transaksi** — Tekan lama satu baris di tab Transaksi untuk masuk mode pilih,
  centang beberapa baris, lalu hapus semuanya sekaligus. Satu permintaan, satu commit di server.
- **Tombol “Pilih semua”** di app bar mode pilih (berubah menjadi “Batalkan pilih semua” saat
  semua baris tercentang). Cakupannya mengikuti filter/pencarian yang sedang aktif.
- Endpoint `POST /api/transactions/bulk-delete` (`{ids: [...]}`, maks 200 id, 20/menit) dengan
  respons `{deleted, missing}`. Id yang sudah tidak ada di server dilaporkan sebagai `missing`
  dan tidak menggagalkan proses.
- Audit log `delete` tetap dibuat **per baris**, dengan penanda tambahan `bulk: true`.

### Changed
- Mode pilih menampilkan checkbox di setiap baris dan menyembunyikan menu titik-tiga; aksi hapus
  dinonaktifkan selama permintaan berjalan.
- Daftar id terpilih dipangkas otomatis setiap kali daftar dimuat ulang (filter/pencarian).
- Version number: `1.4.2+10` → `1.5.0+11`.

## [1.4.2+10] — 2026-11-02

### Fixed
- **Transaksi hasil Matching Mutasi tercatat pada tanggal & jam hari ini** — Baris yang
  dikonfirmasi kini disimpan memakai tanggal dan jam **asli dari mutasi bank**, bukan waktu
  konfirmasi. Pending menyimpan tanggal tersebut (UTC + zona waktu user), dan layar pending
  menampilkan "Tanggal transaksi" supaya bisa diperiksa sebelum dikonfirmasi. Bila mutasi
  tidak mencetak jam, dipakai `00:00` waktu lokal.
- **Transaksi bulan lain ikut dicocokkan** — Pencocokan sekarang memakai **bulan yang dicakup
  berkas mutasi** sebagai filter (mis. hanya September 2026), bukan jendela tanggal di sekitar
  baris mutasi. Batas bulan dihitung di zona waktu user, sehingga transaksi 30 September 23:30
  WIB tetap dianggap bagian September. Berkas tanpa tanggal terbaca tetap memakai jendela lebar
  seperti sebelumnya.

### Added
- **Ringkasan "Periode mutasi"** pada layar hasil Matching Mutasi (mis. `September 2026`).
- Migrasi `0013_pending_transaction_date` — kolom `transaction_date` dan `timezone` pada
  `pending_transactions`.

### Changed
- Version number: `1.4.1+9` → `1.4.2+10`.

## [1.4.1+9] — 2026-10-30

### Added
- **Matching Mutasi: statement yang hanya membedakan arah lewat warna** —
  Sebagian bank (mis. Permata) tidak mencetak kolom Keluar/Masuk sama sekali;
  arah dana hanya terlihat dari warna teks. Parser kini membaca warna nominal
  (merah = pengeluaran, hijau = pemasukan) dan memakai tanggal terakhir untuk
  baris berikutnya. Bila ada nominal tanpa warna, arah tidak ditebak dan baris
  tersebut diserahkan ke jalur berikutnya.

### Fixed
- **Total Balance Dashboard tidak mengikuti filter akun** — Kartu saldo kini
  menjumlahkan hanya akun yang sedang difilter, dengan subtitle nama akun; 
  bila tidak ada akun dipilih, nominal menjadi `Rp 0` dengan keterangan `Tidak ada akun dipilih`.

### Removed
- **Bot Telegram** — Fitur bot Telegram dihapus seluruhnya (kode bot, webhook,
  endpoint linking, variabel environment, beserta dokumentasinya). Semua input
  sekarang melalui aplikasi mobile.

### Changed
- Version number: `1.4.0+8` → `1.4.1+9`.

## [1.4.0+8] — 2026-09-15

### Added
- **Matching Mutasi: dukungan PDF e-statement** — Tombol *Pilih PDF
  E-Statement* di menu Matching Mutasi. PDF digital dibaca dari layer teksnya
  (cepat & akurat), sedangkan PDF hasil scan di-render dan dibaca vision LLM
  halaman demi halaman — tanpa batas jumlah halaman (batasnya hanya ukuran
  berkas 20 MB).

### Changed
- **Dropdown akun pada form transaksi baru** — Tidak lagi menampilkan
  keterangan tipe akun (Bank/E-Wallet); hanya nama akun apa adanya.
- Version number: `1.3.0+7` → `1.4.0+8`.

## [1.3.0+7] — 2026-09-14

### Added
- **Matching Mutasi** — Menu Upload di kanan atas Dashboard untuk
  mencocokkan mutasi bank dengan catatan. Backend membaca setiap baris mutasi
  (screenshot/foto via vision LLM atau ekspor CSV), lalu memeriksa apakah
  nominalnya sudah balance dengan transaksi tercatat (nominal + arah dana +
  jarak tanggal + akun). Mutasi yang belum tercatat otomatis dibuat sebagai
  *transaksi pending* untuk dikonfirmasi user.
- **Jam transaksi** — Form input transaksi kini punya kolom *Jam*
  sejajar dengan kolom *Tanggal*.
- **Filter tanggal (between) di menu Transaksi** — Batasi daftar
  transaksi pada rentang tanggal tertentu.
- **Pencarian transaksi** — Ikon magnifier di kanan atas menu Transaksi
  untuk mencari dari Merchant/keterangan maupun nama item.
- **Snapshot zona waktu per transaksi** — Storage tetap UTC, tetapi
  interpretasi/tampilan memakai zona waktu user yang di-*snapshot* saat
  transaksi dibuat. Zona waktu awal mengikuti setting HP (form saat pertama
  login) dan bisa diubah kapan saja di menu Profil.

### Fixed
- **Select All pada filter Dashboard** — Menekan "Select All" saat semua
  item sudah terpilih kini membatalkan semua pilihan (unselect all).
- **Chart cashflow per akun & transfer** — Transfer antar akun tidak lagi
  dihitung sebagai income/expense, dan filter akun kini juga menyertakan
  transaksi yang masuk ke akun tujuan sehingga saldo per akun konsisten dengan
  best practice akuntansi.
- **Bar percentage kategori terkunci** — Bar percentage di chart kategori
  tidak berubah saat salah satu kategori expense/income dipilih.

### Changed
- Version number: `1.2.2+6` → `1.3.0+7`.

## [1.2.2+6] — 2026-08-31

### Added
- **Informasi Aplikasi di Menu Profil** — Menambahkan informasi versi aplikasi secara dinamis (`package_info_plus`) dan tombol "Cek Pembaruan" pada tab Profil.

### Fixed
- **Filter Transaksi Kategori Transfer** — Transaksi transfer kini otomatis ditampilkan ketika akun asal (`accountId`) atau akun tujuan (`toAccountId`) dipilih pada filter akun.
- **UX Multi-Checklist Filter Dashboard** — Menu filter akun tidak lagi tertutup otomatis saat memilih/membatalkan pilihan akun (`closeOnActivate: false`), dan toggle "Select All" kini berfungsi dengan benar.
- **Robustness OCR Nota** — Prompt OCR nota ditingkatkan dengan fallback dummy item total bila baris produk buram tetapi nominal total terbaca (mencegah error "couldn't read nota").
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
  (OCR), kategori, akun, laporan, dan bot Telegram. *(Bot Telegram dihapus pada
  1.4.1.)*
