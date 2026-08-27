# ROADMAP.md — MyMoney

## 1. Prinsip Eksekusi

- **Bertahap, bukan paralel.** Setiap fase harus punya hasil fungsional sebelum lanjut ke fase berikutnya — bukan mengerjakan 4 fitur besar bersamaan.
- **Timeline: 1-2 bulan, fokus penuh.** Target agresif ini hanya realistis kalau scope tidak melebar di tengah jalan (lihat riwayat revisi di §5 sebagai pengingat pola yang harus dihindari).
- Setiap fase diakhiri dengan checkpoint yang bisa dites nyata (bukan "selesai di kepala"), agar kalau timeline meleset, Anda tetap punya sistem yang jalan di titik manapun berhenti.

## 2. Fase Pengerjaan (REVISI TOTAL — Stack Baru)

### Fase 0 — Setup Fondasi Baru (Target: 3-4 hari, +1 hari dari sebelumnya)
- [ ] Buat project Supabase, setup Auth providers (email, Google OAuth minimal)
- [ ] Setup RLS policies dasar (profiles, transactions, accounts, categories)
- [ ] Setup backend FastAPI, koneksi ke Supabase Postgres via SQLAlchemy
- [ ] Setup Alembic migration target Supabase
- [ ] Init Flutter project (Riverpod, supabase_flutter, dio terpasang)
- [ ] Init Telegram bot project (Node/Telegraf/TypeScript)
- [ ] GitHub Actions dasar: lint 3 ekosistem (ruff/black, dart analyze, eslint)

**Checkpoint**: Backend jalan lokal terhubung Supabase, Flutter bisa
register/login via Supabase Auth, migration sukses.

### Fase 1 — Backend Inti + Integrasi Auth Supabase (Target: 1 minggu,
TIDAK BERUBAH dari estimasi awal meski approach beda)
- [ ] Middleware verifikasi Supabase JWT (bukan generate JWT sendiri —
      lebih cepat dari rencana awal karena tidak perlu implementasi
      refresh token custom)
- [ ] `transaction_service`: CRUD transaksi
- [ ] Trigger Postgres auto-create `profiles` saat user register
- [ ] Unit test service layer

**Checkpoint**: Register via Supabase Auth otomatis buat profile, CRUD
transaksi via Postman dengan token Supabase asli.

### Fase 1.5 — Auth Recovery: Reset Password (Target: 1-2 hari, REVISI
2026-08-26 — keputusan: TIDAK ada role admin, semua user self-register)
- [x] Migration 0007: hapus kolom `role` + constraint dari `profiles`
- [x] Hapus `require_role` dari `deps.py` + field `role` dari model `Profile`
- [x] Verifikasi live flow reset password Supabase (`/auth/v1/recover` + `otp`)
- [x] Dokumentasi flow di DATABASE.md §8 + REQUIREMENTS.md US-02a

### Fase 2 — Telegram Bot + Parsing Teks ✅ (2026-08-26, TIDAK BERUBAH)
- [x] Bot Node/Telegraf: pure proxy — verifikasi secret → forward ke backend dengan `X-Bot-Token`; handler lokal `/start`/`/help` dihapus (men-shadow logic linking backend)
- [x] `telegram_links`: map telegram_id ke profile — endpoint linking dibangun ulang v2 (OTP Supabase): `GET /api/telegram/link` + `POST /api/telegram/link/confirm` (JWKS + upsert relink semantics)
- [x] `nlu_parser` (Python, backend) — env-driven via `call_llm()` + kategori locked list → "Other" (sudah aktif sejak Fase 0)
- [x] Cutover webhook penuh → Fase 6 (butuh URL publik bot); archive bot Python = NO-OP (tidak pernah ada di repo)

### Fase 3 — Report Dasar ✅ (2026-08-26, TIDAK BERUBAH)
- [x] `report_service.py` SQL aggregation (`SUM`/`GROUP BY`): `parse_period_arg` + `get_report_summary` + `get_report_trend` (zero-filled, timezone user) — reuse v1, sudah aktif sejak Fase 0-1
- [x] `GET /api/reports/summary` (total + breakdown kategori) + `GET /api/reports/trend` (line chart data) — period/custom range, 422 validasi
- [x] Telegram `/report` (US-17) — `_format_report` ringkas, timezone user
- [x] Test service + API 24 test; `pytest` 130 hijau; `ruff`/`black` bersih; route terverifikasi live (401 tanpa token)

### Fase 3.5 — Accounts Management CRUD ✅ (2026-08-26, SELESAI)
- [x] CRUD akun (create/list/get/update) + **soft-delete via deactivate** — hard delete TIDAK ADA (route DELETE → 405, terbukti di test); akun nonaktif tidak muncul di pilihan transaksi baru tapi tetap penuh di riwayat/laporan historis (CODING_RULES §2.8)
- [x] Saldo computed dari transaksi (satu query agregasi; dinormalisasi 2 desimal); deactivate akun bersaldo → Transfer otomatis ke target (wajib `target_account_id`), 2 transaksi atomik + audit
- [x] Kategori Transfer (expense+income) global seeded (migration `0001`); `test_accounts_api.py` **15 test** — `pytest` **145 passed**, `ruff`/`black` bersih

