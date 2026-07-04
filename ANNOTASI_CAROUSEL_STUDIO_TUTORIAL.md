# Tutorial Penggunaan Annotasi Carousel Studio

Dokumen ini menjelaskan cara menjalankan dan menggunakan MVP internal Annotasi Carousel Studio dari repo yang dikirim.

## 1. Ringkasan Aplikasi

Annotasi Carousel Studio adalah internal content engine untuk membuat konten faceless berbasis AI. Aplikasi ini menerima ide, topik, source kajian, atau transcript, lalu menghasilkan:

- carousel text,
- PNG carousel 1080x1350,
- MP4 vertical 1080x1920,
- voiceover script,
- video dengan voiceover,
- review/edit workflow,
- content calendar,
- source dan transcript tracking,
- highlight/candidate generation,
- final posting package.

Aplikasi ini dibuat sebagai standalone HTTP service. Hermes/Telegram cukup memanggil endpoint HTTP service ini.

## 2. Struktur File Saat Ini

```text
annotasi-carousel-studio/
├── app.py              # Semua logic utama service saat ini
├── render_png.js       # Renderer PNG carousel via Playwright
├── package.json        # Dependency Node untuk Playwright
├── .env.example        # Template environment variable
├── README.md           # Dokumentasi bawaan repo
└── data/               # Akan terbentuk otomatis saat service dipakai
```

Catatan: saat ini sebagian besar logic masih berada di `app.py`. Ini masih wajar untuk prototype/MVP, tapi perlu dipisah agar mudah dibaca dan dikembangkan.

## 3. Prasyarat VPS/Local

Pastikan tersedia:

```bash
python3 --version
node --version
npm --version
ffmpeg -version
ffprobe -version
```

Jika belum ada FFmpeg di Ubuntu:

```bash
sudo apt update
sudo apt install -y ffmpeg
```

## 4. Setup Environment

Masuk ke folder project:

```bash
cd annotasi-carousel-studio
```

Buat `.env`:

```bash
cp .env.example .env
nano .env
```

Minimal isi:

```bash
AI_BASE_URL=http://127.0.0.1:20128/v1
AI_MODEL=annotasi-coding
AI_API_KEY=isi_api_key_internal_kamu
ANNOTASI_HOST=127.0.0.1
ANNOTASI_PORT=8097
CONTENT_STORAGE_DIR=./data/content
SOURCE_STORAGE_DIR=./data/sources
CONTENT_EXPORT_DIR=./data/exports
CONTENT_AUDIO_DIR=./data/audio
CONTENT_PACKAGE_DIR=./data/packages
CONTENT_TIMEZONE=Asia/Jakarta
```

Jangan hardcode API key di source code.

## 5. Install Renderer PNG

PNG renderer memakai Playwright.

```bash
npm install
npm run install:browsers
```

Kalau hanya ingin test endpoint AI tanpa render PNG, step ini bisa ditunda. Tapi untuk `/render`, wajib ada.

## 6. Menjalankan Service

```bash
set -a
. ./.env
set +a
python3 app.py
```

Health check:

```bash
curl http://127.0.0.1:8097/health
```

Output yang diharapkan:

```json
{"status":"ok","service":"annotasi-carousel-studio"}
```

## 7. Workflow Cepat: Dari Ide Menjadi Package Siap Upload

Workflow ini cocok kalau kamu belum memakai source/transcript.

### 7.1 Generate konten hikmah

```bash
curl -s http://127.0.0.1:8097/api/v1/content/hikmah \
  -H 'Content-Type: application/json' \
  -d '{"topic":"kerja keras dan rezeki halal"}'
```

Simpan `content_id` yang muncul, misalnya:

```text
cnt_20260704_ab12cd34
```

### 7.2 Review konten

```bash
curl -s http://127.0.0.1:8097/api/v1/content/<content_id>/review
```

### 7.3 Approve konten

```bash
curl -s -X POST http://127.0.0.1:8097/api/v1/content/<content_id>/approve \
  -H 'Content-Type: application/json' \
  -d '{"reviewedBy":"internal","notes":"checked"}'
```

