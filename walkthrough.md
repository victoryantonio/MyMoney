# walkthrough.md — MyMoney v2 Execution Guide

> ✅ **Pivot v2 (2026-08-26)**: stack baru Supabase + FastAPI + Flutter + Node bot.
> Panduan aktif: **Fase 4 (implementasi selesai; checkpoint device/iOS masih terbuka)** di bawah. Fase 0, 1, 1.5, 2, 3, 3.5, 7 (deploy produksi) selesai (rekam di bagian bawah).
> Guide fase berikutnya diisi saat fase dimulai (placeholder di bawah).
> Rekam historis v1 ada di git history + `_archive/`.

---

## Fase 7 — Deploy Produksi ✅ DONE (2026-08-28, commit `f827db8`)

**Tujuan:** production mode backend, hardening keamanan, release signing APK, backup DB otomatis, dokumentasi operasional.
**Hasil:** production aktif & terverifikasi publik; rate limit + backup cron + keystore + v1.1.0+2 + docs ter-update.

### Step 1 — Mode production
- `.env`: `APP_ENV=production`. Perilaku: `/docs` & `/redoc` → 404, CORS dibatasi ke `APP_BASE_URL`, error generik.
- **PENTING**: ubah env butuh **recreate** container (`docker compose up -d backend`), bukan `restart`.
- Verifikasi: `/health` → `{"status":"ok","env":"production"}`; `/docs` → 404; kategori API tetap 200 (409 "Kategori sudah ada" untuk duplikat).

### Step 2 — Hardening: rate limit & backup DB
- Rate limit (slowapi) di semua endpoint mutasi: transaksi 30/menit, kategori & akun 20/menit. Setiap endpoint ber-limit wajib punya parameter `request: Request`.
- Verifikasi: burst test 21 request → 20×201 + 1×429; `pytest` 165 passed (docker cp + container).
- `scripts/backup_db.sh`: `pg_dump -Fc` ke `/root/backups/mymoney/` (di luar repo), rotasi 14 file, mode `--test` & `--list`; cron harian `0 3 * * *`.
- **Bug ditemukan**: regex parsing `DATABASE_URL` menukar group port vs dbname → diperbaiki sebelum dipakai.

### Step 3 — Android release signing
- Keystore: `/root/keystore/mymoney/release.jks` (PKCS12, alias `mymoney`, RSA 2048, valid 10000 hari); password acak di `keystore-pass.txt`. **WAJIB backup permanen** (Play Store butuh key yang sama).
- `app/android/app/build.gradle.kts`: baca `key.properties` → `signingConfig release`; fallback debug bila file tidak ada.
- **PENTING**: `key.properties` harus di `app/android/key.properties` (root project Gradle Flutter = `app/android`, BUKAN `/root/project/android/`). APK pertama masih debug-signed karena salah lokasi → dipindah & rebuild.
- Verifikasi: `apksigner verify --print-certs` → CN=MyMoney, SHA-256 `357522a1...dc72` cocok.

### Step 4 — Versi & dokumentasi
- `pubspec.yaml`: `1.1.0+2`; `CHANGELOG.md` baru.
- `README.md`: tabel Tech Stack (EN) + status produksi.
- `backend/README.md`: seluruh bagian produksi/operasional dalam bahasa Inggris.

### Step 5 — Verifikasi end-to-end (publik)
- `/health` → `env:production` ✅ · `/docs` → 404 ✅ · `/api/categories` → 200 ✅ · APK release signed produksi ✅
- Commit `f827db8` → origin/migration.

---

## Fase 1.5 — Auth Recovery: Reset Password ✅ DONE (2026-08-26)

**Tujuan:** tidak ada role admin (semua user self-register); hapus kolom `role`; pastikan ada sistem reset password via OTP/link ke email terdaftar — ditangani Supabase Auth, diverifikasi live.
**Hasil:** migration `0007` di-run; `pytest` hijau; flow reset password terverifikasi live.

