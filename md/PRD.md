# PRD — Matching Mutasi Rekening & Filter Saldo Dashboard

| Field | Isi |
| --- | --- |
| Produk | MyMoney (aplikasi mobile Flutter + backend REST; tanpa bot Telegram) |
| Fitur | Matching Mutasi Rekening, Filter Total Balance Dashboard |
| Versi dokumen | 1.4 |
| Tanggal | 2026-11-02 |
| Status | Disetujui untuk implementasi |
| Dokumen terkait | `md/TRD.md`, `backend/README.md`, `README.md` |
| Perubahan 1.4 | Hapus massal di tab Transaksi: mode multi-pilih + **Pilih semua** (FR-11) |
| Perubahan 1.3 | Filter berbasis **bulan mutasi** (bukan jendela tanggal) + transaksi tercatat pada **tanggal & jam asli mutasi**, bukan waktu konfirmasi (FR-10) |
| Perubahan 1.2 | Jalan keluar layar Matching Mutasi (tombol Matching + `PendingReviewScreen`) dan kebersihan tabel `pending_transactions` (FR-8, FR-9) |
| Perubahan 1.1 | Bank ketiga (Permata) yang hanya menandai arah dana lewat **warna teks**; penghapusan fitur bot Telegram |

---

## 1. Latar Belakang

MyMoney mencatat transaksi dari dua sumber: form Flutter dan pemindaian nota (OCR). Keduanya
bergantung pada **ingatan dan kedisiplinan user**. User yang sudah punya catatan historis di
aplikasi tetap harus mengetik ulang setiap transaksi hanya untuk menyamakan saldo dengan mutasi
bank yang asli.

Masalah ini muncul berulang di praktik:

1. User lupa mencatat pengeluaran kecil (QRIS, admin bank, tarik ATM) sehingga saldo aplikasi
   lebih tinggi dari saldo bank.
2. User baru mulai memakai MyMoney di tengah bulan; saldo awal aplikasi tidak sama dengan saldo
   rekening sebenarnya.
3. Rekonsiliasi manual (buka mutasi bank, buka daftar transaksi, cocokkan satu per satu) makan
   waktu dan mudah salah.

Semua bank di Indonesia sudah menyediakan **e-statement PDF** atau minimal tangkapan layar mutasi.
Jika berkas itu bisa dibaca mesin, rekonsiliasi dapat berubah dari pekerjaan manual menjadi satu
kali unggah.

Pada rilis pertama fitur ini, unggahan **PDF e-statement asli dari user gagal total**: sistem
mengembalikan HTTP 422 "Mutasi tidak terbaca". Penyebabnya bukan berkas yang rusak, melainkan
pipeline yang tidak mengenali tata letak e-statement Indonesia (kolom `KELUAR`/`MASUK`,
deskripsi multi-baris, tanggal tanpa tahun). Fitur yang sudah "ada" secara teknis belum bisa
dipakai secara nyata.

Uji coba berlanjut ke bank ketiga. Statement **Permata** membuktikan bahwa asumsi "kolom" saja
belum cukup: berkas itu **tidak punya kolom keluar/masuk sama sekali** dan hanya membedakan arah
dana dari **warna teks** — nominal hijau berarti uang masuk, nominal merah berarti uang keluar.
Artinya arah dana bisa menjadi informasi yang hilang total bila teks diekstrak tanpa warna.

Selain itu ditemukan regresi terpisah di dashboard: nilai **Total Balance tidak mengikuti filter
akun**. Saat user memfilter satu akun, kartu saldo tetap menampilkan total seluruh akun sehingga
angka yang dibaca user salah konteks.

Pada versi 1.1 ini juga diputuskan **penyempitan lingkup**: bot Telegram dihapus dari produk.
Dalam pemakaian nyata user hampir selalu memakai aplikasi mobile, sehingga jalur kedua yang harus
dirawat (Node bot, webhook, token linking) hanya menambah permukaan perawatan tanpa nilai pakai.

---

## 2. Tujuan

### 2.1 Tujuan

