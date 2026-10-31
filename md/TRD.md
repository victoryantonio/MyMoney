# TRD — Matching Mutasi: Parser E-Statement Deterministik & Filter Saldo

| Field | Isi |
| --- | --- |
| Produk | MyMoney |
| Fitur | Matching Mutasi (`POST /api/mutations/match`), Total Balance dashboard |
| Versi dokumen | 1.4 |
| Tanggal | 2026-11-02 |
| Status | Siap implementasi |
| Dokumen terkait | `md/PRD.md`, `backend/app/core/mutation_matcher.py`, `app/lib/core/balance.dart` |
| Prasyarat rilis | Migrasi head `0013_pending_transaction_date` — **wajib** dijalankan (`docker compose exec -T backend alembic upgrade head`) sebelum klien baru dipakai |
| Perubahan 1.4 | Endpoint hapus massal `POST /api/transactions/bulk-delete` + mode multi-pilih di tab Transaksi (FR-11 PRD) |
| Perubahan 1.3 | Deteksi periode berkas + filter transaksi per bulan (local → UTC) + penyimpanan tanggal & jam asli mutasi sampai konfirmasi |
| Perubahan 1.1 | Jalur ekstraksi berbasis **warna teks** untuk statement tanpa kolom keluar/masuk (Permata); penghapusan bot Telegram |

---

## 1. Ringkasan

Perbaikan ini menyentuh dua area yang tidak saling bergantung:

1. **Backend** — pipeline ekstraksi mutasi di `backend/app/core/mutation_matcher.py` diganti dari
   "andalkan LLM" menjadi "parser deterministik lebih dulu, LLM sebagai fallback". Perubahan
   terbesar ada pada penguraian *text layer* PDF: rekonstruksi teks dari koordinat kata, deteksi
   header kolom per halaman, penggabungan deskripsi multi-baris, dan dukungan dua varian tata letak
   bank Indonesia. Pada versi 1.1 ditambahkan **jalur ketiga berbasis warna teks** untuk bank yang
   tidak mencetak kolom arah dana sama sekali (Permata).
2. **Frontend** — nilai `Total Balance` pada `app/lib/screens/dashboard_screen.dart` dihitung
   ulang agar mengikuti filter akun, dengan logika diekstrak ke `app/lib/core/balance.dart`
   (fungsi murni, dapat diuji terpisah).
3. **Penyempitan lingkup** — bot Telegram (`bot/`, `telegram_webhook.py`, `telegram_linking.py`,
   `telegram_service.py`, model `telegram_link`/`processed_update`) dihapus. Nilai `source` baru
   hanya `app`; nilai lama `telegram` **tetap diizinkan** oleh CHECK constraint agar baris historis
   di DB produksi tidak melanggar.

Tidak ada perubahan skema database, tidak ada perubahan kontrak API yang merusak klien.

---

## 2. Arsitektur Saat Ini

```text
Flutter (mutation_match_screen.dart)
   │  multipart: file + account_id + amount_tolerance + date_window_days
   ▼
POST /api/mutations/match          app/api/mutations.py  (rate limit 10/menit)
   │
   ├─ is_text?  ──────────────► parse_mutation_text()  ─┐
   ├─ is_pdf_upload? ─────────► parse_mutation_pdf()  ──┤
   │                              ├─ parse_colored_statement_pdf()  (jalur warna)
   │                              ├─ parse_mutation_text()          (kolom/teks)
   │                              └─ parse_mutation_image()         (scan/vision)
   └─ else (image) ───────────► parse_mutation_image() ─┤
                                                        │ MutationExtraction
                                                        ▼
                              resolve_upload_account()  (user → hint → None)
                                                        ▼
                              find_matches()  ──► matches / unmatched / unmatched_txs
                                                        ▼
                              _create_pendings() ──► pending_transaction (BELUM commit transaksi)
                                                        ▼
                                   MutationMatchResponse (JSON)
```

Pemisahan tanggung jawab:

| Lapisan | Berkas | Tanggung jawab |
| --- | --- | --- |
| Transport | `app/api/mutations.py` | Validasi ukuran/MIME, rate limit, pemilihan jalur, status HTTP, audit log |
| Ekstraksi | `app/core/mutation_matcher.py` | Teks → baris mutasi (deterministik/LLM), PDF → teks/gambar |
| Pencocokan | `app/core/mutation_matcher.py` | Aturan nominal/tanggal/arah/akun, greedy one-to-one |
| Persistensi | `app/core/pending_service.py` | Membuat `pending_transaction` |
| Presentasi | `app/lib/screens/mutation_match_screen.dart` | Unggah, progres, ringkasan, daftar hasil |

---

## 3. Keputusan Desain

| # | Keputusan | Alternatif yang ditolak | Alasan |
| --- | --- | --- | --- |
| D1 | Parser deterministik didahulukan untuk berkas ber-text-layer | Selalu memakai LLM | Hasil deterministik, gratis, cepat, dapat diuji dengan angka pasti (total harus sama dengan ringkasan statement) |
| D2 | Teks PDF direkonstruksi dari `page.get_text("words")` | `page.get_text("text")` langsung | Ekstraksi biasa menyatukan kolom dengan spasi tak beraturan sehingga kolom angka tidak lagi sejajar dengan header |
| D3 | Pemetaan token → kolom memakai **irisan karakter** terbesar | Titik mulai token, atau jarak ke tengah header | Kolom angka rata kanan; token sering dimulai di kiri judul kolomnya |
| D4 | Deteksi header berbasis *peran* (`tanggal`, `keterangan`, `keluar`, `masuk`, `saldo`, `mutasi`) | Pola khusus per bank (`if bank == "SeaBank"`) | Bank baru tidak butuh kode baru; cukup tambahkan sinonim header |
| D5 | Baris dengan dua arah terisi dilewati | Tebak salah satu | Salah tanda dana merusak data keuangan; lebih baik diserahkan ke LLM/abaikan |
| D6 | `account_hint` = nama bank yang dikenal, bukan baris bebas | Ambil baris teks pertama yang mengandung "REKENING" | Menghindari hint berupa nomor rekening atau teks pemasaran |
| D7 | `balance.dart` berisi fungsi murni | Logika di dalam `State` widget | Dapat diuji tanpa `WidgetTester`, dipakai ulang oleh kartu lain |
| D8 | Warna teks dibaca sebagai sinyal arah (`get_text("dict")` → `spans.color`) | Menambah pola khusus `if bank == "Permata"` | Beberapa bank tidak mencetak kolom arah sama sekali; warna adalah satu-satunya informasi yang tersisa. Jalur ini bank-agnostik |
| D9 | Bila satu halaman memuat nominal `Rp` **tak berwarna**, seluruh halaman dilewati jalur warna | Menganggap tak berwarna = debit, atau menebak dari saldo | Arah salah lebih merusak daripada baris hilang. Baris hilang masih masuk Pending/fallback; arah salah langsung merusak saldo |
| D10 | Tanggal diambil dari label terdekat **sebelum** baris nominal, lalu dibawa (*carry*) ke baris & halaman berikutnya | Mewajibkan tanggal di setiap baris | Statement blok-per-tanggal (Permata) hanya mencetak tanggal sekali untuk banyak transaksi |

