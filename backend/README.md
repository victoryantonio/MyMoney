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
