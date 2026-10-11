# Panduan: Perbaiki Link Konfirmasi Email Supabase (`localhost:3000` → domain produksi)

> **Masalah (Req 1):** email konfirmasi pendaftaran berisi tautan yang menunjuk ke
> `http://localhost:3000` sehingga tidak bisa dibuka di HP pengguna.
>
> **Status kode:** ✅ sudah benar — tidak ada perubahan kode yang diperlukan.
> Perbaikan **hanya** di **Supabase Dashboard**.

---

## 1. Akar masalah

Supabase Auth menyusun tautan konfirmasi dari template email, kurang lebih:

```html
<a href="{{ .ConfirmationURL }}">Konfirmasi email</a>
```

`{{ .ConfirmationURL }}` dibentuk dari **redirect URL** yang diminta aplikasi,
**tetapi hanya jika URL itu terdaftar di allow-list**. Alur keputusannya:

1. Aplikasi mengirim `emailRedirectTo` saat `signUp()` — di kode kita:
   `app/lib/screens/auth_screen.dart` → `emailRedirectTo: AppConfig.botPublicUrl`
   (nilai `BOT_PUBLIC_URL` = `https://mymoneyofficial.online`).
2. Supabase mengecek apakah `https://mymoneyofficial.online` ada di daftar
   **Redirect URLs**.
3. **Jika tidak ada** (kondisi saat ini) → Supabase mengabaikannya dan memakai
   **Site URL** sebagai gantinya.
4. **Site URL** pada project ini masih nilai default → `http://localhost:3000`.

Itulah sebabnya tautan di email tetap `localhost:3000` meskipun aplikasi sudah
mengirim URL yang benar. **Jadi cukup memperbaiki Site URL + Redirect URLs.**

Referensi: <https://supabase.com/docs/guides/auth/redirect-urls>

---

## 2. Langkah perbaikan (klik-per-klik)

### 2.1 Buka URL Configuration