---

## 4. Pipeline Ekstraksi (target)

```text
berkas masuk
   │
   ▼
┌──────────────────────────────────────────────────────────────┐
│ 1. Klasifikasi                                               │
│    is_pdf_upload(magic %PDF- | mime | ekstensi)              │
│    is_text(mime text/* , application/csv | .csv/.txt/.tsv)   │
└──────────────────────────────────────────────────────────────┘
   │ PDF                                     │ teks             │ gambar
   ▼                                         ▼                  ▼
extract_pdf_text()                     parse_statement_text()  vision LLM
   │
   ├─ parse_colored_statement_pdf()  ── rows > 0 ──► MutationExtraction(via="color")
   │
   ├─ chars ≥ MIN_PDF_TEXT_CHARS (40)?
   │      ya  → parse_mutation_text(text)
   │      no  → render_pdf_pages() 1 halaman/iterasi → vision LLM per halaman
   ▼
parse_mutation_text(text)
   │
   ├─ parse_statement_text(text)  ── rows > 0 ──► MutationExtraction(via="deterministic")
   │
   └─ rows == 0 ──► call_llm(TEXT_MODELS, _TEXT_SYSTEM_PROMPT) ──► via="llm"
                     └─ None ──► HTTP 422 "Mutasi tidak terbaca…"
```

### 4.1 `extract_pdf_text()`

1. `fitz.open(stream=data, filetype="pdf")`.
2. Per halaman: `_layout_text(page.get_text("words"))`.
3. Jika `words` gagal → fallback `page.get_text("text")` untuk halaman itu.
4. Exception apa pun → log `mutation_pdf_text_failed`, kembalikan `""` (tidak boleh 500).

### 4.2 `_layout_text(words)` — rekonstruksi kolom

Tujuan: menghasilkan teks monospace-ish di mana posisi karakter mencerminkan posisi x asli,
sehingga header dan nilai pada baris berbeda tetap sejajar.

```text
left       = min(x0) seluruh halaman
char_width = median((x1 - x0) / len(word)), dijepit ke [2.0, 20.0]
             → dihitung GLOBAL per halaman, bukan per baris
pengelompokan baris: |y0 - y_last| ≤ 2.5 pt
kolom karakter = round((x0 - left) / char_width)
```

> `left` dan `char_width` **wajib** global per halaman. Versi pertama menghitungnya per baris;
> akibatnya lebar karakter tiap baris berbeda dan kolom angka bergeser relatif terhadap header.

### 4.3 `parse_statement_text(text)`

Urutan percobaan:

1. Delimiter tabel: `|`, lalu tab, lalu `;` (minimal 2 baris memuat delimiter), terakhir `,`
   hanya jika ≥ 3 koma pada ≥ 2 baris (mencegah teks prosa dianggap CSV).
2. Jika `_parse_delimited_statement()` menghasilkan baris → selesai.
3. Jika tidak → `_parse_whitespace_statement()`.

### 4.4 Jalur delimited

- `_find_header(cells)` memetakan indeks sel → `_ColumnMap(date, description, debit, credit, amount, balance)`.
  Header sah bila punya `description` **atau** `date` **dan** salah satu dari `debit/credit/amount`.
- `_header_role()` memakai urutan prioritas: `balance → debit → credit → amount → date → description`
  agar `SALDO AKHIR` tidak terbaca sebagai kolom nominal.
- `_row_to_mutation()`:
  - `debit` dan `credit` sama-sama terisi → **tolak**.
  - `amount` tunggal → tanda negatif = debit, positif = credit.
  - deskripsi kosong atau cocok `_SUMMARY_PREFIXES` → tolak.
- Baris pemisah markdown (`|---|:--:|`) dilewati.

### 4.5 Jalur whitespace (text layer PDF)

1. `_role_spans(line)` mencari kata header pada baris lalu menyimpan `(start, end)` karakter per
   peran. Baris header diperbarui setiap kali ditemukan (header berulang di tiap halaman).
2. Baris dianggap awal baris transaksi bila cocok `_LEADING_DATE_RE`:
   `yyyy-mm-dd`, `dd/mm/yyyy`, `dd-mm-yy`, atau `01 SEP [2026]`.
3. `_trailing_amount_tokens(rest)` mengambil deret token numerik bersambung di **akhir** baris
   (kolom angka rata kanan), mengembalikan `(start, end, value)`.
4. `_match_role(start, end, spans)` memilih peran dengan irisan karakter terbesar; bila tidak ada
   irisan sama sekali, pakai kolom terdekat yang mulai di kiri token.
5. Hanya token yang jatuh di `debit` **atau** `credit` yang dihitung. Jika jumlahnya ≠ 1 → baris
   dilewati (diserahkan ke LLM). Kolom `balance` tidak pernah dipakai sebagai nominal.
6. `_normalize_date(..., default_year)` mengisi tahun dari `_detect_year(text)`.

### 4.6 Jalur warna (statement tanpa kolom keluar/masuk)

Dijalankan **sebelum** jalur tabel, karena `extract_pdf_text()` membuang warna: teks hasil
rekonstruksi kolom tidak lagi membawa informasi merah/hijau, sehingga statement seperti Permata
hanya menghasilkan 0 baris di jalur biasa.

```text
parse_colored_statement_pdf(data, text=None)
  for tiap halaman:
      spans      = _page_spans(page)          # flattened spans dari page.get_text("dict")
      amounts    = spans dengan teks cocok _CURRENCY_SPAN_RE dan _span_amount() sukses
      colors     = [_color_direction(s.color) for s in amounts]
      if ada amount yang arahnya None → halaman DILEWATI (jangan menebak)
      labels     = spans tanggal (len ≤ 20, _normalize_date() berhasil)
      ignored    = id(amount) ∪ id(label)
      deskripsi  = span lain (len ≥ 2) yang lolos _text_candidate() atau _YEAR_ONLY_RE
      untuk tiap amount:
          date  = label terdekat dengan label_y ≤ amount.center, else carried_date
          parts = deskripsi dengan |center − amount.center| ≤ max(line_height·3, 12)
          row   = ParsedMutation(date, _join_parts(parts urut (center, x)), amount, arah)
```

Aturan penting:

1. **`_color_direction(color)`** — merah bila `R − min(G,B) ≥ 40` dan `R ≥ max(G,B)`; hijau bila
   `G − min(R,B) ≥ 40` dan `G ≥ max(G,B)`; selain itu `None`. Ambang 40 menolak biru/abu/hitam
   yang hanya dipakai sebagai dekorasi.
2. **Halaman dengan nominal tak berwarna dilewati seluruhnya.** Bukan per baris: satu nominal
   hitam berarti statement tidak konsisten, dan menebak arah merusak saldo.
3. **Label tanggal tidak ikut menjadi deskripsi.** Id span label dikumpulkan pada lintasan yang
   sama lalu dimasukkan ke `ignored_ids`; tanpa ini deskripsi menjadi `30 September Biaya Adm …`.