### Fase 4 — Flutter App: Android + iOS + Web ✅ (2026-08-27, target 3-3.5 minggu)
- [x] Scaffold `app/` Flutter: Auth (Supabase Auth UI) + **Dashboard** (ringkasan Net/Pemasukan/Pengeluaran, selector periode 7 hari / Bulan ini, refresh, logout) — Riverpod + dio, config via `--dart-define`
- [x] **Line chart tap-detail**: `fl_chart` 1.1.0, `LineTouchData(handleBuiltInTouches: false)` + handler hanya `FlTapUpEvent` → ketuk titik langsung tampil detail hari (pemasukan/pengeluaran/net + tanggal); **long-press dihapus total**
- [x] Format util + test: `formatRupiah`/`formatDateShort`/`formatDateDetail` dkk; `flutter analyze` bersih + `flutter test` **10 passed**
- [x] APK demo: `app/build/app/outputs/flutter-apk/app-release.apk` (52.8MB, config Supabase+backend ter-embed, debug cert) — cara build & install ada di walkthrough.md Fase 4
- [x] Kredensial demo: **demo@mymoney.dev / Demo1234!** (`scripts/seed_demo.py`, 37 transaksi 14 hari) — terverifikasi live (login 200 → accounts 200 → summary month 7.000.000/1.162.055/5.837.945)
- [x] Performance: loading report/form paralel, tab lazy initialization, dan transaksi lengkap lazy-load hanya saat diperlukan
- [x] Dashboard UX: periode Today/Week/Month/Custom, filter akun multiselect client-side, refresh saat kembali dari tab lain
- [x] Summary card Income/Expense/Net interaktif dengan daftar transaksi full-screen dan sorting tanggal/nominal
- [x] Privacy toggle menyamarkan semua nominal; form transaksi mengikuti urutan tipe, nominal, akun, merchant, kategori, tanggal, catatan
- [x] Chart memakai token warna `DESIGN.md`, tap singkat menampilkan detail titik, dan label sumbu adaptif untuk mencegah tabrakan
- [x] Ganti email melalui Supabase `updateUser` + verifikasi OTP `emailChange`; multi-item text Telegram dan `/edit`
- [x] Validasi implementasi: `flutter analyze` bersih, `flutter test` 20 passed, APK release per-ABI (arm64 21,4 MB)
- [ ] Widget + golden test 5 layar kritis (Dashboard, Login, Transaction List, Add Transaction, Accounts) — sementara 10 test (format 4 + widget 6)
- [ ] Setup GitHub Actions macOS runner untuk build iOS otomatis (gratis,
      repo publik) — trigger di setiap push ke `main`
- [ ] Setup Apple Developer Program ($99/tahun) — WAJIB untuk TestFlight,
      bukan opsional kalau iOS masuk v1 tanpa Mac fisik
- [ ] Upload build iOS ke TestFlight setiap milestone besar (bukan setiap
      commit — terlalu sering akan menghabiskan kuota build)
- [ ] Cari MINIMAL 1 orang dengan iPhone (teman/keluarga) sebagai tester
      manual berkala — dokumentasikan siapa & jadwal testing di README,
      jangan andalkan diri sendiri karena Anda tidak punya device untuk itu

**Checkpoint (REVISI)**: Android teruji langsung di device Anda (APK demo
siap install — config terverifikasi via `strings libapp.so`). iOS lolos
CI build + golden test otomatis, DAN sudah di-testing manual minimal 1x
oleh tester eksternal via TestFlight sebelum dianggap "selesai" — CI hijau
saja TIDAK CUKUP untuk klaim iOS siap.

**Risiko yang diterima secara sadar**: bug UI/UX spesifik-iOS (gesture,
safe area, keyboard behavior) berpotensi baru ketahuan setelah tester
eksternal mencoba, bukan saat development. Ini trade-off yang sudah
disetujui — mitigasi di atas mengurangi risiko, bukan menghilangkannya.

**Catatan proses**: daemon Gradle `-Xmx8G` OOM-kill di mesin 7.8Gi RAM saat
build release → turunkan `-Xmx2G` + `kotlin.daemon.jvmargs=-Xmx1536M` di
`android/gradle.properties`. `.gitignore` root `lib/` (Python) sempat
meng-ignore `app/lib/` → tambah `!app/lib/` + `!app/lib/**`.

**Checkpoint**: App jalan di Android emulator/device, Web browser, dan
idealnya iOS simulator — backend & Supabase yang sama untuk ketiganya.

### Fase 5 — OCR Foto Nota (Target: 1.5-2 minggu, TIDAK BERUBAH secara
logic, tambahan: Supabase Storage integration untuk gambar nota)

### Fase 7 — UI/UX Polish (Target: 1-1.5 minggu, paralel Fase 4-5,
sedikit lebih ringan dari estimasi sebelumnya karena Flutter theme
lebih mudah dikonsistenkan lintas platform dibanding native Kotlin)