1. Buka <https://supabase.com/dashboard> dan login.
2. Pilih project **MyMoney** — project ref `fqjkqcigjeyooejcgbrk`
   (URL langsung: <https://supabase.com/dashboard/project/fqjkqcigjeyooejcgbrk/auth/url-configuration>).
3. Di sidebar kiri: **Authentication** → **URL Configuration**.

### 2.2 Isi Site URL

Ganti **Site URL** dari `http://localhost:3000` menjadi:

```
https://mymoneyofficial.online
```

### 2.3 Tambahkan Redirect URLs (allow-list)

Tambahkan **satu per satu** lewat tombol **Add URL** (kolom *Redirect URLs*):

| Redirect URL                                    | Kegunaan                                     |
| ----------------------------------------------- | -------------------------------------------- |
| `https://mymoneyofficial.online`                | Landing page utama setelah konfirmasi        |
| `https://mymoneyofficial.online/**`             | Semua sub-path (mis. `/auth/callback`)       |
| `https://api.mymoneyofficial.online/**`         | Callback API bila diperlukan                 |
| `mymoney://**`                                   | Deep link balik ke app (opsional, lihat §3.3) |
| `http://10.0.2.2:8000/**`                        | Hanya untuk dev di emulator Android          |
| `http://localhost:3000/**`                       | Hanya untuk dev lokal — **boleh dihapus** jika tidak dipakai lagi |

> ⚠️ Jangan biarkan `http://localhost:3000` sebagai **Site URL**. Bila masih
> dipakai untuk development, biarkan hanya di daftar **Redirect URLs** (bukan
> Site URL).

### 2.4 Simpan

Klik **Save**. Perubahan berlaku segera (tanpa redeploy).

### 2.5 Pastikan Confirm Email aktif & template memakai ConfirmationURL

1. **Authentication** → **Providers** → **Email** → pastikan
   **Confirm email** = **ON**.
2. **Authentication** → **Emails** → tab **Templates** → pilih
   **Confirm signup**.
3. Pastikan isi template memakai variabel bawaan:
   - `{{ .ConfirmationURL }}`, atau
   - `{{ .SiteURL }}/auth/confirm?token_hash={{ .TokenHash }}&type=signup`.

   Bila template pernah diubah manual dan memuat `{{ .SiteURL }}`, nilainya akan
   ikut memakai **Site URL** baru pada §2.2 — jadi perbaikan §2.2 sudah cukup.

---

## 3. Catatan penting

### 3.1 Nilai yang harus konsisten

| Lokasi                                   | Nilai                              |
| ---------------------------------------- | ---------------------------------- |
| Supabase → Site URL                      | `https://mymoneyofficial.online`   |
| Supabase → Redirect URLs                 | allow-list di atas                 |
| root `.env` → `BOT_PUBLIC_URL`           | `https://mymoneyofficial.online`   |
| root `.env` → `APP_BASE_URL`             | `https://api.mymoneyofficial.online` |
| dart-define saat build app → `BOT_PUBLIC_URL` | `https://mymoneyofficial.online` |
| dart-define saat build app → `APP_BASE_URL`   | `https://api.mymoneyofficial.online` |

`BOT_PUBLIC_URL` adalah sumber `emailRedirectTo` dan `redirectTo`
(lihat `app/lib/screens/auth_screen.dart`), jadi kalau salah satu berbeda,
Supabase akan menolak redirect dan jatuh kembali ke Site URL.

### 3.2 Batas kirim email bawaan Supabase

Project Supabase melakukan **rate-limit ketat** pada email bawaan (beberapa
email/jam). Jika pengguna produksi banyak mendaftar, pasang SMTP sendiri:
**Project Settings** → **Authentication** → **SMTP Settings** (mis. Resend,
SendGrid, Postmark, atau SMTP Google Workspace). Setelah SMTP aktif, batas naik
dan pengiriman lebih andal.

### 3.3 Deep link ke aplikasi (opsional, lanjutan)

Saat ini tautan konfirmasi membuka **halaman web** `https://mymoneyofficial.online`.
Agar tautan membuka aplikasi langsung:

1. Tambahkan `mymoney://**` ke Redirect URLs (sudah ada di tabel §2.3).
2. Ubah `emailRedirectTo` menjadi `mymoney://auth-callback` dan daftarkan
   custom scheme / App Links di `android/app/src/main/AndroidManifest.xml`
   serta `ios/Runner/Info.plist`.
3. Tangani `onAuthStateChange` / `getInitialLink` (di app sudah ada
   `app_links` di dependensi) dan panggil `supabase.auth.exchangeCodeForSession`
   bila memakai PKCE.

Fitur ini **tidak diperlukan** untuk menutup bug Req 1.

---

## 4. Verifikasi (wajib dilakukan setelah §2.4)

1. Di Supabase: **Authentication** → **URL Configuration** → pastikan
   Site URL = `https://mymoneyofficial.online`.
2. Jalankan app di HP (atau `flutter run` di device fisik).
3. Daftar dengan **email baru** (yang belum pernah terdaftar — bila email sudah
   ada, Supabase *tidak* mengirim email verifikasi baru).
4. Buka inbox email tersebut, hover/long-press tautan konfirmasi.
   **Harapan:** tautan diawali `https://mymoneyofficial.online/...`
   (bukan `localhost:3000`).
5. Buka tautan di HP → halaman konfirmasi sukses.
6. Kembali ke app → login dengan email & password tadi → berhasil masuk.

### Jika masih `localhost:3000`

| Gejala                       | Penyebab & tindakan                                                                                       |
| ---------------------------- | --------------------------------------------------------------------------------------------------------- |
| Link masih localhost         | Site URL belum tersimpan / salah project. Buka ulang §2.1–§2.4, cek project ref `fqjkqcigjeyooejcgbrk`.    |
| Link benar tapi error "redirect not allowed" | `emailRedirectTo` belum ada di Redirect URLs. Tambahkan persis sama (termasuk skema & tanpa trailing slash ganda). |
| Email tidak masuk sama sekali | Bukan masalah URL — cek spam, cek rate-limit email bawaan (§3.2), atau email sudah terdaftar (anti-enumeration). |
| Link benar tapi blank page  | Belum ada halaman/web handler di `BOT_PUBLIC_URL`. Untuk sementara cukup andalkan deep link §3.3 atau sediakan halaman statis sederhana. |

---

## 5. Ringkasan satu baris

> Supabase Dashboard → **Authentication → URL Configuration** → Site URL =
> `https://mymoneyofficial.online`, lalu **Add URL** `https://mymoneyofficial.online`
> dan `https://mymoneyofficial.online/**` → **Save**. Selesai — tanpa perubahan kode.