### Step 1 — Hapus kolom `role` (keputusan: tidak ada admin)
- Migration `0007_drop_profile_role.py`: drop constraint `ck_profiles_role` → drop kolom `role`; `alembic upgrade head` sukses.
- Verifikasi `information_schema`: kolom `profiles` = id, display_name, timezone, is_active, created_at, updated_at (tanpa role/constraint).
- Model `Profile` tanpa field `role`; `require_role` dihapus dari `deps.py`.

### Step 2 — Verifikasi live reset password (Supabase Auth)
- `POST /auth/v1/recover` (email terdaftar) → `200 {}` — email reset masuk antrian Supabase.
- `POST /auth/v1/otp` → `429 over_email_send_rate_limit` — endpoint nyata, rate-limit email anti-spam aktif.
- `POST /auth/v1/recover` (email tak dikenal) → `200 {}` — anti-enumeration, status email tidak bocor.
- Login password lama setelah recover → `200` — recover tidak mengubah password.

### Step 3 — Dokumentasi
- DATABASE.md §8: flow recover → verify → set password baru; flow OTP murni; catatan verifikasi.
- REQUIREMENTS.md US-02a; referensi role/admin dibersihkan dari ARCHITECTURE.md, ROADMAP.md, task.md, IMPLEMENTATION_PLAN.md.

---

## Fase 2 — Telegram Bot Node + Parsing Teks ✅ DONE (2026-08-26)

**Tujuan:** bot Node jadi thin proxy ke backend (service-to-service token); endpoint linking v2 (OTP Supabase); `nlu_parser` env-driven; cutover webhook.
**Hasil:** bot pure proxy + webhook dual-auth + linking OTP dibangun & diuji; `pytest` 130 hijau; bot typecheck/lint/build bersih; E2E live terverifikasi.

### Step 1 — Backend webhook: dual auth + register ke bot
- `POST /api/telegram/webhook`: terima `X-Bot-Token` (service-to-service, produksi) **ATAU** `X-Telegram-Bot-Api-Secret-Token` (fallback langsung Telegram→backend) — 403 tanpa keduanya.
- `POST /api/telegram/register-webhook` → `setWebhook` ke `{BOT_PUBLIC_URL}/webhook` (bukan lagi ke backend).
- `config.py` + `.env.example`: `BOT_PUBLIC_URL` (default `http://localhost:3000`).

### Step 2 — Rebuild endpoint linking (v2, OTP Supabase)
1. `/start` di backend `telegram_service.py` → JWT `telegram_link` (10 menit) → link `GET /api/telegram/link?token=...` (URL ini sempat 404 karena endpoint dihapus di Fase 1 — dibangun ulang).
2. `GET /api/telegram/link`: validasi token → halaman HTML (DESIGN.md tokens, `/static/icon.png`) minta email → kirim OTP via Supabase `/auth/v1/otp` (anon key, `create_user:false`).
3. `POST /api/telegram/link/confirm {link_token, access_token}`: decode token → verifikasi Supabase JWT (JWKS) → upsert `telegram_links` dengan relink semantics (satu telegram_id ↔ satu profile).
4. Alasan: form email/password v1 tidak mungkin — kredensial milik Supabase Auth, backend tak punya verifikasi password lokal.

### Step 3 — Bot = pure proxy (fix shadowing)
- Handler lokal `bot.command("start")` / `bot.command("help")` dihapus — dulu membalas pesan generik sehingga link linking dari backend tidak pernah sampai ke user.
- `bot.on("message")`: forward `ctx.update` → `${BACKEND_URL}/api/telegram/webhook` dengan `X-Bot-Token`; **tidak membalas sendiri** (backend yang membalas via Bot API → tidak ada double-reply); fallback 1 pesan bila backend gagal.

### Step 4 — Test & verifikasi
- `test_telegram_webhook_api.py`: 403 tanpa header/token salah; 200 `X-Bot-Token`; 200 secret Telegram (background dipatch — LLM/OCR tidak jalan di unit test).
- `test_telegram_linking_api.py`: form valid/invalid, confirm sukses/idempoten/not-found/401/relink (JWKS dipatch).
- `models/profile.py`: `TYPE_CHECKING` imports → warning Pylance hilang.
- `pytest` **130 passed** (naik 12); `ruff`/`black` bersih; bot `typecheck`/`lint`/`build` bersih.
- **E2E live**: curl update `/start` → bot :3000 (secret valid) → forward → backend webhook 200 → diproses → `sendMessage` ke chat acak gagal 400 "chat not found" (ekspektasi — membuktikan seluruh chain jalan).

