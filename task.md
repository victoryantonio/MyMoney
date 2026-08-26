# task.md — MyMoney To-Do List

> Phased execution checklist — **v2 stack** (Supabase + FastAPI + Flutter + Node bot).
> Update status as you work. Current phase: **Fase 4**.
> Saat fase selesai, pindahkan item ke `## Done` dan unmute fase berikut.

Legend: `[ ]` pending · `[x]` done · `[~]` in progress

---

## Fase 4 — Flutter App (Android + iOS + Web) (current)
- [x] Scaffold + layar kritis (Auth, Dashboard, Transaksi, Kategori, Akun)
- [x] Charts; widget/golden test 5 layar; CI iOS + TestFlight
- [ ] Checkpoint: Android device OK; iOS CI hijau + tester eksternal ≥1x

## Fase 5 — OCR Foto Nota
- [ ] `receipt_ocr` vision (env-driven) + Supabase Storage (signed URL)
- [ ] UI Flutter capture/konfirmasi + bot foto

## Fase 6 — UI/UX Polish (paralel)
- [ ] Konsistensi DESIGN.md + anti-slop checklist

## Fase 7 — Deploy Produksi
- [ ] Railway/Render backend & bot; Supabase production
- [ ] Flutter Web → Vercel/Netlify; review keamanan RLS

---

## Done

### Fase 4 — Flutter App (Android + iOS + Web) ✅ (2026-08-27, commit `a0c6a12`)
- [x] **Line chart tap-detail, TANPA long-press**: `TrendChart` (fl_chart 1.1.0) memakai `LineTouchData(enabled, handleBuiltInTouches: false)` + handler **hanya** `FlTapUpEvent` → ketuk titik langsung tampil detail hari itu di panel bawah; long-press & drag diabaikan total
- [x] Dashboard: kartu ringkasan (Net/Pemasukan/Pengeluaran), selector periode (7 hari / Bulan ini), `RefreshIndicator`, `_ErrorView` + retry, logout; `_DetailPanel` tampilkan tanggal + pemasukan/pengeluaran/net saat titik diketuk
- [x] Format utils (`lib/core/format.dart`): `formatRupiah` (IDR, ribuan pakai titik), `formatRupiahSigned`, `formatDateShort` ("12 Agu"), `formatAxisLabel`, `formatDateDetail` ("Rab, 12 Agu") — `format_test.dart` 4 test
- [x] `main.dart` AuthGate → `DashboardScreen` setelah login (bukan placeholder); `flutter analyze` **bersih** + `flutter test` **10 passed**
- [x] **APK demo siap install**: `app/build/app/outputs/flutter-apk/app-release.apk` (52.8MB, config Supabase + backend ter-embed via `--dart-define`; tanda tangan debug cert — cukup untuk demo); debug APK juga tersedia
- [x] **Kredensial demo**: email `demo@mymoney.dev` / password `Demo1234!` — dibuat via `scripts/seed_demo.py` (idempotent), sudah diverifikasi end-to-end: login 200, `GET /api/accounts` 200, summary bulan ini (income 7.000.000 / expense 1.162.055 / net 5.837.945)
- [x] Perbaikan lingkungan: `android/gradle.properties` memori diturunkan ke `-Xmx2G` (sebelumnya `-Xmx8G` → daemon OOM-kill saat build release); `.gitignore` root: `lib/` konvensi Python **meng-ignore `app/lib/`** → ditambahkan `!app/lib/` + `!app/lib/**`; `sdk.dir=/opt/android-sdk` di `android/local.properties` (path SDK salah di mesin ini)
- [x] Docs: walkthrough.md + IMPLEMENTATION_PLAN.md + ROADMAP.md (bagian Fase 4 ter-isi)

### Fase 3.5 — Accounts CRUD ✅ (2026-08-26)
- [x] CRUD akun: `POST /api/accounts` (201), `GET /api/accounts` (aktif default, `?include_inactive=true`), `GET /api/accounts/{id}`, `PUT /api/accounts/{id}` — semua sudah ada sejak Fase 0-1 (verifikasi, tanpa perubahan)
- [x] **Soft-delete, TANPA hard delete**: `POST /api/accounts/{id}/deactivate` (is_active=False); route DELETE → **405** (terbukti di test)
- [x] Saldo computed: `_compute_balance` satu query agregasi (initial + Σ income − Σ expense); `current_balance` & `net_balance` dinormalisasi 2 desimal (fix `quantize` — SUM melebarkan skala ke 4 desimal)
- [x] Deactivate dengan saldo ≠ 0 → wajib `target_account_id` (400 tanpa target, 400 target = source, 404 target tak ditemukan); buat 2 transaksi Transfer (expense+income) atomik + audit
- [x] Kategori Transfer (expense + income) global seeded di migration `0001`; deactivate reuse via `get_or_create_category` — tidak ada duplikat per-user
- [x] CODING_RULES §2.8 aktif: akun nonaktif ditolak di transaksi baru (**422**), tapi tetap muncul penuh di riwayat/laporan historis
- [x] Test: `test_accounts_api.py` **15 test** (CRUD, validasi, auth, no-delete 405, deactivate balancing, §2.8) — `pytest` **145 passed** (130 + 15); `ruff`/`black` bersih