| ID | Tujuan | Indikator keberhasilan |
| --- | --- | --- |
| G-1 | Mutasi rekening dari e-statement PDF asli terbaca tanpa intervensi manual | ≥ 95% baris transaksi pada sampel e-statement nyata terekstrak |
| G-2 | Hasil ekstraksi dapat dipercaya tanpa LLM untuk berkas digital | Total debit/kredit hasil parser **sama persis** dengan ringkasan saldo pada statement |
| G-3 | Rekonsiliasi aman: tidak ada data parsing yang langsung menjadi transaksi | 100% baris tak cocok masuk `pending_transaction` dan menunggu konfirmasi |
| G-4 | Angka saldo di dashboard konsisten dengan filter yang aktif | Total Balance + kartu pendapatan/pengeluaran memakai cakupan akun yang sama |
| G-5 | Biaya LLM tetap rendah | Berkas digital tidak memanggil LLM sama sekali |
| G-6 | Bank yang hanya menandai arah dana dengan warna tetap terbaca | Arah dana 100% baris pada sampel Permata benar; total debit/kredit sama dengan statement |

### 2.2 Non-Tujuan

- Tidak menghitung atau mengubah saldo akun secara otomatis dari mutasi (saldo tetap dihitung dari
  transaksi yang tercatat).
- Tidak mendukung rekonsiliasi dua arah (menghapus transaksi lokal karena tidak ada di mutasi).
- Tidak menambahkan OCR khusus untuk PDF hasil pindaian pada iterasi ini (jalur vision tetap ada
  sebagai fallback, tanpa dioptimalkan).
- Tidak menebak arah dana bila tidak ada petunjuk apa pun (kolom maupun warna); baris seperti itu
  dibiarkan tidak terbaca dan diserahkan ke fallback.
- Tidak mempertahankan bot Telegram; kanal input resmi hanya aplikasi mobile.
- Tidak menambah model database atau migrasi.
- Tidak mengubah alur konfirmasi pending yang sudah ada.

---

## 3. Pengguna Sasaran

| Persona | Kebutuhan | Rasa sakit saat ini |
| --- | --- | --- |
| **Rekonsiliasi rutin** — user disiplin mencatat, ingin memastikan tidak ada yang terlewat | Unggah mutasi bulanan, lihat mana yang belum tercatat | Mencocokkan manual 60–80 baris |
| **Migrasi awal** — user baru pindah ke MyMoney | Masukkan transaksi sebulan terakhir | Mengetik ulang puluhan transaksi |
| **Multi-akun** — user punya tabungan + dompet digital | Pastikan mutasi masuk ke akun yang benar | Salah akun membuat saldo keduanya kacau |

---

## 4. Alur Pengguna

### 4.1 Alur utama (happy path)

```text
Dashboard → Matching Mutasi
        → pilih akun (opsional, default "Semua akun")
        → pilih berkas: Kamera / Galeri / PDF E-Statement
        → [Membaca & mencocokkan mutasi…]
        → Ringkasan: total baris, cocok, belum cocok, transaksi lokal tak bertemu
        → daftar "Mutasi yang cocok" + daftar mutasi yang masuk Pending
        → user membuka menu Pending dan mengonfirmasi satu per satu
```

### 4.2 Alur gagal yang harus tetap jelas

| Kondisi | Perilaku yang diharapkan |
| --- | --- |
| Berkas bukan mutasi (mis. foto struk belanja) | Pesan "Mutasi tidak terbaca — pastikan berkas memuat daftar transaksi (tanggal, keterangan, nominal) lalu coba lagi." |
| PDF berpassword / rusak | Pesan galat yang sama, tidak crash, tidak ada server error 500 |
| Berkas > 20 MB | Ditolak sebelum diproses dengan pesan ukuran |
| LLM tidak tersedia (API key kosong) | Parser deterministik tetap harus menghasilkan baris; jika tidak ada baris, tampilkan pesan gagal baca, bukan galat internal |
| Semua baris cocok | Ringkasan menampilkan 0 pending; tidak error |

