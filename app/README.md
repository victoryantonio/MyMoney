# MyMoney — Flutter App

Flutter client for **MyMoney**, a personal finance assistant. It provides the
dashboard, manual transaction entry, receipt OCR review, category & account
management, reports, and account-transfer flows on top of the FastAPI REST
backend.

## Requirements

- Flutter SDK 3.47+ (see `pubspec.yaml` for the Dart SDK constraint)
- Android SDK (for APK builds)
- A running MyMoney backend — see the root `README.md` and `backend/README.md`

## Configuration

The app reads build-time configuration via `--dart-define` (values are public
by design — never put secrets here):

| Define | Description | Example |
|---|---|---|
| `SUPABASE_URL` | Supabase project URL | `https://YOUR_PROJECT.supabase.co` |
| `SUPABASE_ANON_KEY` | Supabase public anon key | `YOUR_ANON_KEY` |
| `APP_BASE_URL` | Backend REST API base URL | `https://api.mymoneyofficial.online` |

## Run

```bash
cd app
flutter pub get
flutter run \
  --dart-define=SUPABASE_URL=https://YOUR_PROJECT.supabase.co \
  --dart-define=SUPABASE_ANON_KEY=YOUR_ANON_KEY \
  --dart-define=APP_BASE_URL=https://api.mymoneyofficial.online
```

For a physical Android device, `APP_BASE_URL` must be reachable from the
device — do not use `localhost`.

## Test & analyze

```bash
flutter analyze
flutter test
```

## Build a release APK

Release builds are signed with the production keystore configured in
`android/key.properties` (gitignored). The keystore lives outside the repo at
`/root/keystore/mymoney/` — **back it up permanently** (Play Store requires
the same key for every update). If `key.properties` is missing, the build
falls back to the debug signing config so local `--release` runs still work.

```bash
cd app
set -a && . ../.env && set +a
flutter build apk --release \
  --dart-define=SUPABASE_URL="$SUPABASE_URL" \
  --dart-define=SUPABASE_ANON_KEY="$SUPABASE_ANON_KEY" \
  --dart-define=APP_BASE_URL="$APP_BASE_URL"
```

Output: `build/app/outputs/flutter-apk/app-release.apk`

## Key packages

- `flutter_riverpod` — state management
- `supabase_flutter` — Supabase Auth sessions
- `dio` — REST API calls
- `fl_chart` — dashboard charts
- `flutter_local_notifications` + `timezone` — spending reminders
- `image_picker` — receipt photo capture

## Project layout

```
lib/
├── main.dart            # App entry, AuthGate
├── core/                # Config, API client, formatting & exchange-rate utilities
└── screens/             # Dashboard, transactions, categories, accounts, profile
test/                    # Widget & formatting tests
```

See the root `README.md` for architecture, the tech stack, and AI/data-safety
notes.
