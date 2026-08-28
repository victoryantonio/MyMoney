# MyMoney — Backend

FastAPI backend for MyMoney: personal finance tracker with Telegram bot + Android app.

## Local Setup

### Requirements
- Docker & Docker Compose
- (Optional for local dev outside Docker) Python 3.12 + virtualenv

### 1. Configure environment

```bash
cp ../.env.example ../.env
# Edit ../.env and fill in all required values
```

### 2. Start services

```bash
# From the project root
docker-compose up -d --build
```

### 3. Run migrations

```bash
docker-compose exec backend alembic upgrade head
```

### 4. Verify

```bash
curl http://localhost:8000/health
# → {"status": "ok", "env": "development"}
```

### 5. API docs (development only)

Open http://localhost:8000/docs in your browser.

## Running Tests Locally

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest tests/ -v
```

## Project Structure

```
app/
├── main.py          # FastAPI entrypoint, /health
├── core/
│   └── config.py    # Pydantic settings (all env vars)
├── api/             # Route handlers (thin — no business logic)
├── core/            # Service layer (all business logic lives here)
├── db/
│   ├── base.py      # SQLAlchemy declarative base
│   └── session.py   # Engine + session factory
├── models/          # SQLAlchemy ORM models
└── schemas/         # Pydantic request/response schemas
alembic/             # Database migrations
tests/               # pytest test suite
```

---

## Production / Operasional

### Mode production

`APP_ENV` di `.env` menentukan perilaku:
- `development` — `/docs` & `/redoc` aktif, CORS `*`, verbose errors.
- `production` — **dokumentasi API disembunyikan** (`/docs` → 404), CORS dibatasi
  ke `APP_BASE_URL`, hanya error generik yang dikembalikan.

```bash
APP_ENV=production
```

Verifikasi: `curl https://api.mymoneyofficial.online/health` → `{"status":"ok","env":"production"}`.

> ⚠️ Perubahan `.env` membutuhkan **recreate** container (bukan sekadar restart)
> karena env vars dibaca saat container dibuat:
> ```bash
> docker compose up -d backend
> ```

### Deploy

```bash
cd /root/project
docker compose up -d --build backend tunnel
docker compose exec backend alembic upgrade head   # migrasi DB (jika ada versi baru)
curl -s http://localhost:8000/health
```

Arsitektur: `backend` (FastAPI, port 8000) + `cloudflared` (tunnel publik
`api.mymoneyofficial.online`). Keduanya `restart: unless-stopped`.

### Backup database (WAJIB terjadwal)

DB adalah PostgreSQL ter-manage (Supabase). Backup otomatis harian pukul 03:00
sudah terpasang via cron:

```bash
# One-shot backup (tersimpan di /root/backups/mymoney/, rotasi 14 file terbaru)
./scripts/backup_db.sh

# Uji konektivitas tanpa menyimpan file
./scripts/backup_db.sh --test

# Daftar backup yang ada
./scripts/backup_db.sh --list
```

Cron yang terpasang (`crontab -l`): `0 3 * * * /root/project/scripts/backup_db.sh >> /var/log/mymoney-backup.log 2>&1`

**Restore** (jika DB rusak/terhapus):

```bash
pg_restore -h <host> -p 5432 -U <user> -d <db> --no-owner --no-privileges \
  --clean --if-exists /root/backups/mymoney/<file>.dump
```

### Rate limiting

Semua endpoint mutasi dibatasi per IP (slowapi):

| Endpoint | Limit |
|---|---|
| `POST /api/transactions`, `PUT/DELETE /{id}` | 30/menit |
| `POST /api/categories`, `PUT/DELETE /{id}` | 20/menit |
| `POST /api/accounts`, `PUT /{id}`, `POST /{id}/deactivate` | 20/menit |
| `POST /api/receipts/ocr` | 10/menit |
| `POST /api/telegram/link/confirm` | 10/menit |
| `POST /api/telegram/webhook` | 20/menit |

Melebihi limit → `429 Too Many Requests`.

### Monitoring & troubleshooting

- **Health check**: `GET /health` — pastikan `"status":"ok"`.
- **Log**: `docker compose logs -f backend` (struktured JSON via structlog).
- **Log rotation**: json-file, max 10 MB × 5 file (diatur di `docker-compose.yml`).
- **Tunnel bermasalah**: `docker compose logs -f tunnel`; cek `CLOUDFLARE_TUNNEL_TOKEN`
  di `.env` (Cloudflare Zero Trust → Networks → Tunnels).
- **Rate limit palsu (429)**: semua user di balik IP publik sama (NAT operator)
  berbagi kuota per-IP; jika sering kena, naikkan limit di `app/api/*.py`.

### Env vars penting

| Variabel | Keterangan |
|---|---|
| `APP_ENV` | `development` / `production` |
| `APP_BASE_URL` | URL publik API (mis. `https://api.mymoneyofficial.online`) |
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | Auth & admin Supabase |
| `LLM_PROVIDER` | `auto` / `openrouter` / `deepseek` |
| `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY` | Kunci LLM untuk OCR & NLU |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `BOT_PUBLIC_URL`, `BOT_SERVICE_TOKEN` | Bot Telegram |
| `CLOUDFLARE_TUNNEL_TOKEN` | Token tunnel cloudflared (dibaca docker-compose) |

