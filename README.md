   # MyMoney

   MyMoney is an open-source, Telegram-first personal finance assistant. It turns
   natural-language messages and receipt photos into editable, itemized financial
   transactions, then presents the same data in a Flutter dashboard.

   The interesting part is not simply adding an LLM to a finance app. MyMoney is
   a reference implementation for a safer workflow around AI-extracted financial
   data:

   ```text
   Telegram or Flutter input
               -> structured LLM/OCR output
               -> Pydantic validation
               -> category/account resolution
               -> editable transaction with line items
               -> audited backend persistence
   ```

   ## Why Try It?

   - **Telegram-first capture**: record an expense, send a receipt, request a
      report, edit the latest transaction, or undo it without opening the app.
   - **Multimodal and itemized**: text and receipt photos can produce merchant,
      date, category, account, total, and `qty x unit price` line items.
   - **Human-correctable AI**: parsed data is represented as structured fields,
      not an opaque sentence, so users can correct it before saving in the app.
   - **Account-aware bookkeeping**: balances are computed from transactions;
      deactivating an account with a balance creates auditable transfer entries
      instead of destroying history.
   - **One business-logic path**: Flutter and Telegram use the same FastAPI
      service layer. The Node bot is only a webhook proxy.
   - **Useful AI engineering surface**: provider-driven LLM gateway, Pydantic
      schemas, locked categories, audit logging, pagination, SQL aggregation, and
      tests around parsing and transaction flows.

   This is currently most useful to AI engineers and developers who want a
   concrete example of multimodal extraction in a domain where validation,
   traceability, and correction matter more than a flashy demo.

   ## Current Status

   The repository is in the v2 migration branch, `migration`.

   ### Available now

   - FastAPI backend with Supabase JWT authentication
   - Flutter app for Android/iOS/Web targets
   - Dashboard with Today / This Week / This Month / Custom periods
   - Income, Expense, and Net summary cards with transaction drill-down
   - Account multi-select filtering and lazy transaction loading
   - Cash Flow and category charts with tap details
   - Manual transaction form with optional multiple line items
   - Telegram text commands, receipt OCR endpoint, reports, edit, undo, and
      account linking
   - Node.js + Telegraf webhook proxy
   - SQL aggregation, keyset pagination, eager-loaded transaction items, and
      audit trail

   ### Still open

   - Direct Android device checkpoint on Samsung S23+
   - iOS CI/TestFlight and external tester checkpoint
   - Widget and golden tests for the five critical screens
   - Production deployment of backend, bot, and Flutter Web
   - Supabase Storage integration for retaining original receipt images
   - A public, anonymized evaluation dataset and parser benchmark

   The detailed phase status is tracked in [task.md](task.md),
   [ROADMAP.md](ROADMAP.md), and [walkthrough.md](walkthrough.md).

   ## Architecture

   ```mermaid
   flowchart LR
         T[Telegram] --> B[Node bot proxy]
         F[Flutter Android/iOS/Web] --> API[FastAPI REST API]
         B --> API
         API --> S[Service layer]
         S --> DB[(Supabase Postgres/Auth/Storage)]
         S --> L[LLM gateway]
   ```

   - `backend/`: FastAPI API, SQLAlchemy models, service layer, migrations, and
      tests
   - `bot/`: Node.js/Telegraf proxy that forwards Telegram webhooks
   - `app/`: Flutter client and Android build target
   - `receipts/`: local development receipt workspace
   - `_archive/`: inactive v1 Kotlin implementation

   Backend remains the source of truth for transaction business rules. The
   Flutter client uses Supabase Auth for sessions and calls the backend REST API
   for transaction/report operations. It does not write complex business data
   directly to Supabase.

   ## Quick Start

   ### Prerequisites

   - Docker and Docker Compose
   - Flutter SDK 3.13 or newer
   - Python 3.12+ for backend development
   - A Supabase project for authenticated API flows
   - An LLM provider key for text/OCR parsing

   ### Configure environment

   ```bash
   cp .env.example .env
   ```

   Fill in Supabase, database, LLM, Telegram, and service-token values in `.env`.
   Never commit `.env`, Supabase service-role keys, or LLM keys.

   ### Start the backend

   ```bash
   docker compose up -d --build
   docker compose exec backend alembic upgrade head
   curl http://localhost:8000/health
   ```

   Development API documentation is available at
   `http://localhost:8000/docs`.

   ### Run backend tests

   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   pytest -q
   ```

   Some integration tests require reachable Supabase credentials. Unit tests for
   the parser, Telegram flow, pending transactions, LLM client, and OCR parser
   can run without a live Supabase API.

   ### Run Flutter

   ```bash
   cd app
   flutter pub get
   flutter analyze
   flutter test
   ```

   The app reads build-time configuration using `--dart-define`:

   ```bash
   flutter run \
      --dart-define=SUPABASE_URL=https://YOUR_PROJECT.supabase.co \
      --dart-define=SUPABASE_ANON_KEY=YOUR_ANON_KEY \
      --dart-define=APP_BASE_URL=http://10.0.2.2:8000
   ```

   For an Android physical device, `APP_BASE_URL` must be reachable from that
   device. Do not use `localhost` unless the backend runs on the device itself.

   ### Build an Android release

   ```bash
   cd app
   flutter build apk --release --split-per-abi \
      --dart-define=SUPABASE_URL=https://YOUR_PROJECT.supabase.co \
      --dart-define=SUPABASE_ANON_KEY=YOUR_ANON_KEY \
      --dart-define=APP_BASE_URL=https://YOUR_BACKEND_HOST
   ```

   Use the `arm64-v8a` APK for most modern Android phones. A debug APK is much
   larger because it contains Dart JIT and validation artifacts; compare release
   builds when evaluating package size or performance.

   ## AI and Data Safety

   - LLM output is validated with Pydantic before transaction service logic.
   - Categories from LLM paths are resolved against locked categories; unknown
      categories fall back to `Other` rather than being created silently.
   - Transaction totals for line items are calculated from quantity and unit
      price, not trusted blindly from generated text.
   - Financial writes go through the backend service layer and are audited.
   - Receipt OCR has a 10 MB upload limit and returns structured data for review.
   - Do not use real financial data while evaluating an untrusted deployment.
   - Review your LLM provider's retention and training policy before sending
      receipt images or transaction text.

   ## Design and Engineering Notes

   The project uses a dusty slate-blue design system, sage income color, clay
   expense color, keyset pagination, SQL report aggregation, and eager loading of
   transaction items. See:

   - [ARCHITECTURE.md](ARCHITECTURE.md)
   - [DATABASE.md](DATABASE.md)
   - [CODING_RULES.md](CODING_RULES.md)
   - [DESIGN.md](DESIGN.md)
   - [REQUIREMENTS.md](REQUIREMENTS.md)

   ## Contributing

   Before opening a pull request:

   ```bash
   cd backend && ruff check . && black --check .
   cd ../app && flutter analyze && flutter test
   ```

   Please keep business logic in `backend/app/core/`, add regression tests for
   financial or parsing behavior, and do not include credentials or real user
   data in commits. A project license and contributor policy are still planned
   for the public release preparation.

   ## License

   The repository does not yet declare a license. Until one is added, treat this
   as source-available code and do not assume permission to redistribute it.