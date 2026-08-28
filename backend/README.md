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

## Production / Operations

### Production mode

`APP_ENV` in `.env` controls behavior:
- `development` — `/docs` & `/redoc` enabled, CORS `*`, verbose errors.
- `production` — **API documentation is hidden** (`/docs` → 404), CORS is
  restricted to `APP_BASE_URL`, and only generic errors are returned.

```bash
APP_ENV=production
```

Verify: `curl https://api.mymoneyofficial.online/health` → `{"status":"ok","env":"production"}`.

> ⚠️ Changing `.env` requires a **container recreate** (not just a restart),
> because env vars are read when the container is created:
> ```bash
> docker compose up -d backend
> ```

### Deploy

```bash
cd /root/project
docker compose up -d --build backend tunnel
docker compose exec backend alembic upgrade head   # DB migrations (if a new version exists)
curl -s http://localhost:8000/health
```

Architecture: `backend` (FastAPI, port 8000) + `cloudflared` (public tunnel at
`api.mymoneyofficial.online`). Both run with `restart: unless-stopped`.

### Database backups (MANDATORY — scheduled)

The DB is managed PostgreSQL (Supabase). A daily automated backup at 03:00 is
installed via cron:

```bash
# One-shot backup (stored in /root/backups/mymoney/, keeps the 14 newest files)
./scripts/backup_db.sh

# Connectivity check without saving a file
./scripts/backup_db.sh --test

# List existing backups
./scripts/backup_db.sh --list
```

Installed cron (`crontab -l`): `0 3 * * * /root/project/scripts/backup_db.sh >> /var/log/mymoney-backup.log 2>&1`

**Restore** (if the DB is corrupted/deleted):

```bash
pg_restore -h <host> -p 5432 -U <user> -d <db> --no-owner --no-privileges \
  --clean --if-exists /root/backups/mymoney/<file>.dump
```

### Rate limiting

All mutation endpoints are limited per IP (slowapi):

| Endpoint | Limit |
|---|---|
| `POST /api/transactions`, `PUT/DELETE /{id}` | 30/minute |
| `POST /api/categories`, `PUT/DELETE /{id}` | 20/minute |
| `POST /api/accounts`, `PUT /{id}`, `POST /{id}/deactivate` | 20/minute |
| `POST /api/receipts/ocr` | 10/minute |
| `POST /api/telegram/link/confirm` | 10/minute |
| `POST /api/telegram/webhook` | 20/minute |

Exceeding the limit → `429 Too Many Requests`.

### Monitoring & troubleshooting

- **Health check**: `GET /health` — make sure `"status":"ok"`.
- **Logs**: `docker compose logs -f backend` (structured JSON via structlog).
- **Log rotation**: json-file, max 10 MB × 5 files (configured in `docker-compose.yml`).
- **Tunnel issues**: `docker compose logs -f tunnel`; check `CLOUDFLARE_TUNNEL_TOKEN`
  in `.env` (Cloudflare Zero Trust → Networks → Tunnels).
- **Unexpected 429s**: all users behind the same public IP (carrier NAT) share
  the per-IP quota; if 429s happen often, raise the limits in `app/api/*.py`.

### Key environment variables

| Variable | Description |
|---|---|
| `APP_ENV` | `development` / `production` |
| `APP_BASE_URL` | Public API URL (e.g. `https://api.mymoneyofficial.online`) |
| `DATABASE_URL` | Supabase PostgreSQL connection string |
| `SUPABASE_URL` / `SUPABASE_ANON_KEY` / `SUPABASE_SERVICE_ROLE_KEY` | Supabase auth & admin |
| `LLM_PROVIDER` | `auto` / `openrouter` / `deepseek` |
| `OPENROUTER_API_KEY`, `DEEPSEEK_API_KEY` | LLM keys for OCR & NLU |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_WEBHOOK_SECRET`, `BOT_PUBLIC_URL`, `BOT_SERVICE_TOKEN` | Telegram bot |
| `CLOUDFLARE_TUNNEL_TOKEN` | cloudflared tunnel token (read by docker-compose) |

