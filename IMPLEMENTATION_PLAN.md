# IMPLEMENTATION_PLAN.md — MyMoney

> Planning doc for the **current** phase of work.
> Each phase gets its own section. When work moves to a new phase, this file is
> edited so the "Current Phase" points at the active one and completed phases
> move under `## Completed Phases`.

**Current Phase: Fase 4 — Flutter App: Android + iOS + Web**

---

## Pivot v2 — Ringkasan (2026-08-26)

Keputusan: **migrasi total ke stack baru** per ARCHITECTURE.md / ROADMAP.md v2
(Supabase + FastAPI + Flutter + Node/Telegraf bot). 6 dokumen inti sudah
ditulis ulang; `android/` v1 sudah di-archive ke `_archive/android-kotlin-v1/`;
`README.md` baru (banner status migrasi). **Belum ada commit pivot** —
menunggu review user.

### Keputusan yang sudah disepakati (review 2026-08-26)

| Topik | Keputusan | Alasan (chain of thought) |
|---|---|---|
| Penyedia LLM | **Env-driven**: `LLM_PROVIDER=auto\|openrouter\|deepseek`; `.env.example` memuat key kedua penyedia | Dokumen sumber inkonsisten soal model (DeepSeek vs OpenRouter GLM/Gemma). Satu gateway `call_llm()` tetap, penyedia & model dari env → tanpa hardcode di kode |
| Struktur folder v2 | `backend/` (FastAPI, dimigrasi), `bot/` (Node, baru), `app/` (Flutter, baru), `_archive/` (v1) | Untuk review user — pisahkan 3 ekosistem agar lint/CI independen (CODING_RULES §2) |
| Commit | Ditunda sampai user review plan ini | Perubahan besar (105 rename + 6 dokumen) — user ingin review dulu |
| Supabase | Belum dibuat project; `.env.example` placeholder; walkthrough Fase 0 memandu pembuatan | User memilih "pandu saya membuatnya" |

### Prinsip yang TIDAK berubah dari v1 (dipertahankan, bukan diulang)

- Backend FastAPI tetap **single source of truth** logic bisnis; Flutter & bot = thin client (ARCHITECTURE §3.1, CODING_RULES §2.2).
- Service layer satu fungsi untuk Telegram & REST — dilarang duplikasi "khusus bot" (CODING_RULES §2.2).
- Query: pagination cursor, eager loading, agregasi di SQL (CODING_RULES §2.3).
- LLM: satu gateway `call_llm()`; output wajib Pydantic-validated; kategori locked list → "Other"; anti prompt injection (CODING_RULES §2.4, §2.9.B).
- Audit trail eksplisit untuk semua mutasi; log terstruktur (CODING_RULES §2.7).
- Akun tidak pernah hard-delete; saldo computed dari transaksi (CODING_RULES §2.8).
- Keamanan: SQL via ORM saja; service_role key hanya di backend (CODING_RULES §2.9).

---

## Fase 0 — Setup Fondasi Baru ✅ DONE (2026-08-26, commit `29abccc`)

> Selesai & ter-commit — detail hasil di **Completed Phases → Fase 0** di bawah.

---

## Fase 1 — Backend Inti + Auth Supabase ✅ DONE (2026-08-27)

> Selesai & terverifikasi — detail hasil di **Completed Phases → Fase 1** di bawah.

---

## Fase 1.5 — Auth Recovery: Reset Password ✅ DONE (2026-08-26)

> Detail hasil di **Completed Phases → Fase 1.5**.

---

## Fase 2 — Telegram Bot Node + Parsing Teks ✅ DONE (2026-08-26)

> Selesai & terverifikasi live — detail hasil di **Completed Phases → Fase 2**.

---

## Fase 3 — Report Dasar ✅ DONE (2026-08-26)

> Selesai & terverifikasi — detail hasil di **Completed Phases → Fase 3**.

---

## Fase 3.5 — Accounts Management CRUD ✅ DONE (2026-08-26)

> Selesai & terverifikasi — detail hasil di **Completed Phases → Fase 3.5**.

---

## Fase 4 — Flutter App: Android + iOS + Web (target 3-3.5 minggu) ✅ DONE (2026-08-27)

> Selesai & ter-commit — detail hasil di **Completed Phases → Fase 4** di bawah. Milestone besar iOS CI + TestFlight masih terbuka (lihat task di bawah).

**Goal:** satu codebase Flutter (`app/`) untuk 3 platform, konsumsi REST backend dengan Supabase JWT.