### 4.3 Alur filter saldo (perbaikan regresi)
```text
Dashboard
  → filter akun: "Semua akun"  → Total Balance = jumlah seluruh akun, tanpa subtitle
  → filter akun: satu akun     → Total Balance = saldo akun itu, subtitle "SeaBank · Bank"
  → filter akun: 2+ akun       → Total Balance = jumlah akun terpilih, subtitle "2 akun terpilih"
  → filter akun: tidak ada     → Total Balance = Rp 0, subtitle "Tidak ada akun dipilih"
```

### 4.4 Alur konfirmasi pending (baru di 1.2)

```text
Dashboard → Upload → Matching Mutasi
  → pilih berkas + akun → "Cocokkan Mutasi"
  → layar hasil: pasangan cocok + daftar baris belum cocok
  → tombol **Matching** di bagian bawah layar ("Matching — konfirmasi N baris")
      → layar Pending: daftar baris menunggu konfirmasi (baris unggahan ini di atas)
          → "Konfirmasi" → transaksi nyata dibuat, baris hilang dari daftar
          → "Batalkan"   → baris dihapus, tidak ada transaksi dibuat
  → user keluar tanpa menekan Matching
      → baris pending dari unggahan itu dibatalkan otomatis (tabel tetap bersih)
      → bila tetap tersisa, dibersihkan saat daftar dibuka / backend start / unggahan berikutnya
```

---

## 5. Kebutuhan Fungsional

### FR-1 — Unggah mutasi dari tiga sumber

**Sebagai** user, **saya ingin** mengunggah mutasi sebagai foto, gambar galeri, atau PDF
e-statement **agar** saya tidak perlu mengetik ulang.

Kriteria penerimaan:

- [x] Menerima `image/*`, `text/*`, `.csv`, `.txt`, `.tsv`, `application/pdf`.
- [x] Maksimum 20 MB; lebih dari itu ditolak dengan pesan jelas.
- [x] Deteksi tipe berkas tidak hanya dari nama, tetapi juga dari magic bytes PDF.

### FR-2 — Ekstraksi baris mutasi dari teks (deterministik)

**Sebagai** pengguna PDF digital, **saya ingin** mutasi dibaca tanpa menunggu LLM **agar** cepat,
murah, dan hasilnya dapat diprediksi.

Kriteria penerimaan:

- [ ] Tabel ber-delimiter (`|`, tab, `;`, koma tabular) terbaca lengkap.
- [ ] Text layer PDF dengan kolom rata spasi terbaca lengkap.
- [ ] Header `KELUAR`/`MASUK` (SeaBank) maupun kolom tunggal `MUTASI` dengan akhiran `DB`/`CR`
      (BCA) dikenali.
- [ ] Arah dana dari **warna teks** dikenali bila statement tidak punya kolom arah sama sekali:
      nominal merah = keluar (debit), nominal hijau = masuk (kredit) — kasus Permata.
- [ ] Arah dana **tidak pernah** ditebak. Bila pada satu halaman ada nominal yang tidak berwarna,
      seluruh halaman itu dilewati jalur warna dan diserahkan ke jalur berikutnya.
- [ ] Kolom saldo berjalan **tidak pernah** dianggap nominal transaksi.
- [ ] Baris `SALDO AWAL`, `SALDO AKHIR`, `TOTAL KELUAR/MASUK`, `RINGKASAN REKENING`,
      `PERIODE MUTASI` diabaikan.
- [ ] Deskripsi multi-baris (baris keterangan di atas atau di bawah baris tanggal) digabung
      menjadi satu deskripsi.
- [ ] Tanggal `01 SEP`, `01 Sep 2026`, `01/09`, `01-09-2026`, `2026-09-01` dinormalisasi ke
      `YYYY-MM-DD`; tahun diambil dari periode statement bila tidak tertulis.
- [ ] Tanggal yang hanya dicetak sekali (di awal blok, mis. Permata) tetap dipakai untuk baris
      berikutnya pada halaman yang sama dan halaman sesudahnya.
- [ ] Entitas HTML pada text layer (`&quot;`, `&amp;`, `&lt;`, `&gt;`) didekode.
- [ ] Total debit dan kredit hasil parser sama persis dengan ringkasan pada statement.

### FR-3 — Fallback LLM

**Sebagai** user dengan PDF hasil pindaian, **saya ingin** sistem tetap mencoba membaca **agar**
tidak langsung gagal.