4. **Tahun terpotong tetap dipertahankan.** PyMuPDF sering memecah `September 2026` menjadi dua
   span; `_text_candidate("2026")` menolaknya, sehingga `_YEAR_ONLY_RE` (4 digit, 19xx/20xx)
   diizinkan khusus di jalur ini.
5. **`carried_date`** bertahan lintas halaman: blok tanggal Permata berlanjut ke halaman 2 tanpa
   label baru.
6. Jika tidak ada baris berwarna sama sekali, fungsi mengembalikan `[]` dan
   `parse_mutation_pdf()` lanjut ke jalur teks seperti biasa.

---

## 5. Celah yang Ditemukan pada Berkas Nyata

Diuji pada tiga e-statement asli di `receipts/`:

| Berkas | Bank | Halaman | Hasil parser saat ini |
| --- | --- | --- | --- |
| `DOC-20261011-WA0026.pdf` | SeaBank | 6 | **17 baris**, debit 1.747.305, kredit 0 |
| `0581588762_SEP_2026.pdf` | BCA | 3 | **0 baris** (gagal total) |
| `Transaction History - Permata ….pdf` | Permata | 2 | **0 baris** di jalur teks (warna hilang) |

Nilai yang benar pada statement SeaBank: **71 baris**, debit **3.288.616**, kredit **2.553.554**,
saldo akhir **1.009.324**.

### G-1 — Deskripsi multi-baris berada **di atas** baris tanggal (SeaBank)

Bentuk nyata di text layer:

```text
                    Bunga Tabungan
01 SEP                                                                      119           1.744.505
                    Bunga
                    NASI PINDANG
01 SEP             KUDUS &quot;BU                   18.000                               1.726.505
                    Pembayaran
```

Baris jangkar adalah baris **tanggal + nominal**. Nama merchant ada satu baris di atasnya, dan
kata seperti `Pembayaran`/`Bunga`/`Transfer` ada di bawahnya. Parser sekarang hanya memakai teks
di antara tanggal dan token pertama (yaitu bagian di baris jangkar saja), sehingga
keterangan menjadi `KUDUS &quot;BU` dan sebagian besar baris tidak punya deskripsi.

**Perbaikan:** kumpulkan baris-baris "yatim" (tanpa tanggal, tanpa token nominal, hanya teks di
kolom keterangan) sebagai kandidat deskripsi; saat menemukan baris jangkar, gabungkan
`kandidat_sebelum[-1]` + teks jangkar + `kandidat_sesudah` sesuai kolom keterangan.

### G-2 — Kolom `MASUK` tidak terbaca

Hanya 17 dari 71 baris terbaca, dan semuanya debit. Baris kredit (bunga tabungan, transfer DANA
masuk) memiliki token tepat di bawah header `MASUK (IDR)`, namun `_trailing_amount_tokens()` hanya
memindai token yang bersambung di **akhir** baris; pada baris kredit, saldo di kanan ikut terbaca
lalu `_match_role` gagal menemukan irisan untuk token yang lebih kiri.

**Perbaikan:** pindai token numerik di seluruh baris setelah tanggal (bukan hanya ekor
bersambung), lalu klasifikasikan tiap token ke kolomnya. Abaikan token yang jatuh di `balance`.

### G-3 — `account_hint` salah

Saat ini menghasilkan `"901046266356   Hubungi kami"` karena pola `NO. REKENING` dianggap hint.
**Perbaikan:** hint hanya dari daftar bank yang dikenal (`SeaBank`, `BCA`, …) atau pola
`Bank : <nama>`; jika tidak ada, `None`. `resolve_upload_account()` tetap menjadi penentu akhir.

### G-4 — Entitas HTML pada text layer

`KUDUS &quot;BU` berasal dari font encoding bank.
**Perbaikan:** `html.unescape()` pada deskripsi (dan rapikan spasi ganda).

### G-5 — Tata letak BCA belum dikenali

```text
  TANGGAL                         KETERANGAN                        CBG              MUTASI                       SALDO
     01/09      SALDO AWAL                                                                                                732,783.13
     01/09      KARTU KREDIT/PL          0831 WSID952710312                               159,227.00 DB                  573,556.13
                TANGGAL  :31/08          0100 BCA CARD
     05/09      TRSF E-BANKING CR        0509/FTSCY/WS95051                               19,000.00                       260,541.13
```

Karakteristik:

- Satu kolom nominal `MUTASI`, arah ditentukan akhiran `DB` / `CR`.
- Tanggal `dd/mm` tanpa tahun; tahun dari `PERIODE : SEPTEMBER 2026` (nama bulan panjang).
- `SALDO` sering kosong (hanya dicetak saat berubah) → tidak boleh jadi penanda baris.
- Deskripsi berlanjut di baris tanpa tanggal (indentasi sama dengan kolom `KETERANGAN`).
- Header `TANGGAL … KETERANGAN … MUTASI … SALDO` berulang tiap halaman.

**Perbaikan:** tambahkan peran `amount_direction` untuk header `MUTASI`, dukung sufiks `DB`/`CR`
pada token nominal, dan perlakukan `_detect_year` agar membaca `PERIODE : <BULAN> <TAHUN>`.

### G-6 — Arah dana hanya dikodekan warna (Permata)

```text
NASABAH CONTOH                      Biaya Adm Bulanan Kartu 9999 September
                                    2026
 30 September
                                    Rp 5.000                 ← merah
                                    PB Bagi Hasil
                                    Rp 79                    ← hijau
```

Karakteristik:

- **Tidak ada** kolom `KELUAR`/`MASUK`/`MUTASI`, dan tidak ada akhiran `DB`/`CR`.
- Arah hanya terbaca dari warna: `#DD0C25` (merah) = keluar, `#008873` (hijau) = masuk.
- Tanggal dicetak sekali per blok, bukan di setiap baris; nominal ada di baris terpisah dari
  deskripsi.
- `extract_pdf_text()` mengabaikan warna → semua baris kehilangan arah → 0 baris.
- `_detect_account_hint()` sempat mengembalikan `SeaBank` karena deskripsi transfer menyebut
  `PT BANK SEABANK INDONESIA`; hint diperbaiki dengan menghitung **kemunculan terbanyak**.

**Perbaikan:** jalur `parse_colored_statement_pdf()` (§4.6) + `_detect_account_hint()` berbasis
frekuensi.

Hasil pada berkas asli: **15 baris**, debit **7.924.015,00**, kredit **8.209.830,00**, hint
`Permata`, LLM tidak pernah dipanggil.

---

## 6. Rencana Perubahan Kode

### 6.1 `backend/app/core/mutation_matcher.py`