### Step 5 — Cutover & arsip
- Archive bot Python: **NO-OP** — bot Python tidak pernah ada di repo ini (bot selalu Node/Telegraf sejak Fase 0); dicatat jujur.
- Cutover webhook penuh ke URL publik bot → **Fase 6** (deploy). Dev saat ini: bot lokal + backend lokal.

---

## Fase 1 — Backend Inti + Auth Supabase ✅ DONE (2026-08-27)

**Tujuan:** REST API v2 di atas Supabase — auth = Supabase JWT (JWKS), profile auto-create via trigger, CRUD transaksi service layer, unit test.
**Hasil:** semua step selesai & terverifikasi live; `pytest` 118 hijau, `ruff`/`black` bersih.

### Step 1 — Migration FK: `users` → `profiles` (prasyarat blocker)
1. **Blocker terverifikasi**: semua tabel v1 punya FK `user_id → users.id`, padahal user v2 hanya ada di `auth.users` + `profiles` → insert account/transaksi GAGAL (ForeignKeyViolation).
2. Migration `0006_fk_profiles.py`: drop semua FK ke `users.id` → drop tabel `users` (kosong) → re-create FK ke `profiles.id` (ondelete CASCADE).
3. `alembic upgrade head` sukses; verifikasi via `information_schema` — tabel `users` hilang, semua FK `*_user_id_fkey` → `profiles`.

### Step 2 — `verify_supabase_jwt()` di `core/security.py`
- Fetch JWKS dari `{SUPABASE_URL}/auth/v1/.well-known/jwks.json` → cache in-memory (TTL 300 s).
- **Temuan live**: Supabase project ini memakai **ES256 (P-256)** — bukan RS256! Implementasi mendukung **RS256 + ES256** (via `jose.jwk.construct`).
- Validasi signature + `exp`; `SUPABASE_JWT_SECRET` hanya fallback HS256 bila diisi (kosong di project baru).
- Terverifikasi live: token asli → PASS; token korup/diubah → ditolak.

### Step 3 — deps: `require_active_user` → `profiles`
- `api/deps.py`: `get_current_user` (HTTPBearer → verify → `db.get(Profile, sub)` → 401), `require_active_user` (403 bila nonaktif).
- `telegram_service.py` + semua router API (accounts/categories/reports/transactions) → `Profile`.

### Step 4 — Hapus endpoint auth custom
- `api/auth.py`, `api/telegram_linking.py`, `schemas/auth.py`, `models/user.py` dihapus. `main.py`: 23 route (telegram_webhook tetap — bot webhook tak butuh profile auth; linking dibangun ulang di Fase 2 → 25 route).

### Step 5 — Unit test
- `conftest.py`: mimic `auth.users` lokal (CI), fixture `profile`, `supabase_factory` (skip otomatis tanpa kredensial), `limiter.enabled=False`.
- Semua test diadaptasi ke v2: service layer pakai `(db, profile)`; API tests pakai Supabase JWT asli.
- **118 passed** · `ruff check .` bersih · `black --check .` bersih.

### Step 6 — Checkpoint verification (DoD Fase 1) ✅
- [x] Supabase JWT asli (password grant) → 401/200 benar; CRUD akun & transaksi sukses
- [x] Tanpa token → 401; token palsu → 401
- [x] `profiles` auto-buat saat register (trigger) — dibuktikan Fase 0
- [x] `pytest` hijau (118)

---

## Fase 0 — Setup Fondasi Baru ✅ DONE (2026-08-26, commit `29abccc`)

> Detail langkah lengkap di bawah dipertahankan sebagai rekam historis; semua
> item checkpoint sudah terverifikasi: backend `/health` 200 + Supabase pooler
> (Tokyo); `alembic upgrade head` 0001–0005 sukses; `profiles` + trigger + RLS
> terpasang; Flutter analyze bersih + test 2/2; bot typecheck/lint bersih; CI
> job `app` + `bot`; signup → profile auto-terisi (tz=Asia/Jakarta).