Kriteria penerimaan:

- [ ] Gambar dan PDF tanpa text layer dikirim ke model vision.
- [ ] PDF digital yang gagal diparse deterministik dikirim ke model teks, bukan model vision.
- [ ] Prompt teks menjelaskan dua kolom `Keluar`/`Masuk`, kolom saldo, dan tanggal tanpa tahun.
- [ ] Jika semua model gagal, API mengembalikan 422 dengan pesan yang dapat ditindaklanjuti.

### FR-4 — Pencocokan mutasi dengan transaksi

**Sebagai** user, **saya ingin** sistem menunjukkan mutasi mana yang sudah tercatat **agar** saya
tahu apa yang perlu ditambahkan.

Kriteria penerimaan:

- [x] Cocok bila nominal dalam toleransi (default Rp1,00), arah dana sama, jarak tanggal ≤ 3 hari
      (dapat diatur), dan akun sama bila akun dipilih.
- [x] Transfer dianggap cocok jika saldo salah satu sisi (`account` atau `to_account`) sesuai arah.
- [x] Ringkasan menampilkan 4 angka: total mutasi, cocok, belum cocok, transaksi lokal tanpa pasangan.

### FR-5 — Pending, bukan commit langsung

**Sebagai** user, **saya ingin** hasil parsing AI tidak langsung mengubah data keuangan saya
**agar** kesalahan baca tidak merusak catatan.

Kriteria penerimaan:

- [x] Baris tak cocok dibuat sebagai `pending_transaction`, bukan `transaction`.
- [x] Pending memakai kategori fallback yang sah untuk tipe arah dana.
- [x] Response berisi `created_pending_ids`.
- [x] Tidak ada penulisan `Transaction` di modul matcher.

### FR-6 — Total Balance mengikuti filter akun

**Sebagai** user dashboard, **saya ingin** kartu saldo menampilkan total akun yang sedang
difilter **agar** angkanya sesuai konteks.

Kriteria penerimaan:

- [ ] Filter `null` (Semua akun) → jumlah semua akun, tanpa subtitle.
- [ ] Filter berisi N akun → jumlah akun terpilih; subtitle nama akun bila N=1,
      "N akun terpilih" bila N>1.
- [ ] Filter kosong → `Rp 0` dengan subtitle "Tidak ada akun dipilih" (keputusan produk:
      kartu tetap tampil, tidak disembunyikan).
- [ ] Kartu pendapatan, pengeluaran, tren, dan kategori memakai cakupan akun yang sama.
- [ ] Logika diuji unit test terpisah dari widget.

### FR-7 — Rate limit

- [x] Endpoint `POST /api/mutations/match` dibatasi 10 permintaan/menit per IP karena berbiaya LLM.

### FR-8 — Review & konfirmasi pending dari layar Matching Mutasi

**Sebagai** user yang baru selesai mencocokkan mutasi, **saya ingin** bisa langsung
menyelesaikan baris yang belum cocok dari layar hasil **agar** alur tidak berhenti di pesan
buntu.

Latar belakang: teks hasil sebelumnya menyuruh user "buka menu Pending", padahal menu itu
tidak pernah ada di aplikasi — user terpaksa menutup layar dan baris pending menjadi yatim.

Kriteria penerimaan:

- [x] Layar hasil Matching Mutasi menampilkan tombol **Matching** di bagian bawah layar
      (`bottomNavigationBar`) saat ada baris yang belum cocok.
- [x] Label tombol menyebut jumlah baris: "Matching — konfirmasi N baris".
- [x] Tombol membuka layar `PendingReviewScreen` berisi baris pending milik user.
- [x] Setiap baris punya dua aksi tegas: **Konfirmasi** (membuat transaksi nyata) dan
      **Batalkan** (membuang baris, tidak membuat transaksi apa pun).
- [x] Baris yang baru saja dibuat dari unggahan ini ditampilkan lebih dulu.
- [x] Setelah konfirmasi/pembatalan, daftar dan ringkasan dashboard ikut diperbarui.
- [x] Tidak ada lagi teks yang menunjuk ke menu yang tidak ada.
- [x] Konfirmasi/pembatalan baris milik user lain → 404 (isolasi data).
- [x] Konfirmasi baris kedaluwarsa → 410 dengan pesan yang meminta unggah ulang.

