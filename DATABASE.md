# DATABASE.md — MyMoney

## 1. Ringkasan (REVISI)

**Supabase (Postgres terkelola)** sebagai satu-satunya sumber data,
menggantikan self-hosted Postgres di VPS. Skema dasar TIDAK BERUBAH secara
struktural, TAPI ada penyesuaian penting terkait integrasi Supabase Auth
dan Row Level Security (RLS).

## 2.1 `users` → DIGANTI: `public.profiles` (REVISI STRUKTURAL)

Supabase menyediakan `auth.users` bawaan (dikelola penuh oleh Supabase Auth
— email, password hash, OAuth provider info — TIDAK ANDA KELOLA LANGSUNG).
Anda buat tabel `public.profiles` untuk data tambahan aplikasi, relasi 1:1
via `id` yang sama dengan `auth.users.id`.

| Kolom | Tipe | Constraint | Keterangan |
|---|---|---|---|
| id | UUID | PK, FK → `auth.users(id)` ON DELETE CASCADE | SAMA PERSIS dengan id di auth.users, bukan UUID baru |
| display_name | VARCHAR(100) | NOT NULL | |
| timezone | VARCHAR(50) | NOT NULL, default `'Asia/Jakarta'` | |
| is_active | BOOLEAN | NOT NULL, default TRUE | |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` | |
| updated_at | TIMESTAMPTZ | NOT NULL, default `now()` | |

**Trigger wajib**: buat trigger Postgres `on_auth_user_created` yang
otomatis insert row `profiles` baru setiap kali ada row baru di
`auth.users` (via Supabase Database Trigger/Function) — supaya setiap
user yang register otomatis punya profile, tanpa backend perlu insert
manual di dua tempat.

```sql
-- Contoh trigger (dijalankan via Supabase SQL Editor atau migration)
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
  INSERT INTO public.profiles (id, display_name)
  VALUES (NEW.id, COALESCE(NEW.raw_user_meta_data->>'display_name', 'User'));
  RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
```

**Tidak ada role admin (keputusan 2026-08-26)**: semua user self-register via
Supabase Auth — tidak ada konsep admin/user di aplikasi. Kolom `role` sudah
dihapus (migration `0007`). Lupa password ditangani Supabase Auth — lihat §8.

## 2.2 `telegram_links` — TIDAK BERUBAH strukturnya
FK `user_id` sekarang merujuk ke `profiles.id` (yang sama dengan `auth.users.id`).

## 2.3 - 2.9 (categories, transactions, transaction_items, audit_logs,
accounts, pending_transactions) — TIDAK BERUBAH secara struktur kolom.
Semua FK `user_id` sekarang merujuk `profiles(id)` bukan tabel `users`
custom lama.

### 2.3 `categories`

| Kolom | Tipe | Constraint | Keterangan |
|---|---|---|---|
| id | UUID | PK, default `gen_random_uuid()` | |
| user_id | UUID | FK → users(id), NULLABLE | NULL = kategori default/global, milik semua user |
| name | VARCHAR(50) | NOT NULL | |
| type | VARCHAR(10) | NOT NULL, CHECK (`type IN ('income','expense')`) | |
| is_default | BOOLEAN | NOT NULL, default FALSE | |
| is_active | BOOLEAN | NOT NULL, default TRUE | Mekanisme soft-delete agar history transaksi tidak bentrok FK |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` | |

**Index:**
- `INDEX idx_categories_user_id ON categories(user_id)`
- `UNIQUE INDEX idx_categories_user_name_type ON categories(COALESCE(user_id, '00000000-0000-0000-0000-000000000000'), name, type)` — cegah duplikat nama kategori per user (dan per kategori default global).

### 2.4 `transactions`

