MSG_WELCOME = """👋 Selamat Datang di AI Content Generator
Saya dapat membantu mengubah ide atau deskripsi Anda menjadi:

1. Gambar
2. Video
3. Gambar + Caption
4. Video + Caption
5. Caption

✏️ Cara Penggunaan
Kirimkan ide atau deskripsi konten yang ingin dibuat.
Contoh:
• Kucing astronaut berjalan di bulan
• Promosi kopi kekinian
• Pantai tropis saat matahari terbenam

Setelah menerima deskripsi Anda, saya akan menanyakan jenis konten yang ingin dibuat.
Silakan kirim ide atau deskripsi konten Anda."""

MSG_MENU = """✅ Prompt diterima

Prompt:
{prompt}

Pilih jenis konten yang ingin dibuat:

1. Gambar
2. Video
3. Gambar + Caption
4. Video + Caption
5. Caption
0. Batal

Balas dengan ANGKA saja."""

MSG_RASIO = """📐 Pilih rasio gambar:

1. 1:1   — Square (Feed)
2. 9:16  — Portrait (Story/Reels)
3. 16:9  — Landscape (YouTube/Banner)
4. 3:4   — Portrait (Feed)
5. 4:3   — Landscape (Presentasi)
6. 4:5   — Portrait (Feed Instagram)
7. 5:4   — Landscape (Feed)
8. 3:2   — Landscape (Foto)
9. 2:3   — Portrait (Foto)
10. 21:9  — Ultrawide (Cinematic)

Balas dengan ANGKA saja."""

MSG_RESOLUSI = """Rasio dipilih: {rasio} ({desc_rasio})

📏 Pilih resolusi output:

1. 480p  — Cepat, ukuran kecil
2. 720p  — Standar, kualitas baik

Balas dengan ANGKA saja."""

MSG_KONFIRMASI_GENERATE = """🔍 Konfirmasi Generate

Prompt   : {prompt}
Rasio    : {rasio} ({desc_rasio})
Resolusi : {resolusi}

Ketik YA untuk lanjut atau BATAL untuk membatalkan."""

MSG_INVALID_MENU = """❌ Pilihan tidak valid.

Balas dengan ANGKA sesuai menu:

1. Gambar
2. Video
3. Gambar + Caption
4. Video + Caption
5. Caption
0. Batal"""

MSG_INVALID_RASIO = """❌ Pilihan rasio tidak valid.

Balas dengan angka 1-9 sesuai pilihan di atas."""

MSG_INVALID_RESOLUSI = """❌ Pilihan resolusi tidak valid.

Balas dengan angka 1-2 sesuai pilihan di atas."""

MSG_CANCELLED = """🚫 Proses dibatalkan.

Silakan kirim ide atau deskripsi konten baru untuk memulai lagi."""

MSG_SESSION_TIMEOUT = """⏰ Sesi Anda telah berakhir karena tidak ada aktivitas selama 2 menit.

Silakan kirim ide atau deskripsi konten baru untuk memulai kembali."""

MSG_CAPTION_REVISION = """{caption}

---
💡 Jika ingin mengembangkan atau merevisi caption ini, langsung kirim instruksinya.

Contoh:
• buat lebih profesional
• lebih santai
• tambahkan CTA
• tambahkan hashtag

Ketik SELESAI jika sudah selesai."""

MSG_CAPTION_REVISED = """{caption}

---
💡 Mau revisi lagi? Langsung kirim instruksinya.
Ketik SELESAI jika sudah selesai."""

MSG_CAPTION_DONE = """✅ Caption sudah selesai.

Silakan kirim ide baru untuk membuat konten berikutnya."""

MSG_FEATURE_WIP = """⚠️ Fitur {fitur} masih dalam pengembangan.

Sementara Anda bisa menggunakan menu 5 (Caption).
Kirim ide baru untuk mencoba lagi."""

MSG_ERROR_GENERAL = """⚠️ Terjadi kendala teknis.

Silakan coba kirim ulang pesan Anda. Jika masih error, tunggu beberapa saat."""

MSG_ERROR_BUDGET = """⚠️ Budget API harian telah habis.

Pembuatan konten tidak dapat dilakukan sementara ini. Silakan hubungi admin atau coba lagi besok."""

MSG_ERROR_CONTENT_FILTER = """⚠️ Deskripsi kamu tidak dapat diproses karena terdeteksi oleh content filter.

Coba gunakan deskripsi yang berbeda dan hindari kata-kata yang sensitif."""

MSG_ERROR_UPLOAD = """⚠️ Konten berhasil dibuat, namun gagal upload ke Drive.

Silakan coba lagi atau hubungi admin jika masalah berlanjut."""

MSG_RATE_LIMITED = """⏳ Terlalu banyak permintaan.

Silakan tunggu beberapa saat sebelum mengirim pesan lagi."""