| Simbol | Perubahan |
| --- | --- |
| `_MONTH_NAMES` (baru) | Nama bulan panjang (januari…desember) → `_MONTH_ABBREV` yang sudah ada |
| `_detect_year()` | Tambah pola `PERIODE ... <BULAN> <TAHUN>` sebelum fallback frekuensi |
| `_detect_account_hint()` | Hapus pola `NO. REKENING`; hanya `Bank : X` + daftar bank dikenal |
| `_clean_description()` (baru) | `html.unescape`, buang spasi ganda, buang `-` tepi, batasi 200 karakter |
| `_AMOUNT_HEADERS` | Tambah `"mutasi"` sebagai peran `amount_direction` |
| `_has_direction_suffix()` (baru) | `"159,227.00 DB"` → (`debit`, 159227.00); `CR`/`KR` → `credit` |
| `_numeric_tokens(line, after)` (baru) | Semua token numerik setelah offset tertentu, dengan (`start`, `end`, `value`) |
| `_role_spans()` | Simpan juga `amount_direction` |
| `_StatementAccumulator` (baru) | Menyimpan kandidat deskripsi multi-baris; menghasilkan `ParsedMutation` saat baris jangkar ditemukan |
| `_parse_whitespace_statement()` | Ditulis ulang memakai akumulator + `_numeric_tokens` + sufiks arah |
| `_parse_delimited_statement()` | Pakai `_clean_description()`; dukung kolom `mutasi` bersufiks |
| `_detect_account_hint()` | Hitung kemunculan tiap bank dikenal; ambil yang terbanyak (Permata ≠ SeaBank) |
| `_PdfSpan` (baru) | `text`, `x`, `y`, `height`, `color` + properti `center` |
| `_page_spans()` (baru) | Ratakan span dari `page.get_text("dict")` menjadi `list[_PdfSpan]` |
| `_span_amount()` (baru) | Span `Rp 5.000` → (`Decimal("5000")`, `"Rp 5.000"`) |
| `_color_direction()` (baru) | Hex PDF int → `"debit"` (merah) / `"credit"` (hijau) / `None` |
| `_YEAR_ONLY_RE` (baru) | Izinkan tahun terpotong (`2026`) menjadi bagian deskripsi jalur warna |
| `parse_colored_statement_pdf()` (baru) | Jalur warna penuh, dipanggil sebelum jalur tabel |
| `parse_mutation_pdf()` | Urutan baru: warna → teks/tabel → render + vision |

Bentuk akumulator yang direncanakan:

```python
@dataclass
class _PendingRow:
    date: str | None = None
    parts: list[str] = field(default_factory=list)   # potongan deskripsi
    amount: Decimal | None = None
    direction: str | None = None
```

Algoritma jalur whitespace:

```text
for setiap baris:
    perbarui spans bila baris adalah header
    if baris punya tanggal:
        selesaikan _PendingRow sebelumnya (bila lengkap → ParsedMutation)
        mulai _PendingRow baru dengan tanggal tersebut,
        tambahkan teks kolom keterangan pada baris ini ke parts,
        klasifikasikan token nominal → amount + direction
    else:
        if spans ada dan baris punya teks di kolom keterangan:
            if _PendingRow aktif: tambahkan ke parts
            else: simpan sebagai kandidat pra-deskripsi
        elif baris punya token nominal di kolom debit/credit/amount:
            selesaikan sebelumnya, mulai baris baru tanpa tanggal (jarang)
selesaikan _PendingRow terakhir
buang baris tanpa amount/direction atau yang deskripsinya cocok _SUMMARY_PREFIXES
```

Kandidat pra-deskripsi: saat baris jangkar ditemukan, ambil **kandidat terakhir** (paling dekat)
sebagai awalan deskripsi; sisa kandidat dibuang (biasanya judul kolom atau teks halaman).
Ini menangani bentuk SeaBank (`Nama Merchant` di atas baris tanggal) sekaligus menjaga
deskripsi di baris jangkar itu sendiri (mis. `KUDUS &quot;BU`).

### 6.2 `app/lib/core/balance.dart` — sudah dibuat, tidak berubah

```dart
double totalBalanceFor(Iterable<AccountModel> accounts, Set<String>? selectedAccountIds);
String? balanceScopeLabel(Iterable<AccountModel> accounts, Set<String>? selectedAccountIds);
```

Kontrak:

| `selectedAccountIds` | Hasil |
| --- | --- |
| `null` | jumlah seluruh akun |
| himpunan berisi | jumlah akun yang id-nya ada di himpunan (id tak dikenal diabaikan) |
| himpunan kosong | `0` |
| daftar akun kosong | `0` |

`balanceScopeLabel` → `null` bila `null`; `'Tidak ada akun dipilih'` bila kosong; `account.label`
bila satu; `'{n} akun terpilih'` bila lebih.

### 6.3 `app/lib/screens/dashboard_screen.dart`

- `_totalBalance` → `totalBalanceFor(_accounts, _activeAccountFilter)`
- `_balanceSubtitle` → `balanceScopeLabel(...)`, dirender `_BalanceCard` sebagai baris kecil di
  bawah nominal (`maxLines: 1`, `TextOverflow.ellipsis`, warna `onSurfaceVariant`).

---

## 7. Kontrak API

### `POST /api/mutations/match`

**Auth:** JWT Supabase (`require_active_user`). **Rate limit:** `10/minute` per IP.

Request (`multipart/form-data`):

| Field | Tipe | Wajib | Catatan |
| --- | --- | --- | --- |
| `file` | UploadFile | ya | `image/*`, `text/*`, `.csv/.txt/.tsv`, atau PDF; maks 20 MB |
| `account_id` | UUID | tidak | Kosong = cocokkan lintas akun |
| `amount_tolerance` | string desimal | tidak | Default `1.00`, minimal 0 |
| `date_window_days` | int | tidak | Default `3`, dijepit `0…30` |

Response `200` — `MutationMatchResponse`:

```json
{
  "account_id": "…|null",
  "account_name": "Tabungan SeaBank|null",
  "source_description": "SeaBank|null",
  "total_mutations": 71,
  "matched_count": 12,
  "unmatched_mutation_count": 59,
  "unmatched_transaction_count": 3,
  "matches": [
    {
      "mutation": {"date": "2026-09-01", "time": null, "description": "NASI PINDANG KUDUS \"BU",
                   "amount": "18000", "direction": "debit"},
      "transaction_id": "…", "transaction_type": "expense",
      "transaction_amount": "18000", "transaction_date": "2026-09-01T00:00:00+00:00",
      "transaction_merchant": "Nasi Pindang", "day_diff": 0, "amount_diff": "0"
    }
  ],
  "unmatched_mutations": [ /* ParsedMutation[] */ ],
  "created_pending_ids": ["…"]
}
```

Galat:

| Status | Penyebab | Body |
| --- | --- | --- |
| `413` | > 20 MB | `File terlalu besar (maks 20 MB)` |
| `415` | Tipe tidak didukung | `Format tidak didukung. Unggah …` |
| `422` | Berkas kosong | `Empty file` |
| `422` | Tidak ada baris terbaca | `Mutasi tidak terbaca — pastikan berkas memuat daftar transaksi (tanggal, keterangan, nominal) lalu coba lagi.` |
| `429` | Lewat rate limit | standar slowapi |

### Pending API — *baru di 1.2*

