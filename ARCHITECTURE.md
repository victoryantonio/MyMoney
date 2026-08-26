# ARCHITECTURE.md — MyMoney (Revisi Stack v2)

## 1. Ringkasan Sistem

MyMoney adalah aplikasi pencatatan keuangan pribadi dengan input multi-kanal
(Telegram bot & Flutter app — Android/iOS/Web dari satu codebase), parsing
transaksi otomatis berbasis LLM (teks & foto nota), serta fitur pelaporan.
Backend Python tipis + Supabase (Postgres + Auth) sebagai fondasi data.

**Prinsip arsitektur inti (REVISI):**
- **Single source of truth tetap dipegang backend Python**: seluruh logic
  bisnis (buat transaksi, validasi, report, LLM parsing) hidup di satu
  service layer backend. Flutter app dan Telegram bot adalah *thin client*
  yang memanggil REST API yang sama — TIDAK ADA client yang query Supabase
  langsung untuk business logic (RLS tetap aktif sebagai defense-in-depth,
  bukan jalur utama akses data untuk write operation kompleks).
- **Supabase menggantikan self-hosted Postgres + custom JWT auth**: alasan
  solo dev — mengurangi effort membangun auth dari nol, tetap dapat akses
  penuh ke Postgres asli (bukan black-box), migrasi ke self-hosted tetap
  memungkinkan di masa depan kalau skala/biaya jadi masalah.
- **Satu codebase Flutter untuk 3 platform**: menggantikan rencana native
  Kotlin/Compose Android — menghemat effort maintain 2 basis kode UI terpisah.
- **Model routing berdasarkan kapabilitas**: tidak berubah dari desain awal.

## 2. Diagram Arsitektur Tingkat Tinggi

┌──────────────────────┐        ┌─────────────────────────┐
│   Flutter App         │        │   Telegram Bot            │
│ (Android/iOS/Web)      │        │  (Node.js + Telegraf)      │
│ satu codebase Dart      │        │  service terpisah          │
└───────────┬────────────┘        └────────────┬───────────────┘
            │ REST API (Supabase JWT)             │ REST API (internal auth)
            └───────────────┬──────────────────────┘
                             │
                  ┌──────────▼───────────┐
                  │  FastAPI Backend       │
                  │  (Python, Docker,       │
                  │   Railway/Render)         │
                  │ ┌──────────────────────┐ │
                  │ │ API Layer              │ │
                  │ │ - telegram_webhook     │ │
                  │ │ - transactions (REST)  │ │
                  │ │ - reports              │ │
                  │ │ (auth: verifikasi        │ │
                  │ │  Supabase JWT, bukan     │ │
                  │ │  generate sendiri)       │ │
                  │ └──────────┬─────────────┘ │
                  │            │                │
                  │ ┌──────────▼─────────────┐ │
                  │ │ Service Layer           │ │
                  │ │ - transaction_service   │ │
                  │ │ - nlu_parser             │ │
                  │ │ - receipt_parser         │ │
                  │ │ - report_service          │ │
                  │ │ - account_service          │ │
                  │ │ - audit_service             │ │
                  │ └──────────┬─────────────┘ │
                  └─────────────┼────────────────┘
                                │
             ┌──────────────────┼────────────────────┐
             │                  │                     │
    ┌────────▼─────────┐ ┌─────▼──────┐    ┌──────────▼───────────┐
    │  Supabase           │ │ GLM 5.2     │    │  Gemini 3.5 Flash-Lite │
    │  (Postgres + Auth +   │ │ (teks, via    │    │  (vision, via           │
    │   Storage + RLS)        │ │  OpenRouter)  │    │   OpenRouter)             │
    └───────────────────────┘ └─────────────┘    └────────────────────────┘

**Perubahan kunci dari desain awal:**
- VPS self-hosted → **Railway/Render** (managed cloud) untuk backend Python
  & bot Telegram. Postgres self-hosted → **Supabase managed Postgres**.
- Cloudflare Tunnel dihapus — Railway/Render sudah expose HTTPS domain
  langsung, tidak perlu tunnel tambahan.
- JWT generation/refresh custom → **Supabase Auth** (email, magic link,
  OAuth Google/Apple built-in). Backend memverifikasi token Supabase
  (JWKS), tidak generate token sendiri lagi.
