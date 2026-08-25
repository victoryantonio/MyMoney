# task.md — MyMoney To-Do List

> Phased execution checklist. Update status as you work. The current phase is **Phase 5**.
> When Phase 5 is fully done, move its items under `## Done` and unmute Phase 6.

Legend: `[ ]` pending · `[x]` done · `[~]` in progress

---

## Phase 5 — OCR Foto Nota (current)
- [ ] `receipt_service` + vision model via `call_llm()`, multi-item schema,
      confidence handling, image storage.

## Phase 6 — Deploy Produksi & Hardening (not started)
- [ ] VPS provisioning, Nginx + Let's Encrypt, resource limits, deploy CI, monitoring.

---

## Done

- [x] **Phase 4 — Android App** ✅

### A. Project scaffold + app icon
- [x] Create `android/` Gradle project (Kotlin DSL + version catalog, AGP +
      Kotlin + Compose BOM, Material 3), package `id.my.mymoney`, NavHost
      (Auth → Main).
- [x] Manifest: `android:icon="@mipmap/ic_launcher"` + `roundIcon`.
- [x] **App icon from `./icon.png`** (1254×1254 PNG, repo root): script
      `android/tools/gen_icons.py` generates density PNGs (mdpi 48 … xxxhdpi
      192) + round variants + adaptive `mipmap-anydpi-v26/ic_launcher.xml`
      (background color sampled from icon edge) — all committed under
      `android/app/src/main/res/`.

### B. Networking + auth (US-02, US-03)
- [x] Retrofit API interface mirroring backend (auth, transactions, accounts,
      categories, reports/summary).
- [x] OkHttp `AuthInterceptor` (Bearer token) + `TokenAuthenticator` (silent
      refresh on 401).
- [x] DataStore for JWT pair; `AuthRepository` login/register/refresh/logout.

### C. Screens (Compose, MVVM)
- [x] Auth screen (login/register).
- [x] Transactions list — cursor pagination (`?cursor=…`), refresh,
      edit/delete.
- [x] Transaction form — amount, type, category dropdown (custom), account,
      date, merchant; create + edit + delete confirm.
- [x] Categories management — list global + custom, add/edit/soft-delete.
- [x] Dashboard — income/expense/net cards + category breakdown chart
      (custom Compose bars) from `GET /api/reports/summary?period=…` with
      period selector. *(Vico dropped — custom bar chart implemented instead.)*

### D. Tests
- [x] Unit: `AuthRepository` + ViewModels with fake API (loading/error/success)
      — 23 tests green (`AuthRepositoryTest` 8, `AuthViewModelTest` 5,
      `TransactionsViewModelTest` 5, `DashboardViewModelTest` 4,
      `ExampleUnitTest` 1).
- [x] `./gradlew :app:lintDebug` clean (0 errors, 0 warnings);
      `:app:testDebugUnitTest` passes.
- [x] API contract check: DTOs match backend responses (esp.
      `/api/reports/summary` + transaction create payload) — Decimal fields
      handled as JSON strings via `FlexibleStringSerializer`.

### E. Verification
- [x] `cd android && ./gradlew :app:assembleDebug` builds clean
      (`app-debug.apk`, 21 MB).
- [~] Manual E2E (emulator/device + live backend): login → list paging →
      add/edit/delete tx (backend audit rows) → custom category → dashboard
      chart matches report summary per period. *(Pending device run —
      headless CI; contract verified via unit tests + `assembleDebug`.)*
- [x] Icon renders correctly (adaptive + round + legacy densities — verified
      in APK).
- [x] No backend changes needed.

### Phase 4 sign-off
- [x] Launcher icon is `./icon.png`-derived (background `#FBFBFB` sampled
      from icon edge, foreground in 66dp safe zone).
- [x] App targets the same backend as Telegram
      (`https://api.mymoneyofficial.online` — Cloudflare tunnel, permanent).
- [x] Tests + lint + build green → `IMPLEMENTATION_PLAN.md`, `walkthrough.md`,
      and this file updated. (Phase 4 complete, ready for Phase 5.)

- [x] **Telegram UX revision (2026-08-25)** — user decision, backend-only:
      - NL text + `/edit` now **save directly** (no `/confirm` gate); replies
        `Saved! 📉/📈` / `Edited!` and hint `/undo`. `/confirm` & `/cancel`
        kept as no-op fallbacks for leftover pending rows.
      - New `/logout` command unlinks the Telegram account.
      - Linking pages restyled per DESIGN.md (dusty slate blue palette,
        Manrope, 12px/8px radii, SVG icons) + **logo from `./icon.png`** via
        `app/static/icon.png` (`/static` mount) + browser auto-close on success.
      - Tests: telegram suite 27 green (incl. 2 new `/logout` tests); 45 unit
        tests total. Deployed: commit `7aeed35`, `docker compose up -d --build
        backend`.

- [x] **Phase 3 — Report Dasar** ✅ (report_service SQL aggregation, REST
      `GET /api/reports/summary`, Telegram `/report`, 22 new tests — 88 total,
      E2E verified, pushed `cce9c12`).
- [x] **Phase 2 — Telegram Integration + Text Parsing** ✅
      (LLM gateway via DeepSeek `call_llm()`, locked categories → "Other",
      audit trail, service-layer API, slowapi rate limiting,
      pending-confirmation flow US-05/US-08 — 66 tests passed, E2E verified live).
- [x] **Phase 0 — Setup Fondasi** (docker-compose, Dockerfile, Alembic `0001`,
      seed categories, `.env.example`, pre-commit, CI lint scaffold).
- [x] **Phase 1 — Backend Inti + Autentikasi** (auth/JWT/Argon2, transactions CRUD +
      cursor pagination, accounts computed balance, categories).
  - ⚠️ Note: REST endpoints still carry business logic/direct ORM; partly addressed
      by Phase-2 item D.