Modul: `backend/app/api/pending.py` + `backend/app/schemas/pending.py`.
**Auth:** JWT Supabase (`require_active_user`) di semua endpoint. Semua query dibatasi
`user_id = current_user.id` (isolasi data, tanpa endpoint lintas user).

| Method | Path | Rate limit | Keterangan |
| --- | --- | --- | --- |
| `GET` | `/api/pending` | — | Daftar baris aktif (belum kedaluwarsa). `limit` default 200, `1…200`. Urut `created_at DESC`. |
| `GET` | `/api/pending/count` | — | `{"count": n}` — baris aktif milik user. Belum dipakai UI 1.2 (disediakan untuk badge/indikator berikutnya). |
| `POST` | `/api/pending/{id}/confirm` | `30/minute` | Baris → transaksi nyata (lewat `transaction_service`, jadi audit log ikut tercatat). |
| `POST` | `/api/pending/{id}/cancel` | `30/minute` | Baris dihapus; tidak ada transaksi dibuat. |

`PendingTransactionResponse` — field: `id`, `action`, `type`, `total_amount`,
`category_id`, `category_name`, `account_id`, `account_name`, `merchant`, `note`,
`source`, `confidence`, `raw_input`, `target_transaction_id`, `created_at`,
`expires_at`. `category_name` dan `account_name` diresolusi lewat satu query
`Account.id, Account.account_name` untuk semua baris (menghindari N+1), dan
`category` dimuat dengan `selectinload`.

`confirm` mengembalikan `PendingConfirmResponse`:
`{pending_id, transaction_id, action, type, total_amount}`.
`cancel` mengembalikan `PendingCancelResponse`: `{pending_id, cancelled: true}`.

Galat:

| Status | Penyebab | Body |
| --- | --- | --- |
| `401` | JWT tidak ada/invalid | `Could not validate credentials` |
| `404` | Baris tidak ada / milik user lain | `Transaksi pending tidak ditemukan.` |
| `404` | `target_transaction_id` sudah tidak ada | `Transaksi tujuan sudah tidak ada.` |
| `410` | `expires_at` sudah lewat | `Transaksi pending sudah kedaluwarsa — unggah ulang mutasi untuk memprosesnya.` |
| `429` | Lewat rate limit | standar slowapi |

Catatan implementasi: `pending_action` dibaca **sebelum** memanggil service, karena
`confirm_pending_transaction()` menghapus baris pending di dalam transaksi DB yang sama.

### Kebersihan tabel `pending_transactions` — *baru di 1.2*

Dua fungsi di `app/core/pending_service.py`:

| Fungsi | Cakupan WHERE | Commit? | Kapan dipanggil |
| --- | --- | --- | --- |
| `purge_expired_pendings(db, user_id=None)` | `expires_at IS NOT NULL AND expires_at <= now()` (+ `user_id` bila diisi) | ya | `GET /api/pending`, `GET /api/pending/count`, `POST /api/mutations/match`, dan startup backend (tanpa `user_id` → seluruh tabel) |
| `purge_matching_pendings(db, user_id)` | `user_id = ?` AND `raw_input IS NOT NULL` AND `raw_input LIKE 'Matching Mutasi%'` | **tidak** (digabung commit pemanggil) | `POST /api/mutations/match` sebelum membuat pending baru |

Konstanta `MATCHING_MUTASI_RAW_PREFIX = "Matching Mutasi"` menjaga pembersihan tetap sempit:
baris pending dari alur lain (mis. riwayat percakapan Telegram lama) tidak pernah ikut
terhapus, karena `raw_input`-nya tidak memakai prefiks itu.

**Urutan yang dijamin** di `mutations.py`:

```text
baca berkas → parse (LLM/deterministik) → gagal? → 422 (tidak ada yang dihapus)
                                       → sukses → purge_expired_pendings
                                                → purge_matching_pendings
                                                → _create_pendings (commit bersama)
```

Pembersihan sengaja diletakkan **setelah** parse berhasil: unggahan yang gagal (berkas kosong
atau tak terbaca) tidak boleh menghapus pending yang masih berlaku. `purge_matching_pendings`
tidak commit sendiri karena hasilnya harus satu commit dengan pembuatan pending baru —
kalau proses mati di tengah, tabel tetap konsisten (pending lama masih ada, bukan hilang
tanpa pengganti).

Sisi klien, `MutationMatchScreen` mengirim `cancelPending()` (best-effort) untuk setiap
`created_pending_ids` bila user keluar lewat tombol back pada layar hasil (`PopScope` +
`canPop: false`), atau saat `_reset()`. Ini murni optimasi UX agar tabel langsung bersih;
jaring pengaman sebenarnya ada di backend (kedaluwarsa 24 jam + pembersihan di atas).

### `POST /api/transactions/bulk-delete` — *baru di 1.4*

**Auth:** JWT Supabase (`require_active_user`). **Rate limit:** `20/minute` per IP.
Modul: `backend/app/api/transactions.py` → `backend/app/core/transaction_service.py`.

Request (`application/json`):

```json
{ "ids": ["5f1c…", "9a02…"] }
```

| Field | Tipe | Wajib | Batas |
| --- | --- | --- | --- |
| `ids` | `list[UUID]` | ya | `min_length=1`, `max_length=200` (Pydantic → 422 di luar batas) |

Response `200` — `TransactionBulkDeleteResponse`:

```json
{ "deleted": 2, "missing": [] }
```

Semantik:

- `deleted` = jumlah baris yang **benar-benar** dihapus pada commit ini.
- `missing` = id yang tidak ditemukan **atau** milik user lain. Keduanya diperlakukan sama
  (tidak membocorkan keberadaan transaksi user lain) dan **tidak** menggagalkan permintaan.
- Duplikat di `ids` dinormalkan lewat `dict.fromkeys` sehingga satu baris tidak dihapus dua kali.
- Filter query selalu `Transaction.user_id == current_user.id` — tidak ada jalur lintas user.

Implementasi service:

```python
def delete_transactions_internal(db, transactions: Sequence[Transaction],
                                 audit_ip_address: str | None = None) -> int:
    if not transactions:
        return 0
    for transaction in transactions:
        record_audit(db, ..., action="delete", entity_type="transaction",
                     entity_id=transaction.id,
                     old_value={"type": ..., "total_amount": str(...),
                                "category_id": str(...), "note": ...,
                                "bulk": True},
                     source=transaction.source, ip_address=audit_ip_address)
        db.delete(transaction)
    db.commit()          # SATU commit untuk seluruh batch
    return len(transactions)
```

Alasan desain:

1. **Satu commit.** Kalau commit per baris, kegagalan di tengah membuat user melihat sebagian
   terhapus dan sebagian tidak — sulit dijelaskan di UI.
2. **`db.flush()` di dalam `record_audit`.** `record_audit()` memakai `flush()` (tanpa commit);
   pemanggil yang menentukan batas transaksi DB. Pola yang sama sudah dipakai hapus tunggal.
3. **`TransactionItem` ikut terhapus** lewat `cascade="all, delete-orphan"` pada relasi model;
   tidak perlu query terpisah.
