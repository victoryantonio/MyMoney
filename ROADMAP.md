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

### Fase 3 — Report Dasar (Target: 3-5 hari, TIDAK BERUBAH)

### Fase 3.5 — Accounts Management CRUD (Target: 1 minggu, TIDAK BERUBAH)

### Fase 4 — Flutter App: Android + iOS + Web (Target: 3-3.5 minggu)
[...langkah sebelumnya tidak berubah...]
- [ ] Setup GitHub Actions macOS runner untuk build iOS otomatis (gratis,
      repo publik) — trigger di setiap push ke `main`
- [ ] Setup Apple Developer Program ($99/tahun) — WAJIB untuk TestFlight,
      bukan opsional kalau iOS masuk v1 tanpa Mac fisik
- [ ] Widget test + golden test untuk minimal 5 layar kritis (Dashboard,
      Login, Transaction List, Add Transaction, Accounts) — baseline
      screenshot dicek di CI setiap build, supaya regresi visual iOS
      terdeteksi otomatis tanpa Anda lihat langsung
- [ ] Upload build iOS ke TestFlight setiap milestone besar (bukan setiap
      commit — terlalu sering akan menghabiskan kuota build)
- [ ] Cari MINIMAL 1 orang dengan iPhone (teman/keluarga) sebagai tester
      manual berkala — dokumentasikan siapa & jadwal testing di README,
      jangan andalkan diri sendiri karena Anda tidak punya device untuk itu

**Checkpoint (REVISI)**: Android teruji langsung di device Anda. iOS lolos
CI build + golden test otomatis, DAN sudah di-testing manual minimal 1x
oleh tester eksternal via TestFlight sebelum dianggap "selesai" — CI hijau
saja TIDAK CUKUP untuk klaim iOS siap.

**Risiko yang diterima secara sadar**: bug UI/UX spesifik-iOS (gesture,
safe area, keyboard behavior) berpotensi baru ketahuan setelah tester
eksternal mencoba, bukan saat development. Ini trade-off yang sudah
disetujui — mitigasi di atas mengurangi risiko, bukan menghilangkannya.

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