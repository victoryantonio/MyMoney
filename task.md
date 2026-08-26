# task.md — MyMoney To-Do List

> Phased execution checklist — **v2 stack** (Supabase + FastAPI + Flutter + Node bot).
> Update status as you work. Current phase: **Fase 3**.
> Saat fase selesai, pindahkan item ke `## Done` dan unmute fase berikut.

Legend: `[ ]` pending · `[x]` done · `[~]` in progress

---

## Fase 3 — Report Dasar (current)
- [ ] `report_service` SQL aggregation + `/api/reports/summary` + `/report`

## Fase 3.5 — Accounts CRUD
- [ ] CRUD akun, soft-delete, saldo computed; kategori Transfer/Penyesuaian

## Fase 4 — Flutter App (Android + iOS + Web)
- [ ] Scaffold + layar kritis (Auth, Dashboard, Transaksi, Kategori, Akun)
- [ ] Charts; widget/golden test 5 layar; CI iOS + TestFlight
- [ ] Checkpoint: Android device OK; iOS CI hijau + tester eksternal ≥1x

## Fase 5 — OCR Foto Nota
- [ ] `receipt_ocr` vision (env-driven) + Supabase Storage (signed URL)
- [ ] UI Flutter capture/konfirmasi + bot foto

## Fase 7 — UI/UX Polish (paralel)
- [ ] Konsistensi DESIGN.md + anti-slop checklist

## Fase 6 — Deploy Produksi
- [ ] Railway/Render backend & bot; Supabase production
- [ ] Flutter Web → Vercel/Netlify; review keamanan RLS

---

## Done

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