### 7.4 Render PNG carousel

```bash
curl -s http://127.0.0.1:8097/api/v1/content/<content_id>/render/png \
  -H 'Content-Type: application/json' \
  -d '{"format":"instagram_carousel","template":"annotasi_hikmah_dark","forceRegenerate":false}'
```

Output PNG tersimpan di:

```text
./data/exports/<content_id>/<render_id>/slide-01.png
...
```

### 7.5 Render MP4 vertical

```bash
curl -s http://127.0.0.1:8097/api/v1/content/<content_id>/render/video \
  -H 'Content-Type: application/json' \
  -d '{"format":"shorts_vertical","motionPreset":"calm_zoom","durationPerSlideSeconds":5,"forceRegenerate":false}'
```

Output video:

```text
./data/exports/<content_id>/<video_render_id>/final.mp4
```

### 7.6 Ambil script voiceover

```bash
curl -s http://127.0.0.1:8097/api/v1/content/<content_id>/voiceover
```

Rekam suara kamu membaca script tersebut, lalu simpan misalnya:

```text
./data/audio/<content_id>/voiceover.m4a
```

### 7.7 Mix voiceover ke video

```bash
curl -s http://127.0.0.1:8097/api/v1/content/<content_id>/audio/mix \
  -H 'Content-Type: application/json' \
  -d '{
    "audioFilePath":"./data/audio/<content_id>/voiceover.m4a",
    "audioMode":"voiceover",
    "normalizeAudio":true,
    "fitMode":"trim_or_pad",
    "forceRegenerate":false
  }'
```

Output final:

```text
./data/exports/<content_id>/<audio_render_id>/final-voiceover.mp4
```

### 7.8 Schedule konten

```bash
curl -s http://127.0.0.1:8097/api/v1/content/<content_id>/schedule \
  -H 'Content-Type: application/json' \
  -d '{"platform":"instagram","scheduledDate":"2026-07-05","timezone":"Asia/Jakarta"}'
```

### 7.9 Cek readiness

```bash
curl -s http://127.0.0.1:8097/api/v1/content/<content_id>/ready-to-post
```

### 7.10 Buat package siap upload

```bash
curl -s http://127.0.0.1:8097/api/v1/content/<content_id>/package \
  -H 'Content-Type: application/json' \
  -d '{"createZip":true,"includeMetadata":true,"includePlatformCaptions":true,"forceRegenerate":false}'
```

Package tersimpan di:

```text
./data/packages/<content_id>/<package_id>/
```

Struktur package:

```text
01-carousel/
02-video/
03-copy/
04-review/
05-metadata/
README.md
```

Setelah upload manual ke Instagram/TikTok/YouTube Shorts, tandai uploaded:

```bash
curl -s http://127.0.0.1:8097/api/v1/content/<content_id>/uploaded \
  -H 'Content-Type: application/json' \
  -d '{"platform":"instagram","url":"https://instagram.com/..."}'
```

## 8. Workflow Lengkap: Dari Source Kajian + Transcript

Workflow ini lebih aman untuk konten dakwah karena source, credit, transcript, segment, dan context dicatat.

### 8.1 Tambah source

```bash
curl -s http://127.0.0.1:8097/api/v1/sources \
  -H 'Content-Type: application/json' \
  -d '{
    "title":"Kajian Rezeki Halal",
    "speakerName":"Ustadz Example",
    "sourceUrl":"https://youtube.com/example",
    "platform":"youtube",
    "sourceType":"youtube_video",
    "permissionStatus":"allowed_with_credit",
    "topic":"rezeki halal"
  }'
```

Simpan `source_id`.

### 8.2 Set credit

```bash
curl -s http://127.0.0.1:8097/api/v1/sources/<source_id>/credit \
  -H 'Content-Type: application/json' \
  -d '{"creditText":"Sumber: Kajian Rezeki Halal - Ustadz Example"}'
```

### 8.3 Review dan approve source

```bash
curl -s http://127.0.0.1:8097/api/v1/sources/<source_id>/review
curl -s -X POST http://127.0.0.1:8097/api/v1/sources/<source_id>/approve
```

