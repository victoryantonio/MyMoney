# ROADMAP.md — MyMoney

## 1. Prinsip Eksekusi

- **Bertahap, bukan paralel.** Setiap fase harus punya hasil fungsional sebelum lanjut ke fase berikutnya — bukan mengerjakan 4 fitur besar bersamaan.
- **Timeline: 1-2 bulan, fokus penuh.** Target agresif ini hanya realistis kalau scope tidak melebar di tengah jalan (lihat riwayat revisi di §5 sebagai pengingat pola yang harus dihindari).
- Setiap fase diakhiri dengan checkpoint yang bisa dites nyata (bukan "selesai di kepala"), agar kalau timeline meleset, Anda tetap punya sistem yang jalan di titik manapun berhenti.

## 2. Fase Pengerjaan

### Fase 0 — Setup Fondasi (Target: 2-3 hari)
- [ ] Inisialisasi monorepo (struktur sesuai `ARCHITECTURE.md` §7)
- [ ] Setup Docker Compose: FastAPI + PostgreSQL, jalan lokal
- [ ] Setup Alembic, migration awal (tabel `users`, `telegram_links`, `categories`, `transactions`, `transaction_items` sesuai `DATABASE.md`)
- [ ] Seed data kategori default
- [ ] Setup GitHub repo (public), `.gitignore`, `.env.example`
- [ ] Setup pre-commit hook (black, ruff)
- [ ] Setup GitHub Actions dasar (lint + test, belum deploy)

**Checkpoint**: `docker-compose up` jalan lokal, migration sukses, endpoint `/health` merespons.

### Fase 1 — Backend Inti + Autentikasi (Target: 1 minggu)
- [ ] `auth_service`: registrasi, login, JWT (access + refresh token)
- [ ] Password hashing (bcrypt/argon2)
- [ ] `transaction_service`: create/read/update/delete transaksi (manual, tanpa LLM dulu)
- [ ] Endpoint REST dasar untuk transaksi & kategori (dengan pagination cursor-based sejak awal, sesuai `CODING_RULES.md`)
- [ ] Unit test service layer

**Checkpoint**: Bisa registrasi, login, dan CRUD transaksi lewat Postman/curl — tanpa UI apapun.

### Fase 2 — Integrasi Telegram + Parsing Teks (Target: 1-1.5 minggu)
- [ ] Setup Telegram bot, webhook endpoint
- [ ] `/start` — linking `telegram_id` ke `user_id`
- [ ] `nlu_parser`: integrasi GLM 5.2, structured output (JSON schema)
- [ ] Alur konfirmasi sebelum commit (state pending → user konfirmasi → simpan)
- [ ] Command `/batal`, `/edit`

**Checkpoint**: Bisa chat "beli kangkung 5k" ke bot Telegram, dapat balasan konfirmasi, transaksi tersimpan setelah konfirmasi.

### Fase 3 — Report Dasar (Target: 3-5 hari)
- [ ] `report_service`: agregasi per kategori/periode (query database, bukan hitung di Python — sesuai `DATABASE.md` §3.4)
- [ ] Command `/report` di Telegram (ringkasan teks)
- [ ] Endpoint REST report untuk konsumsi Android nanti

**Checkpoint**: `/report bulan-ini` di Telegram menampilkan ringkasan pemasukan/pengeluaran per kategori.

### Fase 4 — Android App (Target: 2-2.5 minggu)
- [ ] Setup project Kotlin + Jetpack Compose, arsitektur MVVM
- [ ] Auth screen (login/register), simpan JWT (refresh otomatis)
- [ ] Input transaksi manual (form)
- [ ] List transaksi (pagination, sesuai API yang sudah ada)
- [ ] Edit/hapus transaksi
- [ ] Manajemen kategori custom (tambah/edit)
- [ ] Dashboard report (chart via Vico/MPAndroidChart)

**Checkpoint**: App Android bisa login, catat transaksi manual, lihat list & report — berjalan di atas backend yang sama dengan Telegram.