### FR-9 — Kebersihan tabel `pending_transactions`

**Sebagai** pemilik produk, **saya ingin** baris pending yang tidak pernah dikonfirmasi ikut
hilang **agar** tabel tidak menumpuk data mati dan daftar Pending tetap bisa dibaca.

Kriteria penerimaan:

- [x] Baris dengan `expires_at` lampau dihapus otomatis saat daftar pending dimuat
      (`GET /api/pending`), saat jumlah pending diminta (`GET /api/pending/count`), dan saat
      backend start.
- [x] Saat user mengunggah mutasi baru, seluruh pending hasil "Matching Mutasi" miliknya dari
      unggahan sebelumnya dihapus — unggahan baru menggantikan daftar lama, bukan menumpuk.
- [x] Pembersihan saat unggah hanya dijalankan **setelah** berkas berhasil dibaca, sehingga
      unggahan yang gagal tidak menghapus pending yang masih berlaku.
- [x] Bila user keluar dari layar hasil tanpa menekan tombol Matching, baris pending dari
      unggahan itu dibatalkan (best-effort) sehingga tabel langsung bersih.
- [x] Baris milik alur lain (mis. riwayat percakapan Telegram lama) **tidak** ikut terhapus —
      pembersihan dibatasi pada `raw_input` berawalan `Matching Mutasi`.
- [x] Baris yang sudah dikonfirmasi menjadi transaksi nyata tidak terpengaruh pembersihan.

### FR-10 — Bulan mutasi jadi dasar filter, tanggal & jam asli dipakai saat konfirmasi

**Sebagai** user yang mengunggah mutasi satu bulan penuh, **saya ingin** sistem hanya
mencocokkan transaksi pada bulan itu dan menyimpan transaksi baru pada **tanggal & jam asli
mutasi** **agar** catatan saya sama dengan rekening bank — bukan tercatat pada hari saya
mengonfirmasi.

Latar belakang: hasil konfirmasi sebelumnya selalu masuk ke tanggal & jam hari ini, sehingga
laporan bulanan bergeser dan transaksi satu bulan bisa menumpuk di satu tanggal.

Kriteria penerimaan:

- [x] Sistem membaca seluruh tanggal pada berkas mutasi dan **mendeteksi bulan yang dicakup**
      (mis. `September 2026`), termasuk berkas yang mencakup dua bulan berurutan.
- [x] Filter kandidat transaksi memakai **bulan penuh** hasil deteksi (bukan jendela
      `min/max tanggal mutasi ± N hari`): transaksi bulan lain tidak dipertimbangkan meski
      selisih harinya kecil.
- [x] Batas bulan dihitung pada **zona waktu profil user**, lalu dikonversi ke UTC, sehingga
      transaksi 30 September 23:30 WIB tetap masuk September walaupun di UTC sudah Oktober.
- [x] Akun yang dipilih user tetap menjadi filter pertama; laporan "transaksi belum ada di
      mutasi" juga dibatasi ke bulan tersebut.
- [x] Bila tidak ada satu pun tanggal yang terbaca, sistem memakai jendela lebar (90 hari
      terakhir) seperti sebelumnya — bukan menolak unggahan.
- [x] Berkas yang rentangnya melebihi 12 bulan dianggap bukan e-statement satu periode; filter
      bulan tidak dipakai (kembali ke jendela lebar) agar tidak menyembunyikan transaksi.
- [x] Baris yang belum cocok disimpan sebagai pending **beserta tanggal & jam aslinya**
      (UTC + snapshot zona waktu).
- [x] Saat user menekan **Konfirmasi**, transaksi baru memakai tanggal & jam dari pending —
      bukan waktu konfirmasi. Hal yang sama berlaku untuk pending `action='update'`.
- [x] Bila mutasi tidak mencetak jam, dipakai **00:00 waktu lokal** pada tanggal mutasi
      (tidak menebak jam).