**Keputusan & alasan (chain of thought):**
- Auth: `supabase_flutter` SDK (session + refresh otomatis) — REST call pakai Supabase JWT di header (backend verifikasi).
- State: **Riverpod** (rekomendasi solo dev, mudah di-test); chart: **fl_chart 1.1.0** (keputusan saat Step 3, DESIGN.md §8).
- iOS: build via GitHub Actions macOS runner; TestFlight ($99/tahun) + tester eksternal minimal 1 orang — **CI hijau saja tidak cukup** (ROADMAP §Fase 4).
- Web: deploy static (Vercel/Netlify), tetap panggil REST backend.

**Task:**
- [x] Scaffold `app/`: Auth (Supabase Auth UI), Dashboard — Riverpod + dio (Transaksi/Kategori/Akun list menyusul di polish)
- [x] Charts dashboard (income/expense/net) — **tap → detail, tanpa long-press**
- [ ] Widget + golden test 5 layar kritis (Dashboard, Login, Transaction List, Add Transaction, Accounts) — sementara: format_test 4 + widget_test 6 (10 passed)
- [ ] CI: `flutter analyze` + test; workflow macOS runner build iOS + upload TestFlight (milestone besar)
- [ ] Checkpoint: Android teruji di device (APK demo siap install); iOS CI hijau + tester eksternal ≥1x

---

## Fase 5 — OCR Foto Nota (target 1.5-2 minggu)

- [ ] `core/receipt_ocr.py`: vision via `call_llm()` (env-driven) — reuse logika v1 (127 test backend sudah mencakup parser & telegram photo)
- [ ] Gambar nota → **Supabase Storage** (bucket privat, signed URL) — menggantikan local storage v1
- [ ] Flutter: capture/upload + konfirmasi/edit item (US-08)
- [ ] Bot: forward foto → OCR → konfirmasi (reuse v1 flow)

---

## Fase 7 — UI/UX Polish (paralel Fase 4-5, target 1-1.5 minggu)

