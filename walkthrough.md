# walkthrough.md — MyMoney Phase 5 Execution Guide

> ✅ **Phase 4 (Android App) is COMPLETE (2026-08-25).** Results: 23 unit tests
> green, `lintDebug` clean, `assembleDebug` clean (`app-debug.apk`), launcher
> icons generated in-repo from `./icon.png`, pushed to `main`.
>
> Phase 4's step-by-step guide below is kept as the record of how the app was
> built. The current phase is **Phase 5 — OCR Foto Nota** (see the new guide at
> the bottom of this file).

Phase 4 = **Android App** — Kotlin + Jetpack Compose, MVVM, JWT auth with
auto-refresh, manual transaction CRUD, custom category management, and a report
dashboard with charts. **The app launcher icon is `./icon.png`** (1254×1254 RGB
PNG at the repo root) — all Android icon resources are generated from it
in-repo (no Android Studio / new design needed).

---

## Step 0 — Decision gate (before writing code)

Read `IMPLEMENTATION_PLAN.md §2/§3`. Resolved decisions:

1. **App icon.** Use `./icon.png` (repo root, 1254×1254 RGB PNG) as the launcher
   icon. Generate resources in-repo with a committed script:
   - `android/app/src/main/res/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher.png`
     (48 / 72 / 96 / 144 / 192 px) + `ic_launcher_round.png` twins
   - `android/app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` +
     `ic_launcher_round.xml` (adaptive: foreground = icon scaled ~66%, background
     = solid color sampled from the icon edge)
2. **Architecture.** MVVM: Repository (Retrofit + OkHttp) → ViewModel (UiState)
   → Compose screens. JWT pair stored in DataStore, silent refresh via OkHttp
   `Authenticator`.
3. **Chart library.** Vico (Compose-native) — ROADMAP lists "Vico/MPAndroidChart";
   pick Vico unless review objects.
4. **Min SDK.** API 26 (Android 8.0) — adaptive icons need 26; legacy PNGs
   cover anything below.

---

## Step 1 — Project scaffold (`android/`) + app icon

### 1.1 Scaffold
- Create `android/` Gradle project: `settings.gradle.kts`, root
  `build.gradle.kts` (AGP + Kotlin + Compose BOM via version catalog
  `gradle/libs.versions.toml`), `app/` module with `build.gradle.kts`.
- Package `id.my.mymoney`; `MainActivity` (Compose), Material 3 theme,
  NavHost (Auth → Main).
- Manifest: internet permission, `android:icon="@mipmap/ic_launcher"`,
  `roundIcon="@mipmap/ic_launcher_round"`.
- `cd android && ./gradlew :app:assembleDebug` must build.

### 1.2 App icon from `./icon.png`
- Commit `android/tools/gen_icons.py` (Python/Pillow or ImageMagick) that reads
  `./icon.png` (1254×1254, repo root) and writes:
  - `app/src/main/res/mipmap-{mdpi,hdpi,xhdpi,xxhdpi,xxxhdpi}/ic_launcher.png`
    (48 / 72 / 96 / 144 / 192 px) + `ic_launcher_round.png` twins
  - `app/src/main/res/mipmap-anydpi-v26/ic_launcher.xml` +
    `ic_launcher_round.xml` (adaptive icon)
  - `values/ic_launcher_background.xml` color sampled from the icon edge
- Adaptive XML:
  ```xml
  <adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">
      <background android:drawable="@color/ic_launcher_background"/>
      <foreground android:drawable="@mipmap/ic_launcher_foreground"/>
  </adaptive-icon>
  ```
- Verify in emulator launcher: no stretch, no alpha bleed, round OK.

---

## Step 2 — Networking + auth

- `data/remote/` — Retrofit service mirroring the backend: `POST
  /api/auth/login|register|refresh`, transactions CRUD, accounts, categories,
  `GET /api/reports/summary`.
- OkHttp `AuthInterceptor` adds `Authorization: Bearer <access>`;
  `TokenAuthenticator` silently refreshes via `/api/auth/refresh` on 401.
- `data/local/` — DataStore for the access/refresh token pair (async).
- `AuthRepository` — login/register/refresh/logout; expose auth UiState.

---

## Step 3 — Screens (Compose, MVVM)

- **Auth screen** — email/password form; login + register; on success → Main.
- **Transactions list** — paging from the cursor API (`?cursor=&limit=`),
  swipe-to-refresh, next page on scroll end; income/expense rows with category
  chip; edit/delete actions.
- **Transaction form** — amount, type toggle, category dropdown (custom),
  account, date, merchant; create + edit + delete confirm dialog.
- **Categories management** — list global + user categories, add/edit/soft-delete.
- **Dashboard** — total income / expense / net cards + per-category chart
  (Vico) from `GET /api/reports/summary?period=...`; period selector
  today/week/month/last-month mirroring backend keywords.

---

## Step 4 — Tests

- Unit: `AuthRepository` + ViewModels with fake repositories / MockWebServer
  (loading / error / success states).
- API-contract check: app DTOs match backend responses — especially
  `/api/reports/summary` shape and the transaction create payload (from the
  Phase-3 E2E notes).
- Instrumented smoke test (emulator, optional): login → list → report.
- No backend changes expected; if a gap appears, record it and add a minimal
  backend follow-up before Phase 5.

---

## Step 5 — Verification (checkpoint)

```bash
cd android
./gradlew :app:assembleDebug      # builds clean
./gradlew :app:lintDebug          # lint clean
./gradlew :app:testDebugUnitTest  # unit tests pass
```

### Manual E2E (emulator/device + live docker backend)
- Login/register against the live backend → transactions list loads (paging).
- Add / edit / delete a transaction → list reflects change (backend audit rows).
- Create a custom category → appears in the form dropdown.
- Dashboard chart matches `/api/reports/summary` numbers for each period.
- Launcher icon: adaptive + round render correctly (from `./icon.png`).

### Negative cases
- Wrong credentials → inline error, no crash.
- Expired token → silent refresh; refresh fails → back to login.

---

## Phase 5 — OCR Foto Nota (next)

> **Status: not started.** Placeholder — fill in the concrete steps while
> working Phase 5 (see ROADMAP Fase 5).

> **Telegram UX revision (2026-08-25, already shipped):** Telegram now saves
> NL text + `/edit` directly (no `/confirm`), adds `/logout`, and the linking
> pages use the DESIGN.md palette + `./icon.png` logo + auto-close. See
> `task.md` → Done and commit `7aeed35`.

**Goal:** user uploads a receipt photo from the Android app / Telegram; the
vision LLM (`call_llm()` with `VISION_MODELS`) extracts items, amounts, and a
category suggestion with confidence; the user confirms/edits before the
transaction is created; receipt images are stored and referenced.

Planned touch points:
1. Backend: `receipt_service` + `POST /api/receipts` (multipart upload),
   multi-item schema, confidence fields, image storage + serving.
2. Android: receipt capture/upload UI + confirm screen wired to the new API.
3. Telegram: forward a photo → same extraction + confirm flow.
4. Tests for the extraction/validation logic; E2E with a sample receipt.

---

## Phase 4 — Android App (COMPLETE ✅, 2026-08-25)

> This is the concrete, step-by-step "how to actually do Phase 4" companion to
> `task.md`. Every step names the real file to touch and what to change. Run
> verification tasks at each checkpoint. **Work was grounded in the repo state
> at the end of Phase 3 (all 88 tests green, pushed `cce9c12`).**
