# walkthrough.md — MyMoney v2 Execution Guide

> ✅ **Pivot v2 (2026-08-26)**: stack baru Supabase + FastAPI + Flutter + Node bot.
> 6 dokumen inti sudah ditulis ulang; `android/` v1 di `_archive/android-kotlin-v1/`.
> Panduan di bawah adalah cara mengeksekusi **Fase 0** (fase berjalan).
> Guide fase berikutnya diisi saat fase itu dimulai (placeholder di bawah).
> Rekam historis v1 ada di git history + `_archive/`.

---

## Fase 0 — Setup Fondasi Baru (current)

**Tujuan:** fondasi terhubung — Supabase sebagai sumber data, backend FastAPI
terhubung, Flutter & bot Node ter-init, CI lint 3 ekosistem.
**Checkpoint (DoD):** backend lokal ↔ Supabase OK; Flutter register/login via
Supabase Auth; `alembic upgrade head` sukses.

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
     `display_name`, `role` (default 'user', CHECK), `timezone` (default
     'Asia/Jakarta'), `is_active`, `created_at`, `updated_at`.
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

## Fase 1 — Backend Inti + Auth Supabase (placeholder)
> Goal & task: lihat `IMPLEMENTATION_PLAN.md` Fase 1. Diisi langkah detail saat
> fase dimulai (pola sama seperti Fase 0 di atas).

## Fase 1.5 — RBAC Admin (placeholder)
## Fase 2 — Telegram Bot Node + Parsing Teks (placeholder)
## Fase 3 — Report Dasar (placeholder)
## Fase 3.5 — Accounts CRUD (placeholder)
## Fase 4 — Flutter App (placeholder)
## Fase 5 — OCR Foto Nota (placeholder)
## Fase 7 — UI/UX Polish (placeholder)
## Fase 6 — Deploy Produksi (placeholder)

---

## v1 — Rekam historis (COMPLETE ✅, 2026-08-25)

> Stack lama (Kotlin + FastAPI + Postgres self-hosted + bot Python) selesai &
> ter-deploy. Kode di `_archive/android-kotlin-v1/`; detail per-fase ada di
> git history. Panduan eksekusi v1 dihapus dari file ini saat pivot v2.