- Kotlin/Jetpack Compose Android app → **Flutter (Dart)**, mencakup
  Android + iOS + Web dari satu codebase.

## 3. Komponen Sistem

### 3.1 Backend (FastAPI, Python, Docker → Railway/Render)
Tetap satu backend tunggal menangani seluruh logic bisnis. Perbedaan dari
desain awal: tidak lagi generate/refresh JWT sendiri — cukup verifikasi
token yang diterbitkan Supabase Auth di setiap request (middleware validasi
JWKS dari Supabase project).

| Layer | Tanggung Jawab |
|---|---|
| API Layer | Terima request dari Telegram webhook, Flutter app (REST), verifikasi Supabase JWT |
| Service Layer | Logic bisnis: transaksi, parsing (teks & gambar), report, akun — TIDAK BERUBAH dari desain awal |
| Data Layer | SQLAlchemy/asyncpg terhubung ke **Supabase Postgres** (connection string dari Supabase project settings) |
| Audit Service | Tetap sama — `audit_logs` tabel di Supabase, dicatat dari service layer |

**Aturan ketat (TIDAK BERUBAH)**: `telegram_webhook.py` dan `transactions.py`
hanya boleh memanggil service layer. Business logic tidak boleh ditulis di
Flutter (client) maupun Telegraf bot (Node) — keduanya thin client murni.

### 3.2 Telegram Bot (Node.js + Telegraf) — REVISI
- Service terpisah, deploy di Railway/Render (bukan numpang di app utama).
- **Memanggil REST API backend Python yang sama** (bukan query Supabase
  langsung) — menjaga single source of truth logic bisnis.
- Autentikasi bot ke backend: service-to-service token (bukan Supabase JWT
  user, karena bot bertindak atas nama sistem, dengan `telegram_id` di-map
  ke `user_id` internal via tabel `telegram_links` seperti desain awal).
- Alasan dipisah dari backend utama: mudah dimatikan/diganti independen,
  tidak mengotori deployment backend utama kalau bot bermasalah.

### 3.3 Flutter App (Android + iOS + Web, satu codebase) — REVISI TOTAL
Menggantikan rencana native Kotlin/Jetpack Compose sepenuhnya.
- State management: **Riverpod** (rekomendasi untuk solo dev — lebih
  eksplisit dan mudah di-test dibanding Provider/Bloc untuk kasus app
  sekompleks ini; boleh diganti Bloc kalau Anda lebih familiar).
- Autentikasi: **Supabase Flutter SDK** (`supabase_flutter` package) —
  langsung dapat session management, refresh token otomatis, tanpa Anda
  tulis ulang logic refresh token seperti rencana awal.
- Komunikasi ke backend: REST API biasa (Dio/http package) dengan Supabase
  JWT di header Authorization — backend Python yang verifikasi token ini.
- Web build: Flutter Web di-deploy sebagai static site (Vercel/Netlify/
  Railway static hosting) — TIDAK menggantikan kebutuhan backend Python,
  web app tetap panggil REST API yang sama seperti mobile.
- Fitur: input manual, foto nota (image_picker + camera package), lihat &
  edit transaksi, dashboard report (fl_chart atau syncfusion_flutter_charts).

**Implikasi positif yang perlu dicatat**: iOS otomatis masuk scope v1 tanpa
effort tambahan signifikan (kode UI sama), TAPI publikasi ke App Store tetap
butuh Apple Developer Program ($99/tahun), code signing, dan testing di
device iOS asli — ini bukan "gratis", hanya UI-nya yang tidak perlu ditulis
ulang.

**Catatan keterbatasan testing iOS**: Developer tidak memiliki akses ke
Mac fisik. Build iOS dijalankan via GitHub Actions macOS runner (gratis,
repo publik), didistribusikan ke tester eksternal via TestFlight (Apple
Developer Program, $99/tahun) untuk testing manual. Golden test/widget
test menjadi lapis pertahanan otomatis terhadap regresi visual, TAPI
tidak menggantikan testing interaktif langsung (gesture, performa,
keyboard behavior) — keputusan sadar menerima risiko ini demi memasukkan
iOS ke scope v1.

### 3.4 LLM Services — TIDAK BERUBAH
Tetap OpenRouter sebagai single gateway, tetap dijalankan dari backend
Python (`core/llm_client.py`), bukan pindah ke Supabase Edge Functions —
alasan: reuse desain yang sudah matang, hindari bahasa ketiga (Deno/TS)
untuk solo dev.