4. **Audit per baris, bukan satu baris "bulk".** Kebutuhan forensik tetap per transaksi; penanda
   `bulk: true` hanya metadata tambahan.

Sisi klien (`app/lib/screens/transactions_screen.dart`):

| State | Fungsi |
| --- | --- |
| `_selectionMode`, `_selectedIds`, `_bulkDeleting` | status mode pilih, himpunan id, penanda proses |
| `_enterSelection` / `_exitSelection` / `_toggleSelected` | long-press masuk mode; membatalkan tanda terakhir otomatis keluar mode |
| `_allSelected` / `_toggleSelectAll` | tombol **Pilih semua** ↔ **Batalkan pilih semua** |
| `_confirmBulkDelete` | dialog konfirmasi → `apiClient.bulkDeleteTransactions` → hapus baris lokal → `_load()` |

`_load()` memangkas `_selectedIds` ke id yang masih terlihat setelah refresh — mencegah id
"hantu" ikut terkirim saat filter berubah. Aksi hapus dinonaktifkan selama `_bulkDeleting`
untuk mencegah permintaan ganda.

Tidak ada perubahan skema/migrasi: endpoint hanya memakai tabel `transactions` dan
`audit_logs` yang sudah ada.

---

## 8. Model Data

Tidak ada perubahan skema. Tabel yang dipakai:

| Tabel | Peran |
| --- | --- |
| `transaction` | Sumber kandidat pencocokan (`account_id`, `to_account_id`, `total_amount`, `transaction_date`, `type`) |
| `pending_transaction` | Tujuan baris tak cocok (`amount`, `type`, `description`, `account_id`, `category_id`, `source`) |
| `category` | `fallback_category_id()` memilih kategori default bertipe sama |
| `account` | `resolve_upload_account()` mencocokkan hint nama bank |

---

## 9. Observability

| Event | Level | Field |
| --- | --- | --- |
| `mutation_text_parsed` | info | `rows`, `via` (`deterministic` \| `llm`) |
| `mutation_pdf_color_parsed` | info | `rows`, `pages_used`, `pages_skipped` |
| `mutation_pdf_parsed` | info | `rows`, `via` (`color`) |
| `mutation_text_all_models_failed` | error | — |
| `mutation_pdf_ok` | info | `pages`, `scanned=True` |
| `mutation_pdf_no_content` | error | — |
| `mutation_pdf_all_pages_failed` | error | `pages` |
| `mutation_pdf_text_failed` | warning | `error` |
| `mutation_pdf_render_failed` | warning | `error` |
| `mutation_match_unrecognized` | warning | `user_id`, `filename` |
| `mutation_match_ok` | info | `user_id`, `total`, `matched`, `unmatched`, `pendings` |
| `pending_expired_purged` | info | `user_id` (opsional), `deleted` |
| `pending_matching_purged` | info | `user_id`, `deleted` |
| `pending_purged_on_startup` | info | `purged` |
| `pending_purge_on_startup_failed` | warning | `exc_info` |
| `pending_confirmed_api` | info | `user_id`, `pending_id`, `transaction_id` |
| `pending_cancel_rejected` / `pending_confirm_rejected` | warning | `user_id`, `pending_id`, `error` |
| `pending_cancelled_api` | info | `user_id`, `pending_id` |

Event baru yang direncanakan: `mutation_statement_rows_mismatch` (warning) — bila jumlah baris
hasil parser ≠ jumlah baris data yang terlihat dari selisih saldo; berguna mendeteksi regresi
tanpa perlu melihat berkas user.

---

## 10. Strategi Pengujian

### 10.1 Fixture

| Berkas | Isi | Dipakai untuk |
| --- | --- | --- |
| `backend/tests/fixtures/seabank_2026_09.txt` | Ekspor tabel pipe 71 baris + ringkasan saldo | Jalur delimited, tanggal tanpa tahun, total exact |
| `backend/tests/fixtures/seabank_2026_09_layout.txt` (baru) | *Text layer* hasil `_layout_text()` dari PDF SeaBank asli | Jalur whitespace: deskripsi multi-baris, kolom MASUK, entitas `&quot;` |
| `backend/tests/fixtures/bca_2026_09_layout.txt` (baru) | *Text layer* hasil `_layout_text()` dari PDF BCA asli | Jalur whitespace: sufiks `DB`/`CR`, `PERIODE : SEPTEMBER 2026`, deskripsi multi-baris |
| `backend/tests/fixtures/permata_2026_09_layout.txt` (baru) | *Text layer* hasil `extract_pdf_text()` dari PDF Permata asli | Bukti jalur teks gagal (0 baris) tanpa warna |
| `backend/tests/fixtures/permata_2026_09_color.txt` (baru) | Dump span `page\|hex\|y\|x\|height\|text` dari PDF Permata asli | Jalur warna: arah dari hex, tanggal di-*carry*, tahun terpotong |

Fixture layout dibuat dari PDF asli (bukan ditulis tangan) agar apa pun yang dibaca PyMuPDF ikut
terwakili. PDF aslinya tidak dikomit (berisi data pribadi); fixture teksnya sudah dianonimkan
bila perlu.

### 10.2 Kasus uji wajib

| ID | Kasus | Ekspektasi |
| --- | --- | --- |
| T-1 | SeaBank pipe fixture | 71 baris; debit 3.288.616; kredit 2.553.554 |
| T-2 | SeaBank layout fixture | 71 baris; total sama dengan T-1; deskripsi baris pertama `Bunga Tabungan` |
| T-3 | SeaBank layout — entitas | `&quot;` menjadi `"` |
| T-4 | SeaBank layout — kolom saldo | Tidak ada `amount` yang sama dengan nilai kolom `SALDO AKHIR` |
| T-5 | BCA layout | Jumlah baris = jumlah baris transaksi; arah `DB` → debit, `CR` → credit; `SALDO AWAL` tidak ikut |
| T-6 | BCA layout — tahun | `01/09` menjadi `2026-09-01` |
| T-7 | `account_hint` | `"SeaBank"` dan `"BCA"`, bukan nomor rekening |
| T-8 | PDF end-to-end | `parse_mutation_pdf()` tanpa LLM (di-*monkeypatch* agar gagal keras) menghasilkan seluruh baris |
| T-9 | PDF rusak / kosong | Kembalian `None`/`""`, tidak ada exception |
| T-10 | Dua arah terisi | Baris dilewati |
| T-11 | Dashboard: filter `null` / subset / kosong / id asing / daftar kosong | Sesuai tabel kontrak §6.2 |
| T-12 | Dashboard: label | `SeaBank · Bank`, `Dompet`, `2 akun terpilih`, `Tidak ada akun dipilih`, `null` |
| T-13 | `_color_direction()` | `#DD0C25` → debit; `#008873` dan `#8873` → credit; `#000000`, `#FFFFFF`, `#444444` → `None` |
| T-14 | Permata span fixture | Tepat **15** baris, tidak lebih dan tidak kurang |
| T-15 | Permata — arah | Merah → debit, hijau → credit; total debit **7.924.015,00**, kredit **8.209.830,00** |
| T-16 | Permata — tanggal | Tanggal di-*carry* lintas baris dan lintas halaman (15 nilai tanggal persis) |
| T-17 | Permata — deskripsi | Baris pertama `Biaya Adm Bulanan Kartu … September 2026`; baris terakhir `PB Bagi Hasil` (kredit 79) |
| T-18 | `parse_mutation_pdf()` Permata | LLM di-*monkeypatch* gagal keras; tetap 15 baris, `via="color"` |
| T-19 | Nominal tak berwarna di halaman berwarna | `_page_spans` di-*monkeypatch* mengembalikan `Rp 10.000` hitam → hasil `[]` (halaman dilewati) |
| T-20 | `account_hint` Permata | `"Permata"`, bukan `"SeaBank"` walau deskripsi transfer menyebut SeaBank |