### Fase 6 — Deploy Produksi (Target: 2-3 hari, LEBIH CEPAT dari VPS
manual — Railway/Render deploy otomatis dari GitHub push, tidak perlu
script SSH manual)
- [ ] Setup Railway/Render project untuk backend & bot
- [ ] Setup Supabase production project (terpisah dari dev)
- [ ] Environment variables production (service role key, OpenRouter key)
- [ ] Deploy Flutter Web ke Vercel/Netlify
- [ ] Review keamanan: RLS policy production, tidak ada key ter-commit

## 3. Ringkasan Timeline Revisi

| Fase | Estimasi | Kumulatif |
|---|---|---|
| Fase 0 — Setup Fondasi Baru | 3-4 hari | ~4 hari |
| Fase 1 — Backend + Auth Supabase | 1 minggu | ~1.5 minggu |
| Fase 1.5 — Auth Recovery (reset password) | 1-2 hari | ~1.8 minggu |
| Fase 2 — Telegram + Parsing | 1-1.5 minggu | ~3.3 minggu |
| Fase 3 — Report Dasar | 3-5 hari | ~3.8 minggu |
| Fase 3.5 — Accounts CRUD | 1 minggu | ~4.8 minggu |
| Fase 4 — Flutter (3 platform) | 3-3.5 minggu | ~8.2 minggu |
| Fase 5 — OCR Foto Nota | 1.5-2 minggu | ~9.9 minggu |
| Fase 7 — UI/UX Polish (paralel) | 1-1.5 minggu | tidak menambah kumulatif |
| Fase 6 — Deploy Produksi | 2-3 hari | **~10.3 minggu** |

**Realitas timeline**: total **~10-11 minggu (2.5 bulan)** — mirip dengan
estimasi stack lama meski approach sangat berbeda, karena penghematan di
auth/deployment (Supabase, Railway/Render) kurang lebih seimbang dengan
tambahan waktu belajar Flutter/Dart (bahasa baru) dan setup RLS (konsep
baru). **Klaim "lebih sederhana" untuk solo dev valid dalam hal maintenance
jangka panjang (auth tidak perlu di-maintain sendiri), tapi TIDAK
otomatis mempercepat waktu pengerjaan v1 awal** — ini penting Anda sadari
supaya ekspektasi timeline tidak meleset.

## 4. Catatan Disiplin Scope (REVISI)

Perubahan stack ini SENDIRI adalah bentuk scope change besar yang harus
dicatat resmi (sesuai prinsip §5 sebelumnya) — bukan hanya "revisi
markdown". Setelah dokumen ini final, JANGAN ada pivot stack lagi di
tengah jalan — evaluasi hasil keputusan ini setelah Fase 1 selesai
(~1.8 minggu), bukan di tengah Fase 4/5 kalau mulai terasa "ribet lagi".

## 3. Ringkasan Timeline

| Fase | Estimasi | Kumulatif |
|---|---|---|
| Fase 0 — Setup Fondasi | 2-3 hari | ~3 hari |
| Fase 1 — Backend Inti + Auth | 1 minggu | ~1.5 minggu |
| Fase 2 — Telegram + Parsing Teks | 1-1.5 minggu | ~3 minggu |
| Fase 3 — Report Dasar | 3-5 hari | ~3.5 minggu |
| Fase 4 — Android App | 2-2.5 minggu | ~6 minggu |
| Fase 5 — OCR Foto Nota | 1.5-2 minggu | ~7.5-8 minggu |
| Fase 6 — Deploy Produksi | 3-5 hari | ~8-8.5 minggu |

**Realitas timeline**: total estimasi ini sudah mendekati **2 bulan penuh** dengan asumsi fokus konsisten tanpa gangguan besar. Target "1-2 bulan" yang Anda tetapkan berada di ujung atas rentang ini — realistis hanya jika tidak ada penambahan scope baru di tengah jalan.

Estimasi tambahan Fase 1 tidak berubah signifikan (~2-3 hari) — solusi ini justru lebih sederhana dari rencana reassignment sebelumnya (tidak perlu update massal account_id di banyak row transaksi, cukup 2 insert baru + 1 update is_active).

## 4. Fase v2 (Di Luar Scope Dokumen Ini)

Dicatat sebagai referensi masa depan, **bukan bagian dari commitment timeline v1**:
- Aplikasi iOS (native Swift/SwiftUI, mengonsumsi REST API yang sama)
- Shared/household data antar user
- Multi-currency
- Caching layer (Redis) untuk report — hanya jika terbukti perlu dari data pemakaian nyata
- Read replica / optimasi lanjutan — hanya jika skala user riil melebihi puluhan-ratusan

## 5. Catatan Disiplin Scope

Selama proses perencanaan dokumen ini, beberapa ide muncul di tengah jalan dan berhasil disaring keluar dari v1 setelah dipertimbangkan: n8n, Hermes Agent, multi-currency, aplikasi iOS, dan ekspektasi skala user yang sempat naik-turun. Pola ini **wajar terjadi lagi** selama development — ROADMAP ini ada justru untuk jadi acuan objektif: sebelum menambah apapun ke v1 di tengah jalan, cek dulu apakah itu benar-benar blocking untuk checkpoint fase saat ini, atau bisa masuk §4 (v2).