### Fase 5 — OCR Foto Nota (Target: 1.5-2 minggu)
- [ ] `receipt_service`: integrasi Gemini 3.5 Flash-Lite (vision)
- [ ] Structured output multi-item (`merchant`, `date`, `total`, `items[]`, `confidence`)
- [ ] Endpoint upload foto (Telegram & Android)
- [ ] UI konfirmasi/edit per-item sebelum commit (Android — ini bagian paling kompleks di UI, sudah ditandai sejak `REQUIREMENTS.md`)
- [ ] Penanganan `confidence: low` — tandai perlu review manual
- [ ] Simpan gambar nota asli (local storage di VPS, path di `receipt_image_url`)

**Checkpoint**: Foto nota belanja dari Telegram atau app menghasilkan transaksi multi-item yang bisa dikoreksi sebelum tersimpan.

### Fase 6 — Deploy Produksi & Hardening (Target: 3-5 hari)
- [ ] Provisioning VPS (Ubuntu 26.04 LTS, 8GB/4vCPU sesuai `ARCHITECTURE.md`)
- [ ] Setup Nginx reverse proxy + Let's Encrypt
- [ ] Konfigurasi resource limit Docker (sesuai `DATABASE.md` §4)
- [ ] GitHub Actions: tambah step deploy otomatis ke VPS
- [ ] Setup monitoring dasar (health check + uptime alert)
- [ ] Review keamanan akhir: pastikan tidak ada credential ter-commit, cek `.env` di server

**Checkpoint**: Sistem berjalan penuh di VPS produksi, bisa diakses dari Telegram & Android dari mana saja.

## 3. Ringkasan Timeline

| Fase | Estimasi | Kumulatif |
|---|---|---|
| Fase 0 — Setup Fondasi | 2-3 hari | ~3 hari |
| Fase 1 — Backend Inti + Auth | 1 minggu | ~1.5 minggu |
| Fase 2 — Telegram + Parsing Teks | 1-1.5 minggu | ~3 minggu |
| Fase 3 — Report Dasar | 3-5 hari | ~3.5 minggu |
| Fase 4 — Android App | 2-2.5 minggu | ~6 minggu |
| Fase 5 — OCR Foto Nota | 1.5-2 minggu | ~7.5-8 minggu |
| Fase 6 — Deploy Produksi | 3-5 hari | ~8-8.5 minggu |

**Realitas timeline**: total estimasi ini sudah mendekati **2 bulan penuh** dengan asumsi fokus konsisten tanpa gangguan besar. Target "1-2 bulan" yang Anda tetapkan berada di ujung atas rentang ini — realistis hanya jika tidak ada penambahan scope baru di tengah jalan.

Estimasi tambahan Fase 1 tidak berubah signifikan (~2-3 hari) — solusi ini justru lebih sederhana dari rencana reassignment sebelumnya (tidak perlu update massal account_id di banyak row transaksi, cukup 2 insert baru + 1 update is_active).

## 4. Fase v2 (Di Luar Scope Dokumen Ini)

Dicatat sebagai referensi masa depan, **bukan bagian dari commitment timeline v1**:
- Aplikasi iOS (native Swift/SwiftUI, mengonsumsi REST API yang sama)
- Shared/household data antar user
- Multi-currency
- Caching layer (Redis) untuk report — hanya jika terbukti perlu dari data pemakaian nyata
- Read replica / optimasi lanjutan — hanya jika skala user riil melebihi puluhan-ratusan

## 5. Catatan Disiplin Scope

Selama proses perencanaan dokumen ini, beberapa ide muncul di tengah jalan dan berhasil disaring keluar dari v1 setelah dipertimbangkan: n8n, Hermes Agent, multi-currency, aplikasi iOS, dan ekspektasi skala user yang sempat naik-turun. Pola ini **wajar terjadi lagi** selama development — ROADMAP ini ada justru untuk jadi acuan objektif: sebelum menambah apapun ke v1 di tengah jalan, cek dulu apakah itu benar-benar blocking untuk checkpoint fase saat ini, atau bisa masuk §4 (v2).