- [x] Layar pending menampilkan tanggal & jam transaksi yang akan disimpan, sehingga user bisa
      memeriksanya sebelum konfirmasi.
- [x] Jalur pending lama (tanpa tanggal asli) berperilaku seperti sebelumnya: memakai waktu
      konfirmasi.

### FR-11 — Hapus massal transaksi salah dari tab Transaksi

Alasan: setelah Matching Mutasi dipakai, user bisa punya banyak baris yang **salah** (mis.
tercatat di tanggal konfirmasi pada versi 1.4.1) dan harus menghapusnya satu per satu lewat
menu titik-tiga. Itu lambat dan rawan salah pencet.

Kriteria penerimaan:

- [ ] Di tab **Transaksi**, tekan lama satu baris → masuk **mode pilih**: setiap baris
      menampilkan checkbox, tap baris menandai/membatalkan tanda (tidak membuka editor).
- [ ] App bar mode pilih menampilkan jumlah terpilih (`n dipilih`) + tiga aksi: **batal**,
      **Pilih semua** / **Batalkan pilih semua**, dan **hapus**.
- [ ] **Pilih semua** mencentang seluruh baris yang sedang termuat (mengikuti filter/pencarian
      aktif); tombol berubah menjadi "Batalkan pilih semua" saat semuanya tercentang.
- [ ] Tombol hapus nonaktif selama tidak ada baris tercentang dan selama proses berjalan
      (indikator progres kecil di tombol).
- [ ] Menekan hapus memunculkan konfirmasi berisi jumlah baris; setelah disetujui, semua baris
      terpilih dihapus dalam **satu** permintaan dan satu commit di server.
- [ ] Baris yang sudah tidak ada di server (dihapus di perangkat lain) tidak menggagalkan
      proses — dilaporkan sebagai `missing` dan diabaikan.
- [ ] Setelah selesai: mode pilih keluar, daftar dimuat ulang, dan snackbar menampilkan jumlah
      baris yang terhapus.
- [ ] Setiap baris tetap meninggalkan **audit log** `delete` (action yang sama dengan hapus
      tunggal) dengan penanda `bulk`.
- [ ] Hapus tunggal (menu titik-tiga) tetap tersedia dan tidak berubah perilakunya.

---

## 6. Kebutuhan Non-Fungsional

| ID | Kebutuhan |
| --- | --- |
| NFR-1 | Ekstraksi 71 baris dari PDF 6 halaman selesai < 3 detik di CPU container (tanpa LLM). |
| NFR-2 | Memori aman untuk e-statement panjang: halaman PDF diproses satu per satu, bukan sekaligus. |
| NFR-3 | Tidak ada data user yang dikirim ke LLM untuk berkas yang berhasil diparse deterministik. |
| NFR-4 | Semua kegagalan parsing tercatat di log terstruktur dan menghasilkan status HTTP yang tepat (422, bukan 500). |
| NFR-5 | Perubahan tidak memerlukan migrasi database maupun perubahan kontrak API yang merusak. |
| NFR-6 | Perilaku baru dikunci oleh regression test dengan fixture dari berkas nyata (bukan data karangan). |
| NFR-7 | Ekstraksi berbasis warna tidak bergantung pada nama bank mana pun; berkas dengan kolom arah tetap memakai jalur tabel. |

---

## 7. Aturan Bisnis

1. **Nominal selalu positif**; arah dana dinyatakan oleh `direction` (`debit`/`credit`).
2. **Satu baris hanya boleh punya satu arah.** Jika kolom `Keluar` dan `Masuk` terisi keduanya,
   baris dilewati — lebih baik tidak terbaca daripada salah tanda.
3. **Saldo berjalan bukan transaksi.** Kolom paling kanan yang berisi saldo tidak boleh dipakai.
4. **Baris ringkasan bukan transaksi.**
5. **Toleransi nominal** default Rp1,00; **jendela tanggal** default 3 hari. Keduanya dapat
   diatur per permintaan.
6. **Tidak ada auto-commit.** Semua hasil parsing berakhir di Pending.
7. **Satu sumber kebenaran** untuk perhitungan saldo dashboard: fungsi murni di
   `app/lib/core/balance.dart` agar kartu tidak berbeda-beda rumus.