- [ ] Konsistensi DESIGN.md: palet dusty slate (#3B5B8C light / #7B9ED4 dark), Manrope + IBM Plex Mono, elevation terarah, radius 12/8dp, spacing 4dp
- [ ] Anti-slop checklist (DESIGN.md §2) direview per layar
- [ ] Voice & microcopy konsisten (DESIGN.md §7)

---

## Fase 6 — Deploy Produksi (target 2-3 hari)

- [ ] Railway/Render: backend & bot (auto-deploy dari GitHub push) — ganti VPS + Cloudflare tunnel
- [ ] Supabase **production** project (terpisah dari dev)
- [ ] Env production: SUPABASE_SERVICE_ROLE_KEY, LLM key, BOT_SERVICE_TOKEN
- [ ] Flutter Web → Vercel/Netlify
- [ ] Review keamanan: RLS production, tidak ada key ter-commit; CVE check (pip-audit, npm audit, dart pub outdated)

---

## Timeline v2 (ringkas, detail di ROADMAP §3)

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
| Fase 7 — Polish (paralel) | 1-1.5 minggu | tidak menambah |
| Fase 6 — Deploy Produksi | 2-3 hari | **~10.3 minggu** |

**Realitas:** ~10-11 minggu (2.5 bulan). Evaluasi hasil pivot setelah Fase 1 (~1.8 minggu), bukan di tengah Fase 4/5 (ROADMAP §4).

---

## Completed Phases

### Fase 4 — Flutter App: Android + iOS + Web ✅ (2026-08-27)

**Goal:** dashboard Flutter dengan line chart interaktif (ketuk titik → detail), siap-pasang APK demo, dan kredensial demo.

**Keputusan implementasi (chain of thought):**
- **Interaksi chart**: `LineTouchData(enabled: true, handleBuiltInTouches: false)` + `touchCallback` yang **hanya** merespons `FlTapUpEvent` → long-press/drag tidak punya handler sama sekali sehingga dihapus total. Ketuk titik → `onPointTap(index)` → `_DetailPanel` tampil.
- Titik terpilih diperbesar (`getDotPainter`) + garis putus-putus vertikal (`ExtraLinesData dashArray [4,4]`); interval label X adaptif; compact number ("5rb", "1,2jt").
- Config build-time via `--dart-define` (`SUPABASE_URL`, `SUPABASE_ANON_KEY` = public-by-design, `APP_BASE_URL` default `http://localhost:8000`) — `AppConfig.isConfigured` guard.
- APK demo: build release dengan config ter-embed (`APP_BASE_URL=http://103.27.206.22:8000` — IP publik VPS, backend listen 0.0.0.0:8000), tanda tangan debug cert (cukup untuk demo; produksi perlu keystore sendiri).

**Hasil (terverifikasi):**
- [x] `flutter analyze` bersih; `flutter test` **10 passed** (format_test 4 + widget_test 6).
- [x] `scripts/seed_demo.py` (idempotent) → user **demo@mymoney.dev / Demo1234!**, akun Cash, **37 transaksi** 14 hari; verifikasi live: login 200, accounts 200, summary month (income 7.000.000 / expense 1.162.055 / net 5.837.945).
- [x] APK: `app/build/app/outputs/flutter-apk/app-release.apk` (52.8MB) — config terverifikasi di dalam APK via `strings libapp.so`.
- [x] Perbaikan lingkungan: gradle `-Xmx2G` (8G → OOM-kill di RAM 7.8Gi), `.gitignore` root `lib/` tidak lagi meng-ignore `app/lib/`, `sdk.dir=/opt/android-sdk`.

### Fase 3.5 — Accounts Management CRUD ✅ (2026-08-26)

**Goal:** CRUD akun + soft-delete (bukan hard delete) + saldo computed + balancing Transfer saat nonaktifkan akun berisi saldo.

**Keputusan implementasi (chain of thought):**
- Seluruh API akun sudah ada sejak Fase 0-1 (reuse v1): `POST /api/accounts` (201), `GET /api/accounts` (aktif default; `?include_inactive=true`), `GET /api/accounts/{id}`, `PUT /api/accounts/{id}`, `POST /api/accounts/{id}/deactivate`. **TIDAK ada route DELETE** — hard delete dilarang (CODING_RULES §2.8).
- `_compute_balance` = satu query agregasi SQL: `initial_balance + SUM(CASE type='income' THEN +amount ELSE -amount)` dengan `func.cast(case(...), Transaction.total_amount.type)` + `func.coalesce(..., Decimal("0.00"))`.
- **Fix nyata (1)**: SUM atas `Numeric(14,2) * cast` melebarkan skala → `80000.0000`; dinormalisasi `quantize(Decimal("0.01"))` agar API konsisten 2 desimal.
- Deactivate dengan saldo ≠ 0 → wajib `target_account_id` (400/400/404 untuk tanpa target / sama dengan source / tak ditemukan); buat 2 transaksi Transfer atomik (expense di source + income di target) + audit; kategori Transfer = seed global migration `0001` (reuse `get_or_create_category`, tanpa duplikat per-user).
- §2.8 aktif: akun nonaktif ditolak transaksi baru (`_verify_category_and_account` → 422), tetap muncul penuh di riwayat/laporan historis.

**Hasil (terverifikasi):**
- [x] `test_accounts_api.py` **15 test**: auth 401, create + validasi, list aktif default / `include_inactive`, update, get/update nonaktif → 404, **no-delete 405**, deactivate saldo 0, deactivate butuh target (400/400/404), transfer balancing (saldo pindah + 2 tx ber-note "Saldo dipindah" + kategori Transfer global), §2.8 422.
- [x] `pytest` **145 passed** (130 baseline + 15); `ruff`/`black` bersih.

### Fase 3 — Report Dasar ✅ (2026-08-26)

**Goal:** SQL aggregation (bukan Python loops) untuk summary per periode + endpoint REST untuk chart + Telegram `/report`.

**Keputusan implementasi (chain of thought):**
- Service sudah dibangun sejak Fase 0-1 (reuse v1 yang sudah matang): `parse_period_arg` (hari-ini/minggu-ini/bulan-ini/bulan-lalu + sinonim EN, default bulan ini), `get_report_summary` (SQL `SUM`/`GROUP BY` per tipe + per kategori), `get_report_trend` (deret harian **zero-filled**, timezone user via `func.timezone`).
- `GET /api/reports/summary` + `GET /api/reports/trend` di `api/reports.py` (terdaftar sejak Fase 1): period `today|week|month|last-month` ATAU custom `start`/`end`; 422 untuk period invalid / `start >= end`; auth `require_active_user` (Supabase JWT); timezone dari `profiles.timezone` (default Asia/Jakarta).
- Telegram `/report` (US-17) di `telegram_service.py`: parse arg → timezone user dari DB → `get_report_summary` → `_format_report` (teks ringkas per kategori).
- Fase ini = **verifikasi & dokumentasi**: semua komponen sudah teruji; tidak ada kode baru yang diperlukan.

**Hasil (terverifikasi):**
- [x] `test_report_service.py` (aggregation: totals per tipe, breakdown per kategori urut terbesar; trend: zero-fill tiap hari) + `test_reports_api.py` (401 tanpa token, default month, 4 period valid, invalid → 422, custom range, range terbalik → 422, trend points) = **24 test**.
- [x] `test_telegram_service.py`: 4 test `/report` (requires link, default this month, `minggu ini` → this week, timezone user dipakai).
- [x] `pytest` **130 passed**; `ruff check`/`black --check` bersih.
- [x] Verifikasi live: route `/api/reports/summary` & `/trend` terdaftar di OpenAPI; tanpa token → 401; test integration memakai Supabase JWT asli.

### Fase 2 — Telegram Bot Node + Parsing Teks ✅ (2026-08-26)

**Goal:** bot Node/Telegraf (`bot/`) jadi thin proxy ke REST backend (service-to-service token); endpoint linking dibangun ulang untuk v2; `nlu_parser` env-driven; cutover webhook.

**Keputusan implementasi (chain of thought):**
- Bot = **pure proxy**: tidak ada command handler lokal. Backend `telegram_service.py` sudah menangani semua command — handler `/start` lokal di `bot/src/index.ts` justru men-shadow logic linking backend → **dihapus**. Bot forward semua update → backend, backend membalas via Bot API (tidak ada double-reply).
- Webhook backend menerima **dua jalur auth**: `X-Bot-Token` (service-to-service, produksi) ATAU `X-Telegram-Bot-Api-Secret-Token` (fallback langsung Telegram→backend, dipakai saat dev sebelum bot di-deploy).
- Linking v2: form email/password v1 TIDAK mungkin (kredensial milik Supabase Auth, tanpa verifikasi lokal). Ganti dengan **OTP Supabase**: halaman HTML minta email → kirim OTP via `/auth/v1/otp` (anon key, aman di client) → user masukkan kode → `/auth/v1/verify` → `POST /api/telegram/link/confirm` (JWKS + upsert relink semantics).
- `nlu_parser` sudah env-driven via `call_llm()` sejak Fase 0; kategori locked list → "Other" sudah aktif — tidak ada perubahan.
- Archive bot Python: **NO-OP** — bot Python tidak pernah ada di repo (bot selalu Node dari Fase 0); tercatat jujur.
- Cutover webhook penuh = Fase 6 (butuh URL publik bot; `BOT_PUBLIC_URL` baru ditambahkan, default localhost:3000).

**Hasil (terverifikasi):**
- [x] `bot/src/index.ts` di-rewrite jadi pure proxy (typecheck + lint + build bersih).
- [x] `telegram_webhook.py`: verifikasi `X-Bot-Token` ATAU secret Telegram (403 tanpa keduanya); `register-webhook` → `BOT_PUBLIC_URL/webhook`.
- [x] `config.py` + `.env.example`: field `bot_public_url` / `BOT_PUBLIC_URL`.
- [x] `telegram_linking.py` baru: `GET /api/telegram/link` (HTML OTP, DESIGN.md tokens, /static/icon.png) + `POST /api/telegram/link/confirm` (decode link token → JWKS → upsert, relink semantics); terdaftar di `main.py`.
- [x] Test baru: `test_telegram_webhook_api.py` (403/200 dua jalur) + `test_telegram_linking_api.py` (7 test: form valid/invalid, confirm sukses/idempoten/not-found/401/relink). **pytest 130 passed**; `ruff`/`black` bersih.
- [x] E2E live: curl → bot :3000 (secret valid) → forward `X-Bot-Token` → backend webhook 200 → `/start` diproses → `sendMessage` ke chat acak gagal 400 "chat not found" (ekspektasi, membuktikan reply flow aktif).
- [x] `models/profile.py`: tambah `TYPE_CHECKING` imports — warning Pylance `reportUndefinedVariable` hilang.

### Fase 1.5 — Auth Recovery: Reset Password ✅ (2026-08-26)

**Goal:** tidak ada role admin (semua user self-register); hapus kolom `role`; pastikan sistem reset password via OTP/link ke email terdaftar (Supabase Auth) terverifikasi & terdokumentasi.

**Hasil (terverifikasi):**
- [x] Migration `0007_drop_profile_role.py` (di-run): drop constraint `ck_profiles_role` → drop kolom `role`. Verifikasi `information_schema`: kolom `profiles` = id, display_name, timezone, is_active, created_at, updated_at (tanpa role/constraint).
- [x] Model `Profile` tanpa field `role`; `require_role` dihapus dari `api/deps.py` (tidak ada admin — semua user self-register).
- [x] Verifikasi live reset password: `POST /auth/v1/recover` → `200`; anti-enumeration (email tak dikenal juga `200`); rate-limit email (`over_email_send_rate_limit`); password lama tetap valid setelah recover (login `200`).
- [x] Dokumentasi: DATABASE.md §8 (flow recover + OTP + catatan), REQUIREMENTS.md US-02a; referensi role/admin dibersihkan dari ARCHITECTURE/ROADMAP/task/walkthrough.
- [x] `pytest` hijau; `ruff check`/`black --check` bersih.

### Fase 1 — Backend Inti + Auth Supabase ✅ (2026-08-27)

**Goal:** REST API v2 di atas Supabase — auth = Supabase JWT; profile auto-create via trigger; CRUD transaksi (service layer); unit test.

**Hasil (terverifikasi):**
- [x] Migration `0006_fk_profiles.py` (di-run): drop 6 FK `*_user_id_fkey` → drop tabel `users` → re-create FK ke `profiles.id` (CASCADE). Verifikasi `information_schema`: tabel `users` hilang, semua FK → `profiles`.
- [x] Model `Profile` (1:1 `auth.users`, trigger `on_auth_user_created`); semua model ORM (account/category/transaction/telegram_link/pending_transaction/audit_log) ber-FK `profiles.id`; `models/user.py` dihapus.
- [x] `verify_supabase_jwt()` di `core/security.py`: fetch JWKS (cache TTL 300 s), dukung **RS256 + ES256** (proyek ini ternyata ES256 P-256 — dibuktikan live), fallback HS256 bila `SUPABASE_JWT_SECRET` diisi; return `sub`.
- [x] `api/deps.py`: `get_current_user` (Bearer → verify → `db.get(Profile)` → 401), `require_active_user` (403).
- [x] Auth custom v1 dihapus: `api/auth.py`, `api/telegram_linking.py`, `schemas/auth.py`, `models/user.py`; `main.py` 23 route (25 setelah linking dibangun ulang di Fase 2).
- [x] Test suite v2: conftest (mimic `auth.users`, fixture `profile` + `supabase_factory` auto-skip tanpa kredensial); service layer + API tests memakai Supabase JWT asli. **118 passed**; `ruff check`/`black --check` bersih.
- [x] E2E live: tanpa token → 401; token asli → 200; CRUD akun/transaksi + report summary/trend sukses.

### Fase 0 — Setup Fondasi Baru ✅ (2026-08-26, commit `29abccc`)

**Goal:** fondasi terhubung — Supabase satu-satunya sumber data; backend FastAPI terhubung ke Supabase Postgres; Alembic target Supabase; Flutter init; bot Node init; CI lint 3 ekosistem.

**Hasil (terverifikasi):**
- [x] Project Supabase dibuat user (ref `fqjkqcigjeyooejcgbrk`, region **ap-northeast-1/Tokyo**) + Auth email
- [x] Migration `0005_supabase_profiles.py`: `profiles` + trigger `handle_new_user` + RLS 7 tabel — `alembic upgrade head` sukses di Supabase
- [x] Backend: settings Supabase/LLM env-driven di `core/config.py`; `DATABASE_URL` → Supabase pooler (Tokyo, IPv4); `/health` 200
- [x] Init `app/` Flutter (Riverpod, supabase_flutter, dio) + AuthScreen — `flutter analyze` bersih, test 2/2
- [x] Init `bot/` Node/Telegraf/TypeScript — typecheck + lint bersih
- [x] GitHub Actions: job `app` (flutter) + `bot` (node) ditambah ke `ci.yml`
- [x] `.env` lokal terisi (Supabase keys, LLM deepseek, Telegram, bot token)
- [x] Checkpoint end-to-end: signup Supabase Auth → `profiles` auto-terisi trigger (tz=Asia/Jakarta)

### v1 — Stack lama (archived, selesai 2026-08-25)

Rekam historis implementasi v1 (Kotlin + FastAPI + Postgres self-hosted + bot Python + VPS/Cloudflare), semua fase selesai & ter-deploy:

- **Phase 0-3** (backend, Telegram, report) — 88+ tests, live.
- **Phase 4** Android Kotlin — 23 tests, APK, icon dari `./icon.png`.
- **Phase 5** OCR vision + Telegram foto — 127 tests, deployed live.
- Kode v1: `_archive/android-kotlin-v1/`; detail historis di git history (`git log main`). Backend v1 tetap live sampai cutover Fase 2/6.
