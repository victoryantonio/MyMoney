# task.md — MyMoney To-Do List

> Phased execution checklist. Update status as you work. The current phase is **Phase 4**.
> When Phase 4 is fully done, move its items under `## Done` and unmute Phase 5.

Legend: `[ ]` pending · `[x]` done · `[~]` in progress

---

## Phase 4 — Android App (current)

### A. Project scaffold + app icon
- [ ] Create `android/` Gradle project (Kotlin DSL + version catalog, AGP +
      Kotlin + Compose BOM, Material 3), package `id.my.mymoney`, NavHost
      (Auth → Main).
- [ ] Manifest: `android:icon="@mipmap/ic_launcher"` + `roundIcon`.
- [ ] **App icon from `./icon.png`** (1254×1254 PNG, repo root): script
      `android/tools/gen_icons.py` generates density PNGs (mdpi 48 … xxxhdpi
      192) + round variants + adaptive `mipmap-anydpi-v26/ic_launcher.xml`
      (background color sampled from icon edge) — all committed under
      `android/app/src/main/res/`.

### B. Networking + auth (US-02, US-03)
- [ ] Retrofit API interface mirroring backend (auth, transactions, accounts,
      categories, reports/summary).
- [ ] OkHttp `AuthInterceptor` (Bearer token) + `TokenAuthenticator` (silent
      refresh on 401).
- [ ] DataStore for JWT pair; `AuthRepository` login/register/refresh/logout.

### C. Screens (Compose, MVVM)
- [ ] Auth screen (login/register).
- [ ] Transactions list — cursor pagination (`?cursor=&limit=`), refresh,
      edit/delete.
- [ ] Transaction form — amount, type, category dropdown (custom), account,
      date, merchant; create + edit + delete confirm.
- [ ] Categories management — list global + custom, add/edit/soft-delete.
- [ ] Dashboard — income/expense/net cards + category chart (Vico) from
      `GET /api/reports/summary?period=...` with period selector.

### D. Tests
- [ ] Unit: `AuthRepository` + ViewModels with fake API (loading/error/success).
- [ ] `./gradlew :app:lintDebug` clean; `:app:testDebugUnitTest` passes.
- [ ] API contract check: DTOs match backend responses (esp.
      `/api/reports/summary` + transaction create payload).

### E. Verification
- [ ] `cd android && ./gradlew :app:assembleDebug` builds clean.
- [ ] Manual E2E (emulator/device + live backend): login → list paging →
      add/edit/delete tx (backend audit rows) → custom category → dashboard
      chart matches report summary per period.
- [ ] Icon renders correctly (adaptive + round + legacy densities).
- [ ] No backend changes needed (or minimal follow-up recorded).

### Phase 4 sign-off
- [ ] Confirm launcher icon is `./icon.png`-derived and looks right.
- [ ] Confirm app works against the same backend as Telegram (ROADMAP Fase 4
      checkpoint).
- [ ] Confirm tests + lint + build green → update `IMPLEMENTATION_PLAN.md`,
      `walkthrough.md`, and this file. (Phase 4 complete, ready for Phase 5.)

## Phase 5 — OCR Foto Nota (not started)
- [ ] `receipt_service` + vision model via `call_llm()`, multi-item schema,
      confidence handling, image storage.

## Phase 6 — Deploy Produksi & Hardening (not started)
- [ ] VPS provisioning, Nginx + Let's Encrypt, resource limits, deploy CI, monitoring.

---

## Done
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