| Kolom | Tipe | Constraint | Keterangan |
|---|---|---|---|
| id | UUID | PK, default `gen_random_uuid()` | |
| user_id | UUID | FK → users(id), NOT NULL | |
| type | VARCHAR(10) | NOT NULL, CHECK (`type IN ('income','expense')`) | |
| total_amount | NUMERIC(14,2) | NOT NULL, CHECK (`total_amount > 0`) | NUMERIC bukan FLOAT — wajib untuk nilai uang, hindari floating point error |
| category_id | UUID | FK → categories(id), NOT NULL | |
| merchant | VARCHAR(150) | NULLABLE | |
| source | VARCHAR(10) | NOT NULL, CHECK (`source IN ('telegram','app')`) | |
| receipt_image_url | TEXT | NULLABLE | Path/URL gambar nota |
| note | TEXT | NULLABLE | |
| confidence | VARCHAR(10) | NULLABLE, CHECK (`confidence IN ('high','medium','low')`) | Hanya diisi jika berasal dari parsing LLM |
| transaction_date | TIMESTAMPTZ | NOT NULL | Tanggal transaksi aktual (bisa beda dari created_at) |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` | |
| updated_at | TIMESTAMPTZ | NOT NULL, default `now()` | |
| account_id | UUID | FK → accounts(id), NOT NULL, ON DELETE RESTRICT | |

**Index (paling kritis di seluruh skema — ini tabel dengan volume terbesar dan query tersering):**
- `INDEX idx_transactions_user_date ON transactions(user_id, transaction_date DESC)` — composite index, dipakai untuk hampir semua query list & report ("transaksi user X pada periode Y")
- `INDEX idx_transactions_user_category ON transactions(user_id, category_id)` — untuk agregasi report per kategori
- `INDEX idx_transactions_category_id ON transactions(category_id)` — mendukung FK lookup
- `INDEX idx_transactions_account_id ON transactions(account_id)` — mendukung FK lookup

Query hitung saldo (computed, bukan disimpan sebagai field terpisah):

```sql
SELECT
    a.id, a.account_name,
    a.initial_balance + COALESCE(SUM(
        CASE WHEN t.type = 'income' THEN t.total_amount ELSE -t.total_amount END
    ), 0) AS current_balance
