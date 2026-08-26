# task.md — MyMoney To-Do List

> Phased execution checklist — **v2 stack** (Supabase + FastAPI + Flutter + Node bot).
> Update status as you work. Current phase: **Fase 0**.
> Saat fase selesai, pindahkan item ke `## Done` dan unmute fase berikut.

Legend: `[ ]` pending · `[x]` done · `[~]` in progress

---

## Fase 0 — Setup Fondasi Baru (current)
- [ ] Buat project Supabase + Auth providers (email, Google OAuth minimal)
- [ ] RLS policies dasar + trigger `handle_new_user` (profiles)
- [ ] Backend: `DATABASE_URL` → Supabase (pooler); `/health` 200
- [ ] Alembic target Supabase; `upgrade head` sukses
- [ ] Init `app/` Flutter (Riverpod, supabase_flutter, dio)
- [ ] Init `bot/` Node/Telegraf/TypeScript
- [ ] GitHub Actions: ruff/black, dart analyze, eslint
- [ ] `.env` lokal dari `.env.example`

**Checkpoint:** backend jalan lokal terhubung Supabase; Flutter register/login via Supabase Auth; migration sukses.

## Fase 1 — Backend Inti + Auth Supabase (next)
- [ ] `verify_supabase_jwt()` (JWKS RS256, cache) di `core/security.py`
- [ ] `require_active_user` baca uid token → profiles
- [ ] CRUD transaksi service layer (FK → profiles) + audit trail
- [ ] Trigger auto-create profiles terverifikasi
- [ ] Unit test service layer

**Checkpoint:** register via Supabase Auth → profile auto-buat; CRUD via Postman.

## Fase 1.5 — RBAC Admin
- [ ] `/admin/users/*` + `require_role("admin")`
- [ ] Seed admin pertama (SQL manual)

## Fase 2 — Telegram Bot Node + Parsing Teks
- [ ] `bot/` webhook Telegraf → REST backend (`BOT_SERVICE_TOKEN`)
- [ ] Command `/start`, `/logout`, NL text, `/report`, `/undo`, `/edit`
- [ ] `nlu_parser` via `call_llm()` (env-driven); kategori locked list
- [ ] Cutover webhook ke `bot/`; archive bot Python → `_archive/bot-python-v1/`

## Fase 3 — Report Dasar
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

### v1 — Stack lama (archived, selesai 2026-08-25)
- [x] Backend FastAPI + Postgres self-hosted + JWT custom (Phase 0-3)
- [x] Telegram bot Python + NL parsing + report (Phase 2-3)
- [x] Android Kotlin (Phase 4) — 23 tests, APK, icon `./icon.png`
- [x] OCR vision + Telegram foto (Phase 5) — 127 tests, deployed
- [x] Kode v1 di `_archive/android-kotlin-v1/`; detail di git history
