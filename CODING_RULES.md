# CODING_RULES.md — MyMoney

## 1. Filosofi

Level kedisiplinan: **menengah**. Konvensi harus konsisten dan jelas, tapi prioritas utama adalah proyek **jalan dan selesai** dalam target 1-2 bulan — bukan coverage test 100% atau dokumentasi berlebihan. Aturan di bawah ini fokus pada hal-hal yang **mencegah bug mahal** (terutama terkait data finansial, keamanan, dan performa di skala banyak user), bukan formalitas administratif.

## 2. Backend (Python / FastAPI)

### 2.1 Style & Linting
- **Formatter**: `black` (default config, tanpa kustomisasi line-length).
- **Linter**: `ruff` (menggantikan flake8+isort, lebih cepat).
- **Type hints wajib** di semua fungsi service layer (`core/`) dan signature endpoint API — tidak wajib di script kecil/testing helper.
- Jalankan `ruff check . && black --check .` sebelum commit (via pre-commit hook, lihat §5).

### 2.2 Struktur Kode — Aturan Ketat (Tidak Boleh Dilanggar)
Ini bukan preferensi, ini aturan arsitektur yang sudah ditetapkan di `ARCHITECTURE.md`:
- **API layer (`api/`) DILARANG berisi logic bisnis.** Hanya boleh: validasi request dasar, panggil fungsi service layer, format response.
- **Semua akses database HARUS lewat service layer (`core/`)**, tidak ada query SQLAlchemy langsung ditulis di dalam `api/`.
- **Setiap fungsi service yang dipanggil dari Telegram DAN Android harus benar-benar satu fungsi yang sama** — dilarang membuat versi duplikat "khusus Telegram" atau "khusus app".

### 2.3 Wajib — Query Database
Berdasarkan `DATABASE.md` §3, ini bukan opsional:
- **Semua endpoint yang return list wajib pagination** (cursor-based, bukan `OFFSET` untuk tabel besar). PR yang menambah endpoint list tanpa pagination tidak boleh di-merge.
- **Wajib eager loading eksplisit** (`selectinload`/`joinedload`) saat mengambil relasi (misal `Transaction` + `TransactionItems`). Dilarang mengandalkan lazy-load default di response API.
- **Query agregasi (SUM, GROUP BY) dilakukan di database**, bukan ditarik mentah lalu dihitung di Python.

### 2.4 Wajib — Interaksi dengan LLM (GLM 5.2 & Gemini 3.5 Flash-Lite)
- Semua panggilan LLM **wajib** meminta structured output (JSON schema), tidak boleh parsing teks bebas dengan regex manual.
- Output LLM **wajib divalidasi** (tipe data, range nilai, enum yang valid) sebelum masuk service layer lebih jauh — gunakan Pydantic schema untuk validasi ini, jangan `if/else` manual bertebaran.
- Tidak ada hasil parsing LLM yang langsung commit ke database tanpa melalui state "pending confirmation" terlebih dahulu (sesuai `REQUIREMENTS.md` US-05, US-08).
- API key LLM disimpan di `.env`, diakses lewat `pydantic-settings`, **tidak pernah** hardcode di kode.

### 2.5 Testing
- Level menengah: **unit test wajib untuk service layer** (`core/`) — terutama `transaction_service`, `nlu_parser` (validasi, bukan mock LLM call sungguhan), `report_service`.
- Endpoint API cukup **integration test dasar** (happy path + 1-2 error case), tidak perlu cover semua edge case di v1.
- Tidak ada target angka coverage minimum eksplisit, tapi **setiap bug yang pernah terjadi di production wajib ditambahkan test case-nya** agar tidak regresi.
- Framework: `pytest` + `pytest-asyncio` (karena FastAPI async).

### 2.6 Error Handling
- Semua exception dari LLM API call (timeout, rate limit, response tidak valid) **wajib ditangani eksplisit**, tidak boleh biarkan 500 error mentah sampai ke user — beri pesan yang jelas ("parsing gagal, coba lagi atau input manual").
- Log error dengan konteks (user_id, endpoint, timestamp) — gunakan `structlog` atau logging standar dengan format terstruktur, bukan `print()`.

### 2.7 Logging & Audit Trail
- Log aplikasi WAJIB terstruktur (JSON), gunakan `structlog`, bukan `print()` atau logging string bebas.
- Level log: `INFO` untuk request normal, `WARNING` untuk kondisi tidak ideal (LLM confidence low, retry), `ERROR` untuk kegagalan yang butuh perhatian.
- Docker logging driver dikonfigurasi dengan limit (`max-size: 10m, max-file: 5`) agar tidak memenuhi disk VPS — WAJIB diset di docker-compose.yml, bukan default unbounded.
- **Audit trail WAJIB dipanggil eksplisit** dari service layer untuk setiap aksi: create/update/delete transaksi, login berhasil/gagal. Dilarang menganggap log aplikasi biasa sebagai pengganti audit trail — keduanya punya tujuan berbeda dan tidak saling menggantikan.
- Audit trail **tidak pernah dihapus/di-rotate** — berbeda dari log aplikasi biasa yang boleh dibuang setelah periode tertentu.