| Task | Model Primary | Fallback |
|---|---|---|
| Text parsing | `z-ai/glm-5.2:free` | `meta-llama/llama-3.3-70b-instruct:free` |
| Vision/OCR | `google/gemma-4-31b-it:free` | `thinkingmachines/inkling:free` |
| Last resort | `openrouter/free` | — |

## 4. Alur Data Utama

### 4.1 Input Teks (Telegram/Flutter App) — TIDAK BERUBAH secara logic
User kirim teks → [Telegram bot Node forward ke backend] atau [Flutter
langsung ke backend REST] → transaction_service.create_transaction(raw_text)
→ nlu_parser.parse() via GLM 5.2 → validate() → pending_transactions →
konfirmasi user → commit ke Supabase Postgres.

### 4.2-4.4 — TIDAK BERUBAH secara logic bisnis, hanya database target
berubah dari self-hosted Postgres ke Supabase Postgres. Gambar nota:
disimpan di **Supabase Storage** (bucket privat), bukan local storage VPS
lagi — `receipt_image_url` sekarang berisi path Supabase Storage.

## 5. Entity Relationship Diagram (ERD)

**Perubahan struktural dari desain awal:**
- Tabel `users` sekarang REFERENSI ke `auth.users` bawaan Supabase, bukan
  tabel custom penuh. Buat tabel `public.profiles` (1:1 dengan `auth.users`)
  untuk data tambahan (display_name, timezone, role, is_active) yang tidak
  ada di skema `auth.users` bawaan Supabase.
- `password_hash` DIHAPUS dari skema Anda — Supabase Auth yang kelola
  password hashing sepenuhnya, Anda tidak pegang/lihat hash-nya sama sekali.
- Detail lengkap kolom ada di `DATABASE.md` revisi.

## 6. Keamanan (REVISI — lihat detail di DATABASE.md & CODING_RULES.md)

| Aspek | Pendekatan (REVISI) |
|---|---|
| Password user | **Dikelola penuh oleh Supabase Auth** — Anda tidak generate/simpan hash sendiri |
| Autentikasi API | **Supabase JWT** — diterbitkan Supabase Auth, backend Python hanya verifikasi (JWKS), tidak generate |
| Row-level isolation | **Supabase Row Level Security (RLS)** — policy per-tabel memastikan user hanya bisa akses row miliknya sendiri, sebagai lapis keamanan TAMBAHAN di atas validasi backend (defense-in-depth, bukan pengganti) |
| Secrets | API key LLM (`OPENROUTER_API_KEY`), Supabase service role key — di `.env` backend, TIDAK PERNAH di client Flutter (service role key bypass RLS, sangat sensitif) |
| Transport | HTTPS otomatis dari Railway/Render/Supabase, tidak perlu Cloudflare Tunnel manual lagi |
| File nota | Supabase Storage bucket privat, akses via signed URL berumur pendek, bukan public URL permanen |

**PENTING**: Flutter app (client) memakai **Supabase anon key** (public,
dibatasi RLS) untuk operasi auth & realtime saja. Semua write transaksi
kompleks (yang butuh validasi LLM/business rule) tetap lewat backend Python
API, BUKAN langsung Flutter → Supabase insert. Ini mencegah client bypass
validasi bisnis backend.

## 7. Struktur Repository (Monorepo, REVISI)

mymoney/
├── backend/                    # FastAPI, Python (TIDAK BERUBAH strukturnya)
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   └── db/                 # koneksi ke Supabase Postgres
│   ├── alembic/                # migration TETAP pakai Alembic, target Supabase
│   ├── tests/
│   └── Dockerfile
├── telegram_bot/                # BARU — Node.js + Telegraf, service terpisah
│   ├── src/
│   │   ├── handlers/
│   │   └── backend_client.ts    # HTTP client ke backend API
│   ├── package.json
│   └── Dockerfile
├── mobile_web/                   # BARU — Flutter, ganti folder android/
│   ├── lib/
│   │   ├── main.dart
│   │   ├── features/             # per-fitur: auth, transactions, reports, accounts
│   │   ├── core/                 # api_client.dart, supabase_client.dart
│   │   └── theme/                 # design tokens (lihat DESIGN.md revisi)
│   ├── pubspec.yaml
│   └── (build target: android/, ios/, web/ — auto-generated Flutter)
├── docs/
│   ├── ARCHITECTURE.md
│   ├── REQUIREMENTS.md
│   ├── DATABASE.md
│   ├── CODING_RULES.md
│   ├── DESIGN.md
│   └── ROADMAP.md
├── docker-compose.yml            # HANYA untuk backend + local Postgres (dev/testing lokal, opsional — Supabase punya local dev CLI sendiri)
├── .env.example
└── README.md