FROM accounts a
LEFT JOIN transactions t ON t.account_id = a.id
WHERE a.user_id = :uid AND a.is_active = TRUE
GROUP BY a.id, a.account_name, a.initial_balance;
```
Saldo tidak disimpan sebagai kolom statis — dihitung langsung dari initial_balance + akumulasi transaksi. Ini keputusan sadar: mencegah saldo "menyimpang" dari data transaksi riil (satu sumber kebenaran), sesuai prinsip integritas data yang sudah kita pegang sejak desain transactions. Di skala puluhan-ratusan user, biaya query agregasi ini masih sangat murah — tidak butuh caching.

1. accounts.is_active (sudah ada) dipakai sebagai mekanisme nonaktifkan — tidak ada hard delete untuk akun yang punya transaksi. ON DELETE RESTRICT pada transactions.account_id tetap dipertahankan sebagai pengaman tambahan di level database.
2. Tambah kategori sistem baru (seed data): Transfer/Penyesuaian Akun (type bisa income maupun expense, is_default = TRUE).
3. Akun dengan is_active = FALSE tetap muncul di riwayat/laporan historis, tapi tidak muncul lagi sebagai pilihan saat input transaksi baru.

### 2.5 `transaction_items`

| Kolom | Tipe | Constraint | Keterangan |
|---|---|---|---|
| id | UUID | PK, default `gen_random_uuid()` | |
| transaction_id | UUID | FK → transactions(id), NOT NULL, ON DELETE CASCADE | Hapus transaksi = hapus semua item-nya |
| name | VARCHAR(150) | NOT NULL | |
| qty | NUMERIC(10,2) | NOT NULL, CHECK (`qty > 0`) | NUMERIC agar mendukung qty desimal (misal 0.5 kg) |
| price | NUMERIC(14,2) | NOT NULL, CHECK (`price >= 0`) | |

**Index:**
- `INDEX idx_transaction_items_transaction_id ON transaction_items(transaction_id)` — wajib untuk eager loading saat ambil detail transaksi + item-nya sekaligus.


### 2.6 `audit_logs`
audit_logs (
    id UUID PK,
    user_id UUID FK -> users(id), NOT NULL,
    action VARCHAR(20) NOT NULL,        -- 'create'|'update'|'delete'|'login'
    entity_type VARCHAR(30) NOT NULL,   -- 'transaction'|'user'|'category'
    entity_id UUID NULLABLE,            -- id record yang terpengaruh
    old_value JSONB NULLABLE,           -- snapshot sebelum perubahan (untuk update/delete)
    new_value JSONB NULLABLE,           -- snapshot sesudah perubahan (untuk create/update)
    ip_address VARCHAR(45) NULLABLE,
    source VARCHAR(10) NOT NULL,        -- 'telegram'|'app'
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
)

Index: INDEX idx_audit_logs_user_created ON audit_logs(user_id, created_at DESC) — untuk query "riwayat aksi user X", pola sama seperti index transactions.

### 2.7 `accounts`
Kolom	Tipe	Constraint	Keterangan
id	UUID	PK, default gen_random_uuid()	
user_id	UUID	FK → users(id), NOT NULL	
account_name	VARCHAR(100)	NOT NULL	Misal "BCA Tabungan", "Cash"
bank_name	VARCHAR(100)	NULLABLE	NULL untuk dompet tunai
initial_balance	NUMERIC(14,2)	NOT NULL, default 0	Saldo awal saat akun dibuat
is_active	BOOLEAN	NOT NULL, default TRUE	
created_at	TIMESTAMPTZ	NOT NULL, default now()	
updated_at	TIMESTAMPTZ	NOT NULL, default now()	

Index: INDEX idx_accounts_user_id ON accounts(user_id)

### 2.8 `pending_transactions`

Hasil parsing LLM yang menunggu konfirmasi user sebelum menjadi transaksi nyata (REQUIREMENTS US-05/US-08, CODING_RULES §2.4 — pending-confirmation flow, ditambahkan di Phase 2, migrasi `0002` + `0003`).

| Kolom | Tipe | Constraint | Keterangan |
|---|---|---|---|
| id | UUID | PK, default `gen_random_uuid()` | |
| user_id | UUID | FK → users(id), NOT NULL | |
| action | VARCHAR(10) | NOT NULL, CHECK (`action IN ('create','update')`), default `'create'` | `'update'` = hasil edit transaksi yang menunggu konfirmasi |
| target_transaction_id | UUID | FK → transactions(id), NULLABLE, ON DELETE CASCADE | Wajib diisi jika `action = 'update'` |
| type | VARCHAR(10) | NOT NULL, CHECK (`type IN ('income','expense')`) | |
| total_amount | NUMERIC(14,2) | NOT NULL, CHECK (`total_amount > 0`) | |
| category_id | UUID | FK → categories(id), NOT NULL | |
| merchant | VARCHAR(150) | NULLABLE | |
| source | VARCHAR(10) | NOT NULL, CHECK (`source IN ('telegram','app')`) | |
| note | TEXT | NULLABLE | |
| confidence | VARCHAR(10) | NULLABLE | Hanya jika berasal dari parsing LLM |
| raw_input | TEXT | NULLABLE | Pesan asli dari user (untuk debug/refetch) |
| items | JSONB | NULLABLE | Line items hasil parsing (mirip `transaction_items`) |
| created_at | TIMESTAMPTZ | NOT NULL, default `now()` | |
| expires_at | TIMESTAMPTZ | NULLABLE | Batas waktu konfirmasi (default 10 menit) |

**Index:**
- `INDEX idx_pending_transactions_user_id ON pending_transactions(user_id)`
- `INDEX idx_pending_transactions_user_created ON pending_transactions(user_id, created_at DESC)` — ambil pending terbaru per user
- `INDEX idx_pending_transactions_action ON pending_transactions(action)`

> Baris pending dihapus dalam commit yang sama dengan transaksi hasil konfirmasi (tidak ada window crash) — lihat `transaction_service.create/update_transaction_internal(pending=...)`.

## 3. Prinsip Desain Query & Performa

### 3.1 Composite index, bukan index per kolom terpisah
Query paling umum di sistem ini berbentuk "transaksi milik user X, dalam rentang tanggal Y" — karena itu index `(user_id, transaction_date)` sengaja dibuat sebagai **composite index**, bukan dua index terpisah. PostgreSQL bisa memakai composite index untuk query yang filter kombinasi kedua kolom jauh lebih efisien dibanding menggabungkan dua index tunggal.

### 3.2 Pagination — cursor-based, bukan OFFSET
```sql
-- HINDARI (lambat untuk offset besar, terutama di skala ratusan user):
SELECT * FROM transactions WHERE user_id = :uid ORDER BY transaction_date DESC OFFSET 5000 LIMIT 20;