8. **Warna adalah sinyal arah, bukan dekorasi.** Merah = keluar, hijau = masuk. Warna dipakai
   hanya bila tidak ada kolom arah; bila ada baris tak berwarna di halaman itu, arah tidak ditebak.
9. **Kanal input hanya aplikasi.** Tidak ada lagi jalur bot; semua `source` baru ditulis `app`.
10. **Periode berkas menentukan cakupan pencocokan.** Bulan yang dicakup mutasi (bukan jendela
    tanggal) adalah batas transaksi yang boleh dicocokkan; jendela tanggal hanya penentu
    batas hari di dalam bulan itu.
11. **Tanggal transaksi = tanggal kejadian, bukan tanggal input.** Konfirmasi pending hasil
    mutasi wajib memakai tanggal & jam dari mutasi. Jam yang tidak tercetak = `00:00` waktu
    lokal (dilarang menebak jam).
12. **Hapus massal = satu commit.** Menghapus banyak transaksi dilakukan dalam satu permintaan
    dan satu commit agar tidak ada kondisi setengah terhapus; setiap baris tetap mendapat
    audit `delete` sendiri.
13. **Pilih semua hanya berlaku untuk baris yang termuat.** Aksi massal tidak boleh
    menyentuh transaksi di luar filter/pencarian yang sedang aktif.

---

## 8. Kasus Tepi

| Kasus | Keputusan |
| --- | --- |
| Baris bunga tabungan bernilai kecil (Rp 60–119) | Tetap dicatat sebagai `credit` — bagian dari mutasi nyata |
| Baris tanpa tahun (`01 SEP`) | Tahun diambil dari periode statement |
| Statement lintas tahun (Des–Jan) | Tahun diambil dari kemunculan terbanyak; baris yang tanggalnya "mundur" > 6 bulan dianggap tahun berikutnya (*future*) |
| Berkas mutasi mencakup dua bulan (mis. 28 Agu – 3 Sep) | Periode = kedua bulan itu; filter memakai rentang penuh Agustus–September |
| Baris mutasi tanpa jam (hanya tanggal) | Jam transaksi disimpan `00:00` waktu lokal, tanpa menebak |
| Transaksi tercatat 23:30 WIB di hari terakhir bulan | Tetap dianggap bagian bulan tersebut (batas dihitung di zona user, bukan UTC) |
| Deskripsi terpotong bank (`KUDUS &quot;BU`) | Disimpan apa adanya setelah entitas didekode |
| Dua transaksi kembar nominal & tanggal sama | Keduanya dicocokkan satu-satu (tidak boleh satu transaksi dipakai dua kali) |
| Pilih semua saat baru sebagian halaman termuat (pagination) | Hanya baris yang sudah termuat yang ikut terpilih — user diberi tahu lewat jumlah di app bar |
| Sebagian id yang dikirim sudah tidak ada di server | Permintaan tetap sukses; `deleted` berisi jumlah yang benar-benar terhapus, id sisanya masuk `missing` |
| Menghapus 200 transaksi sekaligus | Diterima (batas maksimal 200 id per permintaan); lebih dari itu ditolak 422 |
| Koneksi putus saat hapus massal | Baris di perangkat tidak dihapus dari daftar sebelum server menjawab sukses; snackbar merah muncul |
| PDF berpassword | Gagal dengan pesan "tidak terbaca", bukan 500 |
| Berkas kosong / 0 byte | Ditolak sebagai tidak terbaca |
| Statement hanya berwarna (tanpa kolom arah) | Arah diambil dari warna: merah → debit, hijau → kredit |
| Nominal ada yang hitam di halaman berwarna | Halaman itu tidak dipakai jalur warna; tidak ada arah yang ditebak |
| Tanggal hanya tercetak sekali untuk beberapa baris | Tanggal terakhir dipakai ulang untuk baris berikutnya, termasuk lintas halaman |
| Tahun terpotong ke baris terpisah (`September` / `2026`) | Tahun tetap ikut menjadi bagian deskripsi |

---

## 9. Metrik