## 8. Deployment (REVISI TOTAL)

- **Backend Python**: Railway atau Render (pilih salah satu — Railway
  sedikit lebih mudah untuk pemula, Render punya free tier lebih stabil
  untuk service kecil).
- **Telegram bot**: service terpisah di platform yang sama (Railway/Render).
- **Database + Auth + Storage**: Supabase Cloud (free tier cukup untuk skala
  puluhan user; upgrade ke Pro tier kalau volume naik — TIDAK PERLU migrasi
  arsitektur, cukup upgrade billing).
- **Flutter Web**: static hosting (Vercel/Netlify), atau Railway static site.
- **Flutter Mobile**: build APK (Android) untuk testing manual/internal;
  publikasi ke Play Store/App Store adalah keputusan terpisah di v2 kalau
  Anda mau publish publik.
- **CI/CD**: GitHub Actions — lint (ruff/black untuk backend, dart analyze
  untuk Flutter, eslint untuk bot) + test otomatis + auto-deploy ke Railway/
  Render saat push ke `main` (native integration Railway/Render dengan
  GitHub, tidak perlu script SSH manual seperti rencana VPS awal).

**Catatan biaya (perlu Anda pertimbangkan, bukan gratis selamanya)**:
Supabase free tier ada limit (500MB database, 1GB storage, 50K monthly
active users — cukup untuk v1 puluhan user). Railway/Render free tier juga
terbatas (sleep setelah idle, limited compute hours). Kalau backend perlu
selalu-on untuk webhook Telegram real-time, cek apakah free tier
Railway/Render cukup atau perlu upgrade tier berbayar kecil (~$5-7/bulan).

## 9. Batasan & Keputusan Sadar (Out of Scope v1) — REVISI

- Tidak ada multi-currency (IDR saja) — TIDAK BERUBAH.
- Tidak ada shared/household data — TIDAK BERUBAH.
- Tidak ada enkripsi at-rest tambahan di luar yang disediakan Supabase
  (Supabase encrypt at rest secara default di infrastruktur mereka —
  ini sebenarnya upgrade otomatis dari desain awal yang eksplisit skip
  enkripsi at-rest).
- ~~Tidak ada aplikasi iOS di v1~~ **DIHAPUS** — Flutter otomatis mencakup
  iOS dari codebase yang sama. Publikasi ke App Store tetap keputusan
  terpisah (lihat §3.3).
- Tidak menggunakan agent framework orchestration pihak ketiga (n8n, dst)
  — TIDAK BERUBAH untuk logic bisnis; Supabase sebagai BaaS untuk
  data/auth adalah pengecualian sadar yang sudah didiskusikan, bukan
  pelanggaran prinsip ini (BaaS ≠ agent orchestration framework).

## 10. Security Architecture (REVISI)

### Threat Model (Update)

| Ancaman | Mitigasi (REVISI) |
|---|---|
| SQL Injection | ORM SQLAlchemy tetap wajib (TIDAK BERUBAH) |
| Prompt Injection | TIDAK BERUBAH — system prompt hardcoded, validasi Pydantic |
| Auth bypass | Supabase JWT verification (JWKS) di setiap endpoint backend, RLS sebagai lapis kedua di level database |
| Row-level data leak | **RLS Policy wajib di SEMUA tabel yang berisi data user** — kalau backend punya bug validasi user_id, RLS tetap mencegah user A baca data user B langsung dari Postgres |
| Service role key exposure | Service role key (bypass RLS) HANYA ada di backend `.env`, TIDAK PERNAH di Flutter/bot — kebocoran ini setara kebocoran root database |
| File Upload Attack | Supabase Storage bucket privat + signed URL, validasi magic bytes tetap di backend sebelum upload |
| Dependency CVE | pip-audit (backend), `dart pub outdated`/`npm audit` (Flutter/bot) — TIDAK BERUBAH prinsipnya, tambah tooling untuk 2 ekosistem baru |