-- PAKAI (cursor-based, performa konsisten berapa pun offset-nya):
SELECT * FROM transactions
WHERE user_id = :uid AND (transaction_date, id) < (:last_date, :last_id)
ORDER BY transaction_date DESC, id DESC
LIMIT 20;
```
Endpoint list transaksi di REST API **wajib** pagination dari awal — jangan pernah return semua row tanpa limit, walau skalanya masih puluhan user.

### 3.3 Hindari N+1 Query
Saat ambil transaksi beserta item-nya, gunakan eager loading eksplisit di SQLAlchemy:
```python
from sqlalchemy.orm import selectinload

stmt = select(Transaction).options(
    selectinload(Transaction.items)
).where(Transaction.user_id == user_id)
```
Bukan lazy-load default yang memicu satu query tambahan per transaksi (N+1 problem) — di skala puluhan-ratusan user dengan report yang menampilkan banyak transaksi sekaligus, ini perbedaan antara 1 query vs ratusan query per request.

### 3.4 Query agregasi report — dorong ke database, bukan di Python
```sql
-- Contoh: total pengeluaran per kategori bulan ini
SELECT c.name, SUM(t.total_amount) as total
FROM transactions t
JOIN categories c ON c.id = t.category_id
WHERE t.user_id = :uid
  AND t.type = 'expense'
  AND t.transaction_date >= :start_of_month
GROUP BY c.name
ORDER BY total DESC;
```
Jangan tarik seluruh row transaksi ke aplikasi lalu hitung total di Python — PostgreSQL jauh lebih efisien untuk agregasi (`SUM`, `GROUP BY`) dibanding loop di sisi aplikasi, dan ini mengurangi beban network + memori backend.

## 4. Konfigurasi Resource (VPS 8GB RAM / 4 vCPU)

### 4.1 PostgreSQL (`postgresql.conf`)
shared_buffers = 2GB
effective_cache_size = 5GB
max_connections = 50
work_mem = 16MB
maintenance_work_mem = 256MB

### 4.2 SQLAlchemy Connection Pool
```python
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=10,
    pool_pre_ping=True,
    pool_recycle=1800,  # recycle koneksi tiap 30 menit, cegah stale connection
)
```

### 4.3 Docker Compose — resource limit eksplisit
```yaml
services:
  db:
    image: postgres:16-alpine
    mem_limit: 2.5g
    environment:
      POSTGRES_DB: mymoney
      POSTGRES_USER: ${DB_USER}
      POSTGRES_PASSWORD: ${DB_PASSWORD}
    volumes:
      - pgdata:/var/lib/postgresql/data
    restart: unless-stopped

  backend:
    build: ./backend
    mem_limit: 1.5g
    depends_on:
      - db
    restart: unless-stopped