| Metrik | Target | Cara ukur |
| --- | --- | --- |
| Rasio baris terbaca pada berkas uji nyata | ≥ 95% | Regression test + total debit/kredit vs ringkasan statement |
| Pemanggilan LLM untuk PDF digital | 0 | Log `mutation_text_parsed` dengan `via="deterministic"` |
| Baris bank berwarna terbaca | 100% (15/15 pada sampel Permata) | Log `mutation_pdf_parsed` dengan `via="color"` |
| Baris tak cocok yang berakhir di Pending | 100% | Assert `created_pending_ids` |
| Galat 500 pada unggahan mutasi | 0 | Log produksi |

---

## 10. Risiko

| Risiko | Dampak | Mitigasi |
| --- | --- | --- |
| Tata letak bank lain berbeda lagi | Fitur "gagal" untuk user bank tertentu | Parser berbasis deteksi header, bukan pola per bank; fixture nyata ditambah tiap kali ada laporan |
| Posisi kolom PDF bergeser antar halaman | Nominal masuk kolom salah | Kolom dihitung per halaman dari header yang berulang; token tanpa kolom jelas dilewati dan diserahkan ke LLM |
| Pemakaian LLM membengkak | Biaya | Deterministik lebih dulu; LLM hanya fallback |
| Deskripsi multi-baris salah gabung | Nama merchant kotor | Regression test dengan fixture asli |
| Bank memakai warna sebagai satu-satunya penanda arah | Seluruh baris tidak terbaca atau arah terbalik | Jalur warna khusus + fixture span asli + aturan "jangan menebak" bila ada nominal tak berwarna |
| Warna dipakai untuk dekorasi (biru/abu) | Arah salah tebak | Hanya merah dan hijau dengan selisih kanal ≥ 40 yang dianggap sinyal; warna lain diabaikan |

---

## 11. Pertanyaan Terbuka

1. Apakah perlu tombol "Setujui semua pending" setelah rekonsiliasi? — *belum, di luar cakupan.*
   **Status 1.2:** tetap di luar cakupan. Konfirmasi dilakukan satu-per-satu agar setiap baris
   sempat diperiksa; yang ditambahkan pada 1.2 hanya jalan masuk ke daftar pending, bukan
   aksi massal.
2. Apakah saldo awal akun sebaiknya bisa diisi saat rekonsiliasi pertama? — *belum, di luar cakupan.*
3. Apakah Pending perlu menampilkan sumber unggahan (nama berkas)? — *belum, di luar cakupan.*
   **Status 1.2:** nama berkas sudah tersimpan di `raw_input` (mis.
   `Matching Mutasi — mutasi.csv`) dan dipakai sebagai penanda asal baris, namun belum
   ditampilkan sebagai kolom di UI.
4. Berapa lama pending sebaiknya disimpan bila user menutup aplikasi di tengah konfirmasi?
   — *jawaban 1.2: 24 jam (`expires_minutes=60*24`) lalu dibersihkan otomatis.*

---

## 12. Riwayat Versi

| Versi | Tanggal | Perubahan |
| --- | --- | --- |
| 1.4 | 2026-11-02 | Hapus massal transaksi: mode multi-pilih, tombol **Pilih semua**, satu commit di server, audit per baris (FR-11) |
| 1.3 | 2026-11-02 | Akurasi waktu: bulan berkas mutasi dideteksi otomatis dan menjadi dasar filter transaksi (FR-10a); transaksi hasil konfirmasi memakai tanggal & jam asli mutasi (FR-10b) |
| 1.2 | 2026-11-01 | Jalan keluar dari layar Matching Mutasi: tombol **Matching** di bawah layar hasil + layar `PendingReviewScreen` (FR-8), serta kebersihan tabel `pending_transactions` — pending kedaluwarsa & pending tak terkonfirmasi dihapus otomatis (FR-9) |
| 1.1 | 2026-10-30 | Dukungan bank berwarna (Permata: merah = keluar, hijau = masuk) + penghapusan bot Telegram dari lingkup produk |
| 1.0 | 2026-10-29 | PRD awal untuk perbaikan Matching Mutasi pada e-statement Indonesia + perbaikan filter Total Balance |