### Step 0 — Decision gate
1. **LLM env-driven** (keputusan final 2026-08-26): `LLM_PROVIDER=auto` dengan
   `OPENROUTER_API_KEY` (default, free tier) dan/atau `DEEPSEEK_API_KEY`;
   model via `LLM_TEXT_MODEL`/`LLM_VISION_MODEL` (+fallback chain). Satu gateway
   `call_llm()` tetap — tidak ada panggilan LLM di luar `core/llm_client.py`.
2. **Folder v2 (untuk review user)**: `backend/` (FastAPI, dimigrasi),
   `bot/` (Node), `app/` (Flutter), `_archive/` (v1).
3. **Commit pivot**: belum — menunggu review user.

### Step 1 — Buat project Supabase (user yang buat di dashboard — panduan)
1. Buka https://supabase.com → **New project** (pilih org, region terdekat,
   password DB kuat — simpan aman).
2. Setelah jadi, dari **Project Settings → API** salin:
   - `Project URL` → `SUPABASE_URL` (contoh `https://abcxyz.supabase.co`)
   - `anon public` → `SUPABASE_ANON_KEY` (aman untuk client)
   - `service_role` → `SUPABASE_SERVICE_ROLE_KEY` (**RAHASIA** — backend only,
     jangan pernah di Flutter/bot client)
3. **Authentication → Providers**: aktifkan Email (default). Google OAuth:
   buat OAuth Client ID di Google Cloud Console, redirect URI
   `https://<project-ref>.supabase.co/auth/v1/callback`, isi di provider settings.
4. **Project Settings → Database → Connection string**:
   - `Transaction pooler` (port 6543) → `DATABASE_URL` runtime
   - `Session pooler`/direct (port 5432) → untuk migration `alembic`

### Step 2 — `.env` lokal
- Salin `.env.example` → `.env`; isi `SUPABASE_URL`, `SUPABASE_ANON_KEY`,
  `SUPABASE_SERVICE_ROLE_KEY`, `DATABASE_URL`, LLM keys, `TELEGRAM_BOT_TOKEN`.
- JANGAN pernah commit `.env` (sudah di `.gitignore`).

### Step 3 — Backend: koneksi Supabase + migration
1. `backend/app/core/config.py`: tambah settings Supabase (pydantic-settings)
   — `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` (opsional),
   `DATABASE_URL` Supabase.
2. `backend/alembic/env.py`: baca `DATABASE_URL` dari settings (bukan hardcode).
3. Migration baru `alembic/versions/0002_supabase_profiles.py`:
   - Tabel `profiles` (DATABASE.md §2.1): `id UUID PK FK auth.users(id)`,
     `display_name`, `timezone` (default 'Asia/Jakarta'), `is_active`,
     `created_at`, `updated_at`.
   - Trigger `handle_new_user` (SQL DATABASE.md §2.1) — SECURITY DEFINER.
   - RLS: enable + policy `profiles` (select/update own), `transactions`,
     `accounts`, `categories` (user_id = auth.uid(); kategori global NULL
     user_id bisa dibaca semua user terautentikasi).
4. Jalankan: `alembic upgrade head` → verifikasi tabel & trigger di Supabase
   Table Editor / SQL Editor.
5. `/health` backend lokal → 200 (DB Supabase).

