# SKILL.md — MyMoney (Antigravity Skills)

## 1. Ringkasan

Dokumen ini mendaftar Antigravity Skills yang dipasang untuk proyek MyMoney, format instruksi yang dibaca agent (Antigravity) saat membantu development — bukan bagian dari aplikasi itu sendiri.

**Peringatan penting sebelum dipakai**: kedua skill di bawah ini adalah "token saver" yang **sudah diuji independen oleh JetBrains** dengan hasil jauh berbeda dari klaim marketing masing-masing repo. Dicantumkan di sini atas permintaan eksplisit untuk tujuan eksperimen pribadi, **bukan karena efikasinya terbukti**.

## 2. Skill: `caveman`

**Repo**: `JuliusBrussee/caveman`
**Fungsi klaim**: membuat agent merespons singkat gaya "manusia gua" (buang kata pengisi, pertahankan kode/command byte-exact) untuk hemat token output.

**Install (Antigravity):**
```bash
npx skills add https://github.com/JuliusBrussee/caveman --skill caveman
```
Lokasi setelah install: `.agent/skills/caveman/SKILL.md` (atau `~/.gemini/antigravity/skills/caveman/`).

**Klaim vs realita (hasil benchmark independen JetBrains, 80 paired task A/B):**
| | Diklaim | Diukur nyata |
|---|---|---|
| Penghematan token | −65% | **−8.5%** |

Skill ini **user-activated** (baru aktif kalau dipicu frasa seperti "caveman mode" atau "be brief"). Perlu diingat: angka −8.5% di atas didapat dari kondisi **dipaksa aktif di setiap respons** (best-case untuk skill ini) — dalam pemakaian normal di mana agent harus memutuskan sendiri kapan mengaktifkan, penghematan riil kemungkinan **lebih rendah lagi** dari 8.5%.

**Catatan pemakaian**: karena penghematannya kecil dan gaya responsnya sengaja dibuat sangat ringkas/terputus, pertimbangkan trade-off keterbacaan — terutama untuk task yang butuh penjelasan (misal debugging kompleks), gaya "caveman" bisa membuat agent memotong konteks penting demi keringkasan.

## 3. Skill: `rtk`

**Fungsi klaim**: token saver, mengklaim penghematan 60-90% token.

**Klaim vs realita (hasil benchmark independen JetBrains, sama metodologi):**
| | Diklaim | Diukur nyata |
|---|---|---|
| Penghematan token | −60% hingga −90% | **+7.6% (justru bertambah)** |

**Peringatan lebih keras untuk skill ini dibanding `caveman`**: hasil pengujian menunjukkan skill ini **kontraproduktif** — bukan sekadar "kurang efektif dari klaim", tapi **menambah** pemakaian token dibanding tanpa skill sama sekali. Kemungkinan penyebab: overhead instruksi tambahan yang harus diproses agent di setiap turn melebihi penghematan yang didapat dari gaya respons yang dihasilkan.

## 4. Rekomendasi Pemakaian untuk MyMoney

Karena dua skill ini dipasang sebagai **eksperimen sadar**, bukan solusi terbukti, berikut cara memakainya secara bertanggung jawab:

1. **Pantau token usage Anda sendiri** sebelum dan sesudah skill aktif (Antigravity/API dashboard) — jangan asumsikan skill ini bekerja hanya karena sudah terpasang.
2. **Jangan paksa aktif permanen** (`force caveman every reply`) — biarkan mekanisme user-activated bekerja sesuai desainnya, atau ukur dulu di task kecil sebelum diaktifkan luas ke seluruh sesi development MyMoney.
3. **Prioritaskan kejelasan output di atas penghematan token** untuk task berisiko tinggi — terutama saat generate skema database, logic validasi transaksi, atau security-related code (auth, hashing). Kesalahan kecil akibat output yang terlalu dipotong jauh lebih mahal (waktu debug, potensi bug finansial) dibanding penghematan token yang bahkan belum terbukti signifikan.
4. **Evaluasi ulang setelah 1-2 minggu pemakaian.** Kalau data token usage Anda sendiri menunjukkan skill ini tidak membantu (atau memperburuk seperti temuan `rtk`), lepas dari `.agent/skills/` — tidak ada kerugian meninggalkan skill yang tidak terbukti berguna.

## 5. Terkait: Filter Kualitas Kontribusi (Bukan Bagian SKILL.md)

`peakoss/anti-slop` — yang sempat dipertimbangkan masuk sini — **bukan Antigravity Skill**, melainkan GitHub Action untuk menyaring Pull Request berkualitas rendah dari kontributor luar. Karena repo MyMoney bersifat publik, ini tetap relevan tapi ditempatkan di lokasi yang benar: `CODING_RULES.md` §6 (CI/CD), bukan di sini.