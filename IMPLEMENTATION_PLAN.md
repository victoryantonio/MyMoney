# IMPLEMENTATION_PLAN.md — MyMoney

> Planning doc for the **current** phase of work.
> Each phase gets its own section. When work moves to a new phase, this file is
> edited so the "Current Phase" points at the active one and completed phases
> move under `## Completed Phases`.

**Current Phase: Fase 0 — Setup Fondasi Baru (Supabase + Flutter + Node bot)**

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

## Fase 0 — Setup Fondasi Baru (current, target 3-4 hari)

**Goal:** fondasi terhubung — Supabase (project + Auth + RLS dasar) satu-satunya
sumber data; backend FastAPI terhubung ke Supabase Postgres; Alembic target
Supabase; Flutter init; bot Node init; CI lint 3 ekosistem.

**Current reality (verified):** backend v1 live (`api.mymoneyofficial.online`,
Postgres self-hosted via docker-compose, bot Python di `backend/app/core/`);
`android/` v1 di `_archive/`; Flutter & Node **belum terinstall** di environment.

**Definition of done (ROADMAP §Fase 0):** backend jalan lokal terhubung Supabase;
Flutter bisa register/login via Supabase Auth; migration sukses.

**Task:**
- [ ] Buat project Supabase + Auth providers (email, Google OAuth) — panduan di `walkthrough.md` Fase 0 Step 1 (user yang buat di dashboard)
- [ ] Migration: tabel `profiles` + trigger `handle_new_user` + RLS dasar (profiles, transactions, accounts, categories) — DATABASE.md §2.1
- [ ] Backend: settings Supabase di `core/config.py`; `DATABASE_URL` → Supabase (pooler); verifikasi koneksi; `/health` 200
- [ ] Alembic target Supabase (`alembic/env.py`); `upgrade head` sukses
- [ ] Init `app/` Flutter (Riverpod, supabase_flutter, dio) + layar Auth minimal
- [ ] Init `bot/` Node/Telegraf/TypeScript (scaffold webhook minimal)
- [ ] GitHub Actions: ruff/black (backend), `dart analyze` (app), eslint (bot)
- [ ] `.env` lokal dari `.env.example` (Supabase keys terisi)

**Verification (checkpoint):** `walkthrough.md` Fase 0 Step 7.

---

## Fase 1 — Backend Inti + Auth Supabase (target 1 minggu)

**Goal:** REST API v2 di atas Supabase: auth = Supabase JWT; profile auto-create
via trigger; CRUD transaksi (service layer); unit test.

**Keputusan & alasan (chain of thought):**
- Verifikasi JWT via **JWKS RS256** dari `/auth/v1/.well-known/jwks.json` (default Supabase modern), public key di-cache — bukan decode HS256 manual. `SUPABASE_JWT_SECRET` hanya fallback opsional.
- `profiles.id == auth.users.id` (1:1) via trigger `on_auth_user_created` (DATABASE.md §2.1). Admin pertama di-seed manual SQL.
- Endpoint login/register custom **dihapus** — digantikan Supabase Auth langsung dari Flutter (`supabase_flutter` SDK) & bot. Backend hanya verifikasi token.
- `require_active_user` membaca `sub`/`auth.uid` dari token → lookup `profiles`.

**Task:**
- [ ] `core/security.py`: `verify_supabase_jwt()` (JWKS, cache, expired check)
- [ ] `api/deps.py`: `require_active_user` (uid → profiles) + `require_role`
- [ ] `core/transaction_service.py`: CRUD transaksi (FK → profiles), audit trail tetap; pagination cursor tetap
- [ ] RLS + trigger terverifikasi (query sebagai user via anon key)
- [ ] Unit test service layer (pytest; DB test = schema terpisah di Supabase atau Postgres lokal mirror)
- [ ] `.env.example` final (env-driven LLM sudah di Fase 0)

**Verification:** register via Supabase Auth → `profiles` auto-buat; CRUD transaksi via Postman dengan Supabase JWT asli; tanpa token → 401.

---

## Fase 1.5 — RBAC Admin (target 2 hari)

- [ ] Endpoint `/admin/users/*` + `require_role("admin")` (kolom `role` sudah ada di `profiles`)
- [ ] Seed admin pertama (SQL manual)

---

## Fase 2 — Telegram Bot Node + Parsing Teks (target 1-1.5 minggu)