Docker Compose logging config:
```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "5"
```

### 2.8 Akun & Saldo
- Akun TIDAK PERNAH dihapus permanen jika memiliki riwayat transaksi — hanya `is_active = FALSE`.
- Nonaktifkan akun dengan saldo tersisa WAJIB membuat transaksi penyeimbang (bukan mengubah data historis) — jaga prinsip saldo selalu computed dari transaksi, bukan field yang diedit langsung.
- Akun nonaktif tidak muncul di pilihan input transaksi baru, tapi tetap muncul penuh di riwayat/laporan historis.

## 3. Android (Kotlin / Jetpack Compose)

### 3.1 Style & Linting
- **Linter**: `ktlint` (official Kotlin style).
- Ikuti [Kotlin Coding Conventions](https://kotlinlang.org/docs/coding-conventions.html) resmi JetBrains.

### 3.2 Arsitektur
- **MVVM** — `ViewModel` untuk state & logic UI, `Repository` untuk akses data (Retrofit ke backend).
- **Dilarang** memanggil Retrofit API langsung dari `Composable` — selalu lewat `ViewModel`.
- State UI dikelola dengan `StateFlow`/`Compose State`, hindari mutable global state.

### 3.3 Testing
- Unit test untuk `ViewModel` dan `Repository` logic (mock API response).
- UI test (Compose Test) opsional untuk v1 — tidak wajib, sesuai level "menengah".

## 4. Database & Migration

- **Semua perubahan skema lewat Alembic migration** — dilarang ubah struktur tabel manual langsung di production.
- Setiap migration wajib punya `upgrade()` dan `downgrade()` yang benar-benar reversible, diuji di environment lokal sebelum deploy.
- Nama migration deskriptif (`add_confidence_column_to_transactions`), bukan default auto-generated tanpa diedit.

## 5. Git Workflow

### 5.1 Branching
- `main` — selalu deployable, dilindungi (tidak boleh direct push, wajib lewat PR walau solo dev, agar CI jalan dulu).
- `feature/<nama-fitur>` — kerja per fitur (misal `feature/ocr-receipt-parsing`).
- Merge ke `main` lewat PR setelah CI (lint + test) lulus.

### 5.2 Commit Convention
Menggunakan **Conventional Commits**:
feat: tambah endpoint parsing foto nota
fix: perbaiki validasi nominal transaksi negatif
refactor: pindahkan logic kategori ke service layer
docs: update DATABASE.md dengan index baru
chore: update dependency FastAPI

### 5.3 Pre-commit Hook
Setup `pre-commit` menjalankan otomatis sebelum commit:
```yaml
repos:
  - repo: local
    hooks:
      - id: black
        name: black
        entry: black --check .
        language: system
      - id: ruff
        name: ruff
        entry: ruff check .
        language: system
```

## 6. CI/CD (GitHub Actions)

Pipeline minimum di `.github/workflows/ci.yml`:
1. **Lint** — `ruff check` + `black --check` (backend), `ktlint` (Android).
2. **Test** — `pytest` (backend), unit test Android jika ada.
3. **Build** — pastikan Docker image backend berhasil di-build.
4. **Deploy** (hanya di push ke `main`, setelah lulus tahap 1-3) — SSH ke VPS, pull image terbaru, jalankan `alembic upgrade head`, restart container.

Kegagalan di tahap manapun **menghentikan pipeline** — tidak ada deploy otomatis kalau lint/test gagal.

## 7. Keamanan (Wajib, Bukan Opsional)

- **Tidak ada credential, API key, atau connection string yang di-commit ke repo** (repo bersifat publik). Cek dengan `git-secrets` atau review manual sebelum push pertama kali.
- `.env.example` di repo hanya berisi nama variabel dengan placeholder, tidak pernah nilai asli.
- Password **wajib** di-hash dengan bcrypt/argon2 — dilarang menyimpan atau meng-log password dalam bentuk apapun selain hash.
- JWT secret key disimpan di `.env`, di-generate acak (bukan default/contoh dari tutorial manapun).

## 8. Dokumentasi Kode

- Docstring wajib untuk fungsi di service layer (`core/`) yang punya logic non-trivial — jelaskan **kenapa**, bukan sekadar apa (kode sudah menjelaskan "apa").
- README per folder (`backend/`, `android/`) berisi cara setup lokal minimal (install dependency, jalankan migration, run server).
- Tidak perlu dokumentasi exhaustive di level fungsi kecil/trivial — hindari komentar yang sekadar mengulang nama fungsi.