### 8.4 Tambah transcript

```bash
curl -s http://127.0.0.1:8097/api/v1/sources/<source_id>/transcript \
  -H 'Content-Type: application/json' \
  -d '{"transcriptText":"Paste transcript kajian di sini..."}'
```

### 8.5 Generate segment

```bash
curl -s -X POST http://127.0.0.1:8097/api/v1/sources/<source_id>/segments/generate
```

Lihat segment:

```bash
curl -s http://127.0.0.1:8097/api/v1/sources/<source_id>/segments
```

### 8.6 Generate highlight/candidate

```bash
curl -s http://127.0.0.1:8097/api/v1/sources/<source_id>/highlights \
  -H 'Content-Type: application/json' \
  -d '{"candidateCount":10,"preferredTypes":["carousel","short_video","voiceover_reflection","quote_post"],"allowHighRisk":false}'
```

### 8.7 Approve candidate

```bash
curl -s -X POST http://127.0.0.1:8097/api/v1/candidates/<candidate_id>/approve
```

### 8.8 Generate content dari candidate

```bash
curl -s -X POST http://127.0.0.1:8097/api/v1/candidates/<candidate_id>/generate-content
```

Setelah mendapatkan `content_id`, lanjutkan pipeline biasa:

```text
review → approve → render PNG → render MP4 → voiceover → package → upload manual
```

## 9. Mapping Command Telegram ke API

Hermes cukup memanggil endpoint HTTP lalu mengirim isi `telegramMessages` ke Telegram.

Command utama:

```text
/hikmah <topic>                    -> POST /api/v1/content/hikmah
/review <content_id>               -> GET /api/v1/content/{id}/review
/approve <content_id>              -> POST /api/v1/content/{id}/approve
/render <content_id>               -> POST /api/v1/content/{id}/render/png
/video <content_id>                -> POST /api/v1/content/{id}/render/video
/voiceover <content_id>            -> GET /api/v1/content/{id}/voiceover
/mixvoice_file <id> <audio_path>   -> POST /api/v1/content/{id}/audio/mix
/schedule <id> <date> <platform>   -> POST /api/v1/content/{id}/schedule
/ready_to_post <id>                -> GET /api/v1/content/{id}/ready-to-post
/package <id>                      -> POST /api/v1/content/{id}/package
/uploaded <id> <platform> <url>    -> POST /api/v1/content/{id}/uploaded
```

Source workflow:

```text
/source_add ...                    -> POST /api/v1/sources
/source_credit <id> ...            -> POST /api/v1/sources/{id}/credit
/source_approve <id>               -> POST /api/v1/sources/{id}/approve
/transcript_add <id> ...           -> POST /api/v1/sources/{id}/transcript
/segments_generate <id>            -> POST /api/v1/sources/{id}/segments/generate
/highlights_from_source <id>       -> POST /api/v1/sources/{id}/highlights
/candidates <source_id>            -> GET /api/v1/sources/{id}/candidates
/candidate_approve <candidate_id>  -> POST /api/v1/candidates/{id}/approve
/generate_from_candidate <id>      -> POST /api/v1/candidates/{id}/generate-content
```

## 10. Urutan Harian yang Disarankan

Untuk produksi konten harian Annotasi Hikmah:

1. Pilih topik/source.
2. Generate candidate atau langsung `/hikmah`.
3. Review manual.
4. Edit slide/caption bila perlu.
5. Approve.
6. Render PNG.
7. Render MP4.
8. Rekam voiceover sendiri.
9. Mix voiceover.
10. Package.
11. Upload manual.
12. Tandai uploaded.

## 11. Catatan Penting untuk Konten Dakwah

Sebelum upload, wajib cek:

- sumber jelas,
- izin/permission dicatat,
- credit ada,
- tidak menciptakan ayat/hadits palsu,
- tidak mengatasnamakan ustadz tanpa source,
- tidak memotong makna,
- judul tidak clickbait berlebihan,
- voiceover memakai suara sendiri,
- konten sudah direview manual.

Kalimat pengingat utama:

```text
Review kembali sebelum upload agar tidak salah konteks.
```