```

## 5. Migration Strategy

Alembic tetap dipakai untuk migration skema (TIDAK BERUBAH), TAPI target
koneksi sekarang connection string Supabase (dari project settings →
Database → Connection string). RLS policy sebaiknya **dipisah** dari
migration Alembic biasa — taruh di folder terpisah `backend/supabase_policies/`
sebagai file SQL murni, dijalankan manual via Supabase SQL Editor atau
Supabase CLI (`supabase db push`), karena Alembic tidak native mengerti
sintaks RLS Supabase dengan baik.

## 6. Extensibility — Hook untuk Skala Lebih Besar (Tidak Diimplementasi di v1)

Bagian ini **bukan implementasi**, hanya catatan desain agar migrasi ke skala lebih besar tidak memerlukan rombak total:

| Kebutuhan Masa Depan | Kesiapan Skema Saat Ini |
|---|---|
| Household/shared data | Tinggal tambah tabel `households` + `household_members`, lalu kolom `household_id` NULLABLE di `transactions` — tidak mengubah struktur yang ada |
| Caching layer (Redis) untuk report berat | `report_service.py` sudah terpisah sebagai service layer sendiri — cache bisa disisipkan di titik ini tanpa ubah API layer |
| Read replica | Koneksi database sudah terpusat lewat satu `db/session.py` — routing read/write terpisah bisa ditambah di titik ini tanpa ubah query logic |
| Partitioning tabel `transactions` by date | Kolom `transaction_date` sudah jadi bagian composite index utama — partitioning native PostgreSQL bisa diterapkan tanpa ubah pola query |

## 7. Seed Data — Kategori Default

Kategori default (`user_id = NULL`, `is_default = TRUE`) diisi lewat migration awal (`0001_initial_schema`), bukan hardcode di kode aplikasi. Nama seed mengikuti yang tertanam di migrasi (bahasa Inggris); daftar lengkap:

**Pengeluaran (expense):** Food, Transport, Shopping, Bills, Entertainment, Health, Education, Other
**Pemasukan (income):** Salary, Bonus, Investment, Gift, Other
**Transfer/Penyesuaian Akun:** Transfer (expense) dan Transfer (income) — `is_default = TRUE`, ditambahkan untuk balancing saat akun dinonaktifkan (lihat catatan §2.4).

Keunikan `(owner, name, type)` dijamin index `idx_categories_user_name_type` (§2.3) — kategori global memakai sentinel `00000000-0000-0000-0000-000000000000` sebagai owner. Aplikasi (REST/Android) menampilkan daftar gabungan: global default + kategori custom milik user.

## 8. Reset Password & Recovery (Supabase Auth) — BAGIAN BARU

Sistem ini TIDAK punya role admin (semua user self-register). Reset password
sepenuhnya ditangani **Supabase Auth** terhadap email terdaftar — backend
Python tidak menyimpan token reset apa pun; client (Flutter/bot) cukup
memanggil endpoint Supabase langsung.

**Flow lupa password (magic link / OTP di email):**
1. `POST {SUPABASE_URL}/auth/v1/recover` body `{"email": "<email>"}`, header
   `apikey: <anon key>` → Supabase mengirim email berisi link reset (atau
   kode OTP 6 digit, sesuai template email project).
2. User membuka link / memasukkan OTP → client verifikasi:
   `POST {SUPABASE_URL}/auth/v1/verify` body
   `{"type": "recovery", "email": "<email>", "token": "<otp/link token>"}` →
   respons berisi session sementara.
3. Client set password baru: `PUT {SUPABASE_URL}/auth/v1/user` body
   `{"password": "<password-baru>"}` dengan header
   `Authorization: Bearer <access_token sementara>`.

**Flow OTP murni (tanpa link):**
- `POST {SUPABASE_URL}/auth/v1/otp` body `{"email": "<email>", "create_user": false}`
  → OTP dikirim ke email → verifikasi via `/auth/v1/verify` dengan
  `{"type": "email", ...}`.

**Catatan (dibuktikan live 2026-08-26):**
- `recover`/`otp` selalu balas `200 {}` meski email tidak dikenal — anti user
  enumeration (identitas email tidak dibocorkan).
- Pengiriman email di-rate-limit per email (error `over_email_send_rate_limit`
  saat 2 email dikirim beruntun ke alamat sama) — proteksi anti-spam bawaan
  Supabase.
- `recover` TIDAK mengubah password: login dengan password lama tetap sukses
  setelah request recover.
- Konfigurasi template email (subject/isi link/OTP) di Dashboard Supabase →
  Authentication → Email Templates.

## 10. Row Level Security (RLS) — BAGIAN BARU, WAJIB

Setiap tabel yang berisi data spesifik-user WAJIB diaktifkan RLS dan diberi
policy eksplisit. Ini lapis keamanan tambahan di level database, independen
dari validasi backend Python.

```sql
-- Aktifkan RLS di semua tabel data user
ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transaction_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.categories ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.pending_transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_logs ENABLE ROW LEVEL SECURITY;

-- Contoh policy: user hanya bisa lihat/edit transaksi miliknya sendiri
CREATE POLICY "Users can view own transactions"
  ON public.transactions FOR SELECT
  USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own transactions"
  ON public.transactions FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- transaction_items: cek lewat parent transaction
CREATE POLICY "Users can view own transaction items"
  ON public.transaction_items FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM public.transactions t
      WHERE t.id = transaction_id AND t.user_id = auth.uid()
    )
  );

-- categories: user lihat kategori miliknya + kategori global (user_id NULL)
CREATE POLICY "Users can view own or global categories"
  ON public.categories FOR SELECT
  USING (user_id = auth.uid() OR user_id IS NULL);

-- Backend service (pakai service_role key) BYPASS semua RLS di atas —
-- ini yang membuat backend Python tetap bisa insert/update apa pun sesuai
-- validasi bisnisnya sendiri, RLS hanya membatasi akses LANGSUNG dari client.
```

**Prinsip penting**: RLS adalah lapis pertahanan TAMBAHAN, bukan pengganti
validasi service layer Python. Backend tetap wajib validasi `user_id`
secara eksplisit di setiap query (CODING_RULES.md), RLS mencegah kebocoran
kalau validasi backend ternyata ada bug.