### 10.3 Perintah verifikasi

```bash
# backend (venv lokal; DB sekali pakai, Supabase dinonaktifkan)
python3 -m pytest backend/tests -q

# kualitas kode
ruff check backend/app backend/tests
black --check backend/app backend/tests

# flutter (WAJIB dari folder app/)
cd app && flutter analyze && flutter test
```

---

## 11. Kinerja

| Aspek | Pendekatan |
| --- | --- |
| Parsing | Satu lintasan per baris; regex dikompilasi di tingkat modul. PDF 6 halaman / 71 baris ≪ 1 s |
| Memori | PDF dibuka *streaming*; jalur scan merender satu halaman per iterasi lalu melepas `pixmap` |
| Biaya LLM | Nol untuk berkas ber-text-layer; satu permintaan untuk berkas pindaian per halaman |
| Rate limit | `10/minute` per IP pada endpoint |

---

## 12. Kompatibilitas & Rollout

1. Perubahan bersifat *backward compatible*: bentuk response dan nama field tidak berubah.
2. `parsed_mutation.description` bisa sedikit berbeda dari sebelumnya (entitas didekode, deskripsi
   digabung) — ini perbaikan data, bukan *breaking change*.
3. Langkah rilis:
   ```bash
   docker compose up -d --build backend
   docker compose logs -f backend   # cari mutation_match_ok tanpa warning unrecognized
   ```
4. Rollback: `git revert` commit tunggal; tidak ada migrasi yang perlu dibatalkan.

---

## 13. Batasan & Pekerjaan Lanjutan

- Bank dengan letak kolom tidak konsisten antar halaman tetap bergantung pada fallback LLM.
- Jalur warna hanya mengenali **merah** dan **hijau**; bank yang memakai biru/oranye sebagai penanda
  arah belum didukung (akan jatuh ke jalur LLM).
- Jalur warna membaca satu span nominal = satu transaksi; statement yang mencetak nominal dan saldo
  berwarna pada baris yang sama belum diuji.
- PDF hasil pindaian tanpa peningkatan kualitas (de-skew, kontras) — jalur vision apa adanya.
- Belum ada tombol "setujui semua pending".
  **Update 1.2:** tetap belum ada — konfirmasi dilakukan satu-per-satu. Yang sudah ada:
  jalan masuk ke daftar pending dari layar hasil Matching Mutasi (tombol **Matching** di
  `bottomNavigationBar`) dan layar `PendingReviewScreen`. Aksi massal sengaja ditunda agar
  user tetap memeriksa tiap baris.
- Belum ada penyimpanan berkas unggahan; berkas gagal tidak dapat diuji ulang dari produksi.
  *Saran lanjutan:* simpan berkas gagal secara sementara (mis. 7 hari) agar regresi bisa
  direproduksi.

---

## 14. Checklist Implementasi

- [ ] `_clean_description()` + `html.unescape` diterapkan pada semua jalur.
- [ ] `_detect_account_hint()` tidak lagi mengembalikan nomor rekening.
- [ ] `_detect_year()` mendukung `PERIODE : SEPTEMBER 2026`.
- [ ] Peran `amount_direction` (`MUTASI`) + sufiks `DB`/`CR`.
- [ ] `_numeric_tokens()` memindai seluruh baris, bukan hanya ekor.
- [ ] Akumulator deskripsi multi-baris (atas + bawah baris jangkar).
- [ ] Fixture layout SeaBank & BCA dari PDF asli.
- [ ] `parse_colored_statement_pdf()` + `_color_direction()` + `_page_spans()` (jalur warna).
- [ ] Halaman dengan nominal tak berwarna dilewati, bukan ditebak.
- [ ] `_detect_account_hint()` berbasis frekuensi bank.
- [ ] Fixture span Permata dari PDF asli (anonim).
- [ ] Bot Telegram dihapus: kode, test, CI job, `.env.example`, README.
- [ ] Seluruh kasus uji §10.2 hijau.
- [ ] `ruff`, `black`, `flutter analyze`, `flutter test` bersih.
- [ ] `.gitignore` diperbaiki (`tests/` dan `test/root@…` dihapus) sehingga fixture & unit test ikut ter-commit.
- [ ] Backend image dibangun ulang dan diverifikasi di container.

### Tambahan 1.2 — alur Pending & kebersihan tabel

- [x] `app/schemas/pending.py` — DTO daftar/konfirmasi/batal/jumlah.
- [x] `app/api/pending.py` — `GET /api/pending`, `GET /api/pending/count`,
      `POST /api/pending/{id}/confirm`, `POST /api/pending/{id}/cancel`.
- [x] `app/main.py` — router `pending` terdaftar + housekeeping pending kedaluwarsa saat startup.
- [x] `purge_expired_pendings()` — global saat startup, per-user saat list/count/match.
- [x] `purge_matching_pendings()` — unggahan baru menggantikan pending "Matching Mutasi" lama.
- [x] Pembersihan dijalankan **setelah** parse sukses (unggahan gagal tidak menghapus apa pun).
- [x] 410 Gone untuk konfirmasi baris kedaluwarsa; 404 untuk baris user lain.
- [x] `app/lib/models/pending_models.dart` + 3 method di `api_client.dart`.
- [x] `app/lib/screens/pending_review_screen.dart` — Konfirmasi / Batalkan per baris.
- [x] Tombol **Matching** di `bottomNavigationBar` layar hasil + teks buntu diganti.
- [x] `PopScope` di layar hasil: keluar tanpa konfirmasi → pending dibatalkan (best-effort).
- [x] `tests/test_pending_api.py` — 18 test (auth, isolasi, konfirmasi, batal, housekeeping).
- [x] `test/pending_review_screen_test.dart` — 6 widget test (daftar, konfirmasi, batal,
      empty state, tombol Matching, pembuangan saat keluar layar).
- [x] `ruff`, `black`, `flutter analyze`, `flutter test` bersih; suite backend 304 passed.

### Tambahan 1.3 — Akurasi waktu transaksi hasil Matching

**Masalah.** `confirm_pending_transaction()` memanggil `create_transaction_internal()` tanpa
`transaction_date`, sehingga transaksi tercatat pada `datetime.now(UTC)` — tanggal & jam
konfirmasi, bukan tanggal & jam mutasi. Tanggal asli hanya tersisa sebagai teks di `note`.
Selain itu `find_matches()` membangun kandidat dari `min/max` tanggal mutasi ±
`date_window_days`, sehingga unggahan satu bulan bisa mencocokkan transaksi bulan lain.

