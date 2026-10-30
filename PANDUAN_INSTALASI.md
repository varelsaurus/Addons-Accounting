# Panduan Menjalankan Odoo 19 + Modul Accounting (Windows)

Modul di repo ini (versi 19.0, dari Cybrosys CybroAddons):
- `base_accounting_kit` (fitur akuntansi lengkap)
- `base_account_budget`
- `cybrosys_support_client` (dependency)

## 1. Install Odoo 19 Community
1. Unduh installer Windows Odoo 19.0 Community dari https://www.odoo.com/page/download
   (idealnya build yang sama dengan pemilik data: **19.0.20261017**).
2. Install dengan opsi default. Installer ikut memasang **PostgreSQL 18**. Jangan ganti ke versi PostgreSQL yang lebih lama.
3. Pastikan http://localhost:8069 terbuka.

## 2. Ambil modul
Dengan Git:
```
cd C:\
git clone https://github.com/varelsaurus/Addons-Accounting.git odoo-custom-addons
```
Tanpa Git: klik **Code → Download ZIP**, ekstrak, lalu pastikan folder `base_accounting_kit`, `base_account_budget` dan `cybrosys_support_client` berada langsung di `C:\odoo-custom-addons\`.

## 3. Install dependensi Python
Buka PowerShell sebagai Administrator. Sesuaikan path Python bawaan Odoo jika berbeda:
```
& "C:\Program Files\Odoo 19.0.20261017\python\python.exe" -m pip install openpyxl ofxparse qifparse xlsxwriter
```

## 4. Edit odoo.conf
File: `C:\Program Files\Odoo 19.0.20261017\server\odoo.conf` (buka dengan Notepad sebagai Administrator).

- Tambahkan folder modul ke `addons_path` (pisahkan dengan koma, tanpa spasi):
  ```
  addons_path = C:\Program Files\Odoo 19.0.20261017\server\odoo\addons,C:\odoo-custom-addons
  ```
- Tambahkan **satu baris saja** (baris ganda membuat Odoo gagal start):
  ```
  pg_path = C:\Program Files\PostgreSQL\18\bin
  ```
- Pastikan ada `admin_passwd` (master password). Catat, karena diminta saat restore.

## 5. Restart service
PowerShell (Administrator):
```
Restart-Service odoo-server-19.0
```
Kalau gagal start, cek log di `C:\Program Files\Odoo 19.0.20261017\server\odoo.log`. Penyebab paling umum: baris ganda di `odoo.conf` atau path yang salah.

## 6. Restore database
1. Buka http://localhost:8069/web/database/manager
2. Klik **Restore Database**.
3. Isi master password, pilih file backup `.zip` yang dikirim pemilik data, dan beri nama database.
4. Pilih **"This database might have been moved"**. Aktifkan neutralize jika tersedia, supaya email dan cron tidak berjalan dari laptop ini.
5. Klik Continue dan tunggu sampai selesai.

## 7. Login
Login memakai email dan password dari database asli. Password tidak ada di GitHub, jadi pemilik data harus memberikannya lewat jalur pribadi.

**Untuk pemilik data (sebelum membuat backup):**
1. Di Odoo Anda buka Settings → Users → New.
2. Isi nama dan email teman, beri hak akses yang sesuai (misalnya Accounting / Billing atau Administrator), dan set password sementara.
3. Buat backup ulang di `/web/database/manager` supaya user baru itu ikut di file zip.
4. Kirim email, password sementara dan file zip lewat chat atau Drive pribadi.

**Untuk teman:** login dengan email dan password sementara tadi, lalu ganti password lewat menu profil (kanan atas → Preferences → Account Security).

Kalau modul accounting tidak muncul, aktifkan Developer Mode (`/odoo?debug=1`), buka Apps → Update Apps List, lalu cari "Odoo 19 Accounting Kit".

## Catatan
- Setiap laptop punya database sendiri. Perubahan data **tidak** otomatis sinkron.
- File backup berisi data keuangan dan hash password. Kirim lewat Drive pribadi atau flashdisk, **jangan ke GitHub**.
- `odoo.conf` tidak ada di repo karena berisi password.