### Fase 3 — Report Dasar ✅ (2026-08-26)
- [x] `report_service.py` SQL aggregation (`SUM`/`GROUP BY`): `parse_period_arg` (hari-ini/minggu-ini/bulan-ini/bulan-lalu) + `get_report_summary` + `get_report_trend` (zero-filled daily, timezone user)
- [x] `GET /api/reports/summary` (total income/expense/net + breakdown per kategori) + `GET /api/reports/trend` (deret harian) — auth Supabase JWT, period/custom range, 422 validasi
- [x] Telegram `/report` (US-17) — `_format_report` render ringkas; `period_label`; timezone user dari DB
- [x] Test: `test_report_service.py` + `test_reports_api.py` (24 test) + `/report` di `test_telegram_service.py` — `pytest` 130 hijau, `ruff`/`black` bersih
- [x] Verifikasi live: route terdaftar di OpenAPI; tanpa token → 401; test integration memakai Supabase JWT asli

### Fase 2 — Telegram Bot Node + Parsing Teks ✅ (2026-08-26)
- [x] `bot/` pure proxy: webhook Telegraf verifikasi secret → forward ke backend dengan `X-Bot-Token` (BOT_SERVICE_TOKEN) — handler `/start` lokal yang men-shadow backend dihapus
- [x] Backend webhook: verifikasi `X-Bot-Token` ATAU `X-Telegram-Bot-Api-Secret-Token`; `register-webhook` → `BOT_PUBLIC_URL/webhook`; `config.py` + `.env.example` + `BOT_PUBLIC_URL`
- [x] Endpoint linking dibangun ulang: `GET /api/telegram/link` (HTML + OTP Supabase) + `POST /api/telegram/link/confirm` (JWKS + upsert telegram_links, relink semantics)
- [x] Command `/start`, `/logout`, NL text, `/report`, `/undo`, `/edit` — semua diproses backend `telegram_service.py` (sudah lengkap dari Fase 0-1, tanpa perubahan)
- [x] `nlu_parser` via `call_llm()` env-driven; kategori locked list → "Other" (sudah aktif)
- [x] Test: webhook API (403/200 X-Bot-Token/secret) + linking API (7 test) — `pytest` 130 hijau; bot typecheck/lint/build bersih; E2E live: curl → bot :3000 → backend → reply (chat not found, wajar)
- [x] Archive bot Python: **NO-OP** — bot Python tidak pernah ada di repo ini (hanya `bot/src/index.ts` Node dari awal); tercatat jujur
- [x] Cutover webhook penuh ditunda ke Fase 6 (butuh URL publik bot; `BOT_PUBLIC_URL` default localhost:3000)

### Fase 1.5 — Auth Recovery: Reset Password ✅ (2026-08-26)
- [x] Migration `0007`: hapus kolom `role` + constraint `ck_profiles_role` dari `profiles` (terverifikasi via `information_schema`)
- [x] Hapus `require_role` (`deps.py`) + field `role` (`Profile` model)
- [x] Verifikasi live reset password Supabase: `recover` 200, anti-enumeration, rate-limit email, login tetap jalan
- [x] Dokumentasi: DATABASE.md §8 + REQUIREMENTS.md US-02a; `pytest` hijau, `ruff`/`black` bersih

### Fase 1 — Backend Inti + Auth Supabase ✅ (2026-08-27)
- [x] Migration `0006`: drop `users` → FK semua tabel → `profiles.id` (CASCADE)
- [x] Model `Profile` (1:1 `auth.users`); semua model ORM ber-FK `profiles`
- [x] `verify_supabase_jwt()` (JWKS RS256 **+ ES256**, cache TTL) — terverifikasi live
- [x] `api/deps.py`: `get_current_user`/`require_active_user` (Profile)
- [x] Auth custom v1 dihapus (`auth.py`, `telegram_linking.py`, `schemas/auth.py`, `models/user.py`)
- [x] Test suite v2: service layer + API (Supabase live) — `pytest` 118 hijau, `ruff`/`black` bersih

### Fase 0 — Setup Fondasi Baru ✅ (2026-08-26, commit `29abccc`)
- [x] Project Supabase dibuat (ref `fqjkqcigjeyooejcgbrk`, region Tokyo) + Auth email
- [x] RLS policies + trigger `handle_new_user` (profiles) — migration `0005`
- [x] Backend: `DATABASE_URL` → Supabase pooler; `/health` 200
- [x] Alembic target Supabase; `upgrade head` sukses (0001–0005)
- [x] Init `app/` Flutter (Riverpod, supabase_flutter, dio) — analyze bersih, test 2/2
- [x] Init `bot/` Node/Telegraf/TypeScript — typecheck + lint bersih
- [x] GitHub Actions: job `app` (flutter) + `bot` (node)
- [x] `.env` lokal dari `.env.example` (Supabase keys terisi)

### v1 — Stack lama (archived, selesai 2026-08-25)
- [x] Backend FastAPI + Postgres self-hosted + JWT custom (Phase 0-3)
- [x] Telegram bot Python + NL parsing + report (Phase 2-3)
- [x] Android Kotlin (Phase 4) — 23 tests, APK, icon `./icon.png`
- [x] OCR vision + Telegram foto (Phase 5) — 127 tests, deployed
- [x] Kode v1 di `_archive/android-kotlin-v1/`; detail di git history
