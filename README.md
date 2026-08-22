# MyMoney

Aplikasi pencatatan keuangan pribadi — input via Telegram bot & Android app, parsing LLM (teks + foto nota).

## Stack

| Layer | Tech |
|---|---|
| Backend | FastAPI, Python 3.12, asyncpg, SQLAlchemy 2 (async) |
| Database | PostgreSQL 16 |
| Auth | Argon2 + JWT (access + refresh) |
| LLM Teks | GLM 5.2 |
| LLM Vision | Gemini 3.5 Flash-Lite |
| Bot | python-telegram-bot |
| Android | Kotlin, Jetpack Compose, Material 3, Hilt, Retrofit, Coil |
| Infra | Docker Compose, Cloudflare Tunnel |

## Cara Setup Lokal

```bash
# 1. Copy env
cp .env.example .env
# Edit .env dengan nilai asli (API keys, DB password, JWT secret)

# 2. Jalankan
docker compose up --build

# 3. Run migration
docker compose exec backend alembic upgrade head

# 4. Cek health
curl http://localhost:8000/health
```

## API Docs

Tersedia di `http://localhost:8000/docs` (development mode saja).

## Struktur

```
backend/app/
├── api/           # Routing layer only — no business logic
├── core/          # Service layer — all business logic
├── models/        # SQLAlchemy models
├── schemas/       # Pydantic schemas
└── db/            # DB session + config

android/
└── app/src/main/
    ├── kotlin/com/mymoney/app/
    │   ├── data/       # API, repository, local token store
    │   ├── di/         # Hilt dependency injection
    │   └── ui/         # Jetpack Compose screens & theme
    └── res/            # Android resources
```

## Keamanan

- Tidak ada credential di repo (publik). Semua via `.env`.
- Password: Argon2 hash, tidak pernah disimpan plaintext.
- JWT: access token 30 menit, refresh token 30 hari.
- Audit trail: setiap create/update/delete/login dicatat di `audit_logs`.

