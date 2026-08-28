# Changelog — MyMoney

All notable changes to the MyMoney app are documented in this file.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and versioning follows [Semantic Versioning](https://semver.org/).

## [1.1.0+2] — 2026-08-28

### Added
- **Multi-currency per transaction** — every transaction can use a currency
  other than IDR (USD, EUR, SGD, etc.); the amount is stored in the original
  currency plus its exchange rate to IDR, and totals are always computed in IDR.
- **Account transfer system** — move balances between accounts
  (cash/e-wallet/bank) without affecting income/expense reports.
- **Unique category names per user (case-insensitive)** — you can no longer
  create two categories with the same name (e.g. "Food" vs "food") in the same
  type.
- **Production hardening**:
  - Production mode enabled in the backend (`APP_ENV=production`): API docs
    (`/docs`) are hidden and CORS is restricted to the official domain.
  - Rate limiting on all mutation endpoints (transactions 30/min, categories &
    accounts 20/min, OCR 10/min).
  - Automated daily database backup script (pg_dump, 14-day rotation).
  - Release APK signed with the production keystore (no longer debug).

### Fixed
- **SegmentedButton truncation** (Pengeluaran/Pemasukan/Transfer clipped) in the
  transaction form and category management — segment icons removed &
  `showSelectedIcon` disabled so labels are no longer cut off.
- **Currency dropdown** — now shows only the currency code (e.g. `USD`) so the
  amount field is wider and easier to fill in.
- **Category conflict message** — creating an already-existing category now
  shows "Kategori sudah ada" (409) instead of "Server Error 409"; the backend's
  `detail` message is shown as-is in the app.
- The "Other" category that already exists (default) no longer needs to be
  recreated — just pick it from the list.

### Changed
- Version number: `1.0.0+1` → `1.1.0+2`.

## [1.0.0+1] — initial release

- Aplikasi pencatat keuangan pribadi: dashboard, transaksi manual, scan nota
  (OCR), kategori, akun, laporan, dan bot Telegram.