**Goal:** bot Node/Telegraf (`bot/`) menggantikan bot Python; forward ke REST backend (service-to-service token); `nlu_parser` Python tetap di backend.

**Keputusan & alasan (chain of thought):**
- Bot = thin client murni: tidak query Supabase langsung, tidak parsing LLM sendiri (ARCHITECTURE §3.2, CODING_RULES §2.2) — semua logic di backend.
- Service-to-service auth: header `X-Bot-Token` / Bearer `BOT_SERVICE_TOKEN` diverifikasi middleware backend (bukan Supabase JWT user).
- `telegram_links` tetap di backend (map telegram_id → profiles).
- Bot Python lama di-archive → `_archive/bot-python-v1/` setelah cutover.
- LLM env-driven: `call_llm()` memakai OPENROUTER (default) atau DEEPSEEK; model dari `LLM_TEXT_MODEL`/`LLM_VISION_MODEL` + fallback chain.

**Task:**
- [ ] `bot/`: webhook Telegraf + verifikasi secret + forward ke backend
- [ ] Command: `/start` (link), `/logout`, NL text, `/report`, `/undo`, `/edit` (fungsi sama seperti v1, dipanggil lewat REST)
- [ ] Backend: endpoint bot proxy + verifikasi `BOT_SERVICE_TOKEN`
- [ ] `nlu_parser` via `call_llm()` env-driven; kategori locked list → "Other"
- [ ] Cutover: set webhook Telegram ke `bot/`; matikan bot Python
- [ ] Archive bot Python → `_archive/bot-python-v1/`

---

## Fase 3 — Report Dasar (target 3-5 hari)

- [ ] `core/report_service.py`: `parse_period_arg` + `get_report_summary` (SQL-only SUM/GROUP BY) — **reuse v1** (sudah matang), sesuaikan FK
- [ ] `GET /api/reports/summary` + Telegram `/report`
- [ ] Test service + API (adaptasi dari v1: 22 test)

---

## Fase 3.5 — Accounts Management CRUD (target 1 minggu)

- [ ] CRUD akun, soft-delete (`is_active`), saldo computed — reuse v1
- [ ] Kategori sistem baru: Transfer/Penyesuaian Akun (DATABASE.md §2.4)

---

## Fase 4 — Flutter App: Android + iOS + Web (target 3-3.5 minggu)

**Goal:** satu codebase Flutter (`app/`) untuk 3 platform, konsumsi REST backend dengan Supabase JWT.

**Keputusan & alasan (chain of thought):**
- Auth: `supabase_flutter` SDK (session + refresh otomatis) — REST call pakai Supabase JWT di header (backend verifikasi).
- State: **Riverpod** (rekomendasi solo dev, mudah di-test); chart: `fl_chart` / `syncfusion_flutter_charts` (keputusan saat Step 3, DESIGN.md §8).
- iOS: build via GitHub Actions macOS runner; TestFlight ($99/tahun) + tester eksternal minimal 1 orang — **CI hijau saja tidak cukup** (ROADMAP §Fase 4).
- Web: deploy static (Vercel/Netlify), tetap panggil REST backend.

**Task:**
- [ ] Scaffold `app/`: Auth (Supabase Auth UI), Dashboard, Transaksi list/form, Kategori, Akun — Riverpod + dio
- [ ] Charts dashboard (income/expense/net + breakdown kategori)
- [ ] Widget + golden test 5 layar kritis (Dashboard, Login, Transaction List, Add Transaction, Accounts)
- [ ] CI: `flutter analyze` + test; workflow macOS runner build iOS + upload TestFlight (milestone besar)
- [ ] Checkpoint: Android teruji di device; iOS CI hijau + tester eksternal ≥1x

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
| Fase 1.5 — RBAC Admin | 2 hari | ~1.8 minggu |
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

### v1 — Stack lama (archived, selesai 2026-08-25)

Rekam historis implementasi v1 (Kotlin + FastAPI + Postgres self-hosted + bot Python + VPS/Cloudflare), semua fase selesai & ter-deploy:

- **Phase 0-3** (backend, Telegram, report) — 88+ tests, live.
- **Phase 4** Android Kotlin — 23 tests, APK, icon dari `./icon.png`.
- **Phase 5** OCR vision + Telegram foto — 127 tests, deployed live.
- Kode v1: `_archive/android-kotlin-v1/`; detail historis di git history (`git log main`). Backend v1 tetap live sampai cutover Fase 2/6.