**Desain.**

1. `PendingTransaction` mendapat dua kolom: `transaction_date TIMESTAMPTZ NULL` dan
   `timezone VARCHAR(64) NULL` (migrasi `0013_pending_transaction_date`, `down_revision=0012`).
   Nullable agar baris pending jalur lama tetap sah dan berperilaku seperti sebelumnya.
2. `mutation_matcher.detect_statement_period()` menghimpun seluruh tanggal yang terbaca →
   `MutationPeriod(start_date, end_date, months, label, first_mutation_date, last_mutation_date)`.
   Rentang > 12 bulan ditolak (`None`) karena bukan satu periode e-statement.
3. `period_bounds_utc(period, tz)` mengubah batas bulan **lokal** menjadi UTC:
   `[1 <bulan> 00:00 tz, 1 <bulan+1> 00:00 tz)` — batas atas eksklusif, sehingga hari terakhir
   bulan tidak terpotong di zona negatif/positif.
4. `mutation_local_datetime(mutation, tz)` menggabungkan tanggal + `HH:mm`; jam tidak ada /
   tidak valid → `00:00` lokal (tidak menebak).
5. `find_matches(..., period=None, tz=None)` — bila `period` ada, jendela kandidat = batas
   periode (tanpa ekstensi ± window); bila tidak, perilaku lama dipertahankan (min/max ± window,
   fallback 90 hari). `date_window_days` tetap berlaku sebagai batas selisih hari **di dalam**
   periode. Laporan "transaksi belum ada di mutasi" ikut dibatasi ke periode.
6. `POST /api/mutations/match` mendeteksi periode, memakai zona profil user
   (`ZoneInfo`, fallback `Asia/Jakarta`), mengembalikan `period` di response, dan menulis
   `transaction_date` (UTC) + `timezone` ke setiap pending.
7. `confirm_pending_transaction()` meneruskan `transaction_date=pending.transaction_date` dan
   `user_timezone=pending.timezone` ke `create_transaction_internal()` /
   `update_transaction_internal()`; `None` → tetap memakai waktu sekarang + zona profil.

**Checklist implementasi.**

- [x] `app/models/pending_transaction.py` — kolom `transaction_date`, `timezone`.
- [x] `alembic/versions/0013_pending_transaction_date.py` — upgrade/downgrade.
- [x] `app/core/mutation_matcher.py` — `MutationPeriod`, `detect_statement_period`,
      `period_bounds_utc`, `mutation_local_datetime`, `find_matches(period=, tz=)`.
- [x] `app/core/pending_service.py` — `create_pending_transaction(transaction_date=, timezone=)`;
      konfirmasi meneruskan tanggal asli untuk `create` maupun `update`.
- [x] `app/api/mutations.py` — `period` pada response, zona user, timestamp di pending.
- [x] `app/schemas/pending.py` + `app/api/pending.py` — `transaction_date`, `timezone` di DTO.
- [x] `app/lib/models/mutation_models.dart` — `MutationPeriodModel`, `period` di result.
- [x] `app/lib/models/pending_models.dart` — `transactionDate`, `timezone`.
- [x] `app/lib/screens/mutation_match_screen.dart` — baris "Periode mutasi" di ringkasan.
- [x] `app/lib/screens/pending_review_screen.dart` — "Tanggal transaksi: Sen, 14 Sep 2026 13:21".
- [x] Test backend: `TestDetectStatementPeriod`, `TestPeriodBounds`, `TestMutationLocalDatetime`,
      `TestFindMatchesPeriodFilter`, `TestCreatePendingsTimestamp`, plus test pending-service
      untuk tanggal asli dan dua test API (periode + timestamp pending → transaksi).
- [x] `ruff`, `black`, `flutter analyze`, `flutter test` bersih; suite backend 247 passed
      (240 pada rilis 1.3).

### Tambahan 1.4 — Hapus massal transaksi (FR-11)

- [x] `app/core/transaction_service.py` — `delete_transactions_internal(db, transactions,
      audit_ip_address=None)`: audit per baris (`old_value["bulk"] = True`) + **satu** commit.
- [x] `app/schemas/transaction.py` — `TransactionBulkDeleteRequest` (`ids`, 1…200) dan
      `TransactionBulkDeleteResponse` (`deleted`, `missing`).
- [x] `app/api/transactions.py` — `POST /api/transactions/bulk-delete`, rate limit `20/minute`,
      dedup id dengan `dict.fromkeys`, filter `user_id`, `missing` untuk id tak dikenal.
- [x] `app/lib/core/api_client.dart` — `bulkDeleteTransactions(List<String> ids)`.
- [x] `app/lib/models/transaction_models.dart` — `BulkDeleteResult`.
- [x] `app/lib/screens/transactions_screen.dart` — mode multi-pilih (long-press), checkbox per
      baris, app bar pilihan (`n dipilih`, pilih semua, hapus), dialog konfirmasi, snackbar
      hasil, pemangkasan `_selectedIds` setelah `_load()`.
- [x] Test baru `backend/tests/test_transactions_bulk_delete.py` (7 kasus): hapus id terpilih +
      cascade item, id asing / milik user lain → `missing`, id duplikat dihitung sekali, audit
      `bulk`, `ids` kosong → 422, 201 id → 422, tanpa auth → 401. Berkas ini memakai
      `app.dependency_overrides` sehingga jalan tanpa kredensial Supabase.
- [x] **Deployment**: `docker compose up -d --build backend` **dan**
      `docker compose exec -T backend alembic upgrade head` (0012 → 0013). Tanpa langkah kedua,
      produksi tetap memakai kode lama: pending tanpa `transaction_date` → transaksi tercatat di
      waktu konfirmasi.
- [x] `ruff`, `black`, `flutter analyze`, `flutter test` bersih; suite backend **247 passed,
      86 skipped**.

---

## Revisi 2026-10-31 — `core/balance.dart` digabung ke dashboard

Bagian 6.2 di atas **tidak berlaku lagi** (dibiarkan sebagai catatan historis):

- `app/lib/core/balance.dart` **dihapus**. Isinya hanya dipakai `dashboard_screen.dart`, jadi
  `totalBalanceFor(...)` sekarang menjadi fungsi top-level di
  `app/lib/screens/dashboard_screen.dart` (5 unit test di
  `app/test/dashboard_total_balance_test.dart`).
- **`balanceScopeLabel(...)` dihapus** — kartu "Total Balance" kini hanya menampilkan nominal.
  Keterangan cakupan akun tidak perlu duplikat karena dropdown filter di atasnya sudah menulis
  `'Semua akun (n)'`, `'n akun terpilih'`, atau `'Tidak ada akun dipilih'`.
- `_BalanceCard` kehilangan parameter `subtitle`; `_balanceSubtitle` di state dashboard dihapus.
- `flutter analyze` bersih, `flutter test` **54 passed**.