### Step 4 — Flutter init (`app/`)
1. Install Flutter SDK (https://docs.flutter.dev/get-started/install/linux),
   lalu `flutter doctor` (Android toolchain untuk build APK).
2. `flutter create app --org id.my.mymoney --platforms android,ios,web`
3. Deps: `flutter pub add flutter_riverpod supabase_flutter dio`.
4. `lib/main.dart`: `await Supabase.initialize(url: ..., anonKey: ...)`
   (pakai `--dart-define` build-time, bukan hardcode).
5. Layar Auth minimal (email login/register) — cukup untuk verifikasi checkpoint.

### Step 5 — Bot Node init (`bot/`)
1. Install Node LTS (nvm): `curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash` lalu `nvm install --lts`.
2. `mkdir -p bot && cd bot && npm init -y && npm i telegraf dotenv && npm i -D typescript tsx @types/node`.
3. Scaffold minimal `src/index.ts`: webhook endpoint + cek
   `X-Telegram-Bot-Api-Secret-Token` + forward update ke backend
   (URL dari `APP_BASE_URL`, auth `BOT_SERVICE_TOKEN`) — implementasi penuh Fase 2.
4. `tsc --noEmit` clean.

### Step 6 — GitHub Actions (lint 3 ekosistem)
- `.github/workflows/lint.yml`:
  - backend: `pip install -e .[dev] && ruff check . && black --check .`
  - app: `flutter pub get && flutter analyze`
  - bot: `npm ci && npx eslint src && tsc --noEmit`

### Step 7 — Checkpoint verification (DoD Fase 0)
- [ ] `backend`: `/health` 200; `alembic upgrade head` sukses di Supabase
- [ ] Supabase: `profiles` + trigger + RLS terpasang
- [ ] `app`: `flutter analyze` clean; register/login via Supabase Auth →
      row `profiles` otomatis muncul
- [ ] `bot`: `tsc --noEmit` clean; webhook endpoint hidup

---

## Fase 3 — Report Dasar ✅ DONE (2026-08-26)

**Tujuan:** SQL aggregation untuk summary per periode + endpoint REST + Telegram `/report`.
**Hasil:** `report_service` + `/api/reports/summary` + `/trend` + `/report` sudah aktif sejak Fase 0-1; diverifikasi ulang di fase ini (test + route + auth).

### Step 1 — Service (sudah ada, reuse)
- `core/report_service.py`: `parse_period_arg` (hari-ini/minggu-ini/bulan-ini/bulan-lalu + EN synonyms, default bulan ini) → `get_report_summary` (SQL `SUM`/`GROUP BY` per tipe + per kategori) + `get_report_trend` (deret harian zero-filled, timezone user via `func.timezone`).
- `schemas/report.py`: `ReportSummaryResponse`, `ReportTrendResponse`, `CategoryTotal`, `TrendPoint`.

### Step 2 — API (sudah ada, reuse)
- `GET /api/reports/summary` — total income/expense/net + breakdown per kategori; period `today|week|month|last-month` ATAU custom `start`/`end`; 422 bila period invalid / start ≥ end.
- `GET /api/reports/trend` — deret harian (line chart); setiap hari di [start, end) muncul (zero-filled).
- Auth: `require_active_user` (Supabase JWT → Profile). Timezone dari `profiles.timezone` (default Asia/Jakarta).

### Step 3 — Bot `/report` (sudah ada, reuse)
- `/report` di `telegram_service.py`: parse arg → timezone user dari DB → `parse_period_arg` → `get_report_summary` → `_format_report` (teks ringkas, per kategori dengan ikon).

### Step 4 — Test & verifikasi
- `test_report_service.py` (aggregation + trend zero-fill) + `test_reports_api.py` (auth 401, default month, valid periods, invalid 422, custom range, trend points) = **24 test**.
- `test_telegram_service.py`: 4 test `/report` (requires link, default this month, arg minggu-ini → this week, timezone user).
- `pytest` **130 passed**; `ruff`/`black` bersih; route terverifikasi via OpenAPI (401 tanpa token).

---

## Fase 3.5 — Accounts CRUD ✅ (2026-08-26)

> Fase verifikasi: semua kode akun sudah ada sejak Fase 0-1 — fase ini = audit + test API + fix kecil.

### Step 1 — Audit kode (sudah ada, tidak diubah)
- `backend/app/api/accounts.py`: CRUD penuh + `POST /api/accounts/{id}/deactivate`. **TIDAK ada route DELETE** (terbukti 405 di test).
- `_compute_balance(account, db)` → `(current_balance, net_balance)` via SATU query agregasi: `initial_balance + SUM(CASE type='income' THEN +amount ELSE -amount)` dengan `func.cast(case(...), Transaction.total_amount.type)` + `func.coalesce(..., Decimal("0.00"))`.
- Model `Account` (soft-delete `is_active`), schema `AccountResponse` dengan `current_balance`/`net_balance` computed.

### Step 2 — Fix nyata (1)
- **Bug**: SUM atas `Numeric(14,2) * cast` melebarkan skala → `current_balance` bernilai 4 desimal (mis. `80000.0000`).
- **Fix**: `delta.quantize(Decimal("0.01"))` di `_compute_balance` — API konsisten 2 desimal dengan schema NUMERIC(14,2).

### Step 3 — Deactivate & balancing
- Saldo = 0 → langsung nonaktif (tanpa target).
- Saldo ≠ 0 → WAJIB `target_account_id`: 400 tanpa target; 400 target = source; 404 target tak ditemukan/terhubung.
- Balance ≠ 0: buat 2 transaksi Transfer atomik (expense di source + income di target, jumlah = saldo, note "Saldo dipindah dari X ke Y") + audit; kategori Transfer = seed global migration `0001` (reuse via `get_or_create_category`, tanpa duplikat per-user).

### Step 4 — CODING_RULES §2.8
- Akun nonaktif **ditolak** di transaksi baru: `_verify_category_and_account` → **422** "Account not found or not accessible".
- Akun nonaktif tetap muncul penuh di riwayat/laporan historis (tidak dihapus).

### Step 5 — Test & verifikasi
- `test_accounts_api.py` **15 test**: auth 401, create + validasi, list aktif default / `include_inactive`, update, get/update akun nonaktif → 404, **no-delete 405**, deactivate saldo 0, deactivate butuh target (400/400/404), transfer balancing (saldo pindah + 2 tx ber-note + kategori Transfer global), §2.8 422.
- `pytest` **145 passed** (130 baseline + 15); `ruff`/`black` bersih.

---

## Fase 4 — Flutter App (implementation complete; checkpoint open) (2026-08-27)

> Implementasi Flutter dan follow-up performance/UX selesai. Fase tetap aktif
> sampai APK release diuji di perangkat Android dan checkpoint iOS/TestFlight
> terpenuhi.

### Step 5 — Performance & UX follow-up (commit `d784e9d`, `2ab9b41`)
- Dashboard dan form memuat request independen secara paralel.
- Semua transaksi untuk filter akun di-load lazy; dashboard default hanya mengambil satu halaman transaksi terbaru.
- Tab navigasi diinisialisasi lazy; Dashboard refresh saat tab dipilih kembali.
- Summary card dapat ditekan untuk daftar transaksi penuh dengan sorting tanggal/nominal.
- Toggle mata menyamarkan seluruh nominal; form transaksi mengikuti urutan tipe, nominal, akun, merchant, kategori, catatan.
- Ganti email memakai `auth.updateUser` lalu verifikasi `OtpType.emailChange`.
- Chart memakai token warna DESIGN.md dan interval label adaptif agar tidak bertabrakan.
- Multi-item text Telegram dan `/edit` mengirim item, merchant, dan total hasil perhitungan.

### Step 6 — Verifikasi
- `flutter analyze`: bersih.
- `flutter test`: 20 passed.
- `flutter build apk --release --split-per-abi`: arm64-v8a 21,4 MB; armeabi-v7a 19,0 MB; x86_64 23,0 MB.
- Backend unit tests: 70 passed; integration API yang membutuhkan Supabase live belum dapat dijalankan di environment lokal (ReadTimeout).
- Checkpoint tersisa: instal dan uji Samsung S23+, iOS CI, dan tester eksternal TestFlight.

### Step 1 — Line chart: tap → detail, hilangkan long-press
- `app/pubspec.yaml` + `fl_chart ^1.1.0`; `flutter pub get`.
- `lib/widgets/trend_chart.dart`: `TrendChart(points, selectedIndex, onPointTap)`.
  - `LineTouchData(enabled: true, handleBuiltInTouches: false, touchCallback: ...)` — handler **hanya** `FlTapUpEvent`; long-press/drag **tidak punya handler sama sekali** sehingga diabaikan.
  - Ketuk → `onPointTap(x.round())` → panel detail di bawah chart.
  - Titik terpilih menonjol (`getDotPainter` radius 5 vs 2.5, stroke putih) + garis putus-putus vertikal (`ExtraLinesData` dashArray [4,4]).
  - Garis pemasukan hijau `0xFF2E7D32`, pengeluaran merah `0xFFC62828`, area bawah hanya untuk income (alpha 0.08).
  - Label sumbu X rapat otomatis: `_bottomInterval` 1 (≤7 titik) / 2 (≤15) / 4; `_compact` ("5rb", "1,2jt").
  - Catatan fl_chart 1.1: `barData.color` nullable → fallback `Color(0xFF555555)`.

### Step 2 — Dashboard + format
- `lib/screens/dashboard_screen.dart`: `ConsumerStatefulWidget(supabase)`; `SegmentedButton` periode ('week' = 7 hari, 'month' = Bulan ini); kartu Net/Pemasukan/Pengeluaran; `_TrendCard` = chart + `_DetailPanel`; `_ErrorView` + retry; `RefreshIndicator`; tombol logout.
- `_DetailPanel`: hint "Ketuk titik pada grafik untuk melihat detail hari itu" saat belum ada pilihan; setelah ketuk → tanggal (`formatDateDetail`), Pemasukan/Pengeluaran/Net berwarna.
- `lib/core/format.dart`: `formatRupiah` ("Rp40.000"), `formatRupiahSigned`, `formatDateShort` ("12 Agu"), `formatAxisLabel`, `formatDateDetail` ("Rab, 12 Agu").
- `lib/main.dart`: AuthGate → `DashboardScreen` saat session ada.
- `flutter analyze` bersih; `flutter test` **10 passed** (`format_test.dart` 4 + `widget_test.dart` 6).

### Step 3 — Kredensial demo + seed data
- `scripts/seed_demo.py` (idempotent, baca `.env` tanpa mencetak secret): buat user demo via Supabase admin API, login, buat akun "Cash" (saldo awal 500.000), seed 14 hari transaksi (Makan siang, Gojek, Shopping, Bills, Salary, Bonus) — **37 transaksi**.
- Kredensial demo: **`demo@mymoney.dev` / `Demo1234!`**.
- Verifikasi live: login 200 → `GET /api/accounts` 200 → `GET /api/reports/summary?period=month` = income 7.000.000 / expense 1.162.055 / net 5.837.945.
- **Pelajaran**: 401 padahal JWT valid = container backend jalan dengan env lama (DB lokal). Solusi: `docker compose build backend && docker compose up -d --force-recreate backend`.

### Step 4 — APK demo
- Build release dengan config ter-embed:
  ```bash
  cd app && flutter build apk --release \
    --dart-define=SUPABASE_URL=https://fqjkqcigjeyooejcgbrk.supabase.co \
    --dart-define=SUPABASE_ANON_KEY=<anon dari .env> \
    --dart-define=APP_BASE_URL=http://103.27.206.22:8000
  ```
- Hasil: `app/build/app/outputs/flutter-apk/app-release.apk` (52.8MB) — config terverifikasi ada di dalam APK (`strings libapp.so`). Tanda tangan: debug cert (default Flutter; cukup untuk demo).
- **Pelajaran**: daemon Gradle `-Xmx8G` → OOM-kill di mesin 7.8Gi RAM saat build release; turunkan ke `-Xmx2G` + `kotlin.daemon.jvmargs=-Xmx1536M` di `android/gradle.properties`. `.gitignore` root `lib/` (konvensi Python) meng-ignore `app/lib/` → tambah `!app/lib/` + `!app/lib/**`.

## Fase 5 — OCR Foto Nota (placeholder)
## Fase 7 — UI/UX Polish (placeholder)
## Fase 6 — Deploy Produksi (placeholder)

---

## v1 — Rekam historis (COMPLETE ✅, 2026-08-25)

> Stack lama (Kotlin + FastAPI + Postgres self-hosted + bot Python) selesai &
> ter-deploy. Kode di `_archive/android-kotlin-v1/`; detail per-fase ada di
> git history. Panduan eksekusi v1 dihapus dari file ini saat pivot v2.
