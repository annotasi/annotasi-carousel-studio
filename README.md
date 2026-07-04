# Annotasi Carousel Studio

Milestone 1 standalone content engine for the Annotasi internal Telegram workflow.

This is intentionally a small HTTP service instead of a Hermes patch because the accessible workspace does not include the Hermes repository. Hermes can call this service from its existing Telegram command handlers without changing the production AI gateway or restarting services during development.

## What It Does

- Generates Bahasa Indonesia carousel packages through the OpenAI-compatible 9Router endpoint.
- Supports `/carousel`, `/hikmah`, `/caption`, `/voiceover`, `/content`, and `/ideas` workflows via HTTP endpoints.
- Saves generated content as local JSON files.
- Returns `telegramMessages` arrays that are already split for Telegram message limits.
- Validates the AI JSON structure before saving.
- Adds dakwah safety guardrails to the system prompt and response validation.
- Renders existing carousel content into 1080x1350 PNG slides with the `annotasi_hikmah_dark` template.
- Stores render metadata beside the existing content JSON record.
- Converts completed PNG carousel renders into 1080x1920 vertical MP4 videos for Shorts/Reels/TikTok.
- Mixes a user-provided voiceover audio file into the latest completed MP4 video.
- Adds review/edit workflow status, render staleness, upload markers, and a simple content calendar.
- Tracks source materials, transcripts, transcript segments, permissions, credits, and source-content links.
- Finds transcript highlights and stores clip/content candidates that can be reviewed before content generation.
- Exports ready-to-upload content packages with media, captions, metadata, ZIP archive, and posting checklists.

## Files

- `app.py` - HTTP service, AI client, validation, JSON storage, render metadata, and Telegram formatting.
- `render_png.js` - Playwright renderer for branded PNG carousel slides.
- `package.json` - local Node dependency metadata for Playwright rendering.
- `.env.example` - environment variables for local or VPS configuration.
- `README.md` - runbook and Hermes integration notes.

## Environment Variables

Required:

```sh
AI_BASE_URL=http://127.0.0.1:20128/v1
AI_MODEL=annotasi-coding
AI_API_KEY=your-configured-key
```

Optional:

```sh
ANNOTASI_HOST=127.0.0.1
ANNOTASI_PORT=8097
CONTENT_STORAGE_DIR=./data/content
CONTENT_EXPORT_DIR=./data/exports
CONTENT_AUDIO_DIR=./data/audio
AI_TIMEOUT_SECONDS=90
TELEGRAM_MESSAGE_LIMIT=3900
LOG_LEVEL=INFO
CAROUSEL_DEFAULT_TEMPLATE=annotasi_hikmah_dark
CAROUSEL_WIDTH=1080
CAROUSEL_HEIGHT=1350
CAROUSEL_RENDER_TIMEOUT_SECONDS=60
VIDEO_DEFAULT_FORMAT=shorts_vertical
VIDEO_WIDTH=1080
VIDEO_HEIGHT=1920
VIDEO_FPS=30
VIDEO_DURATION_PER_SLIDE_SECONDS=5
VIDEO_TRANSITION_SECONDS=0.5
VIDEO_DEFAULT_MOTION_PRESET=calm_zoom
VIDEO_RENDER_TIMEOUT_SECONDS=180
FFMPEG_PATH=ffmpeg
FFPROBE_PATH=ffprobe
AUDIO_MAX_FILE_SIZE_MB=50
AUDIO_ALLOWED_EXTENSIONS=mp3,m4a,wav,ogg,oga
AUDIO_NORMALIZE_ENABLED=true
AUDIO_DEFAULT_FIT_MODE=trim_or_pad
AUDIO_RENDER_TIMEOUT_SECONDS=180
AUDIO_OUTPUT_CODEC=aac
CONTENT_TIMEZONE=Asia/Jakarta
CONTENT_DEFAULT_CALENDAR_DAYS=7
CONTENT_ALLOW_SCHEDULE_REJECTED=false
CONTENT_REQUIRE_APPROVAL_BEFORE_SCHEDULE=true
SOURCE_STORAGE_DIR=./data/sources
SOURCE_REQUIRE_APPROVAL_FOR_GENERATION=false
SOURCE_BLOCK_RESTRICTED_GENERATION=true
TRANSCRIPT_MAX_CHARS_DIRECT=12000
TRANSCRIPT_SEGMENT_MIN_WORDS=300
TRANSCRIPT_SEGMENT_MAX_WORDS=800
SOURCE_DEFAULT_LANGUAGE=id
SOURCE_DEFAULT_PERMISSION_STATUS=unknown
CANDIDATE_BLOCK_RESTRICTED_SOURCE=true
CANDIDATE_ALLOW_UNKNOWN_PERMISSION=true
CANDIDATE_ALLOW_HIGH_RISK=false
CANDIDATE_DEFAULT_COUNT=10
CANDIDATE_MAX_TRANSCRIPT_CHARS=30000
CANDIDATE_MAX_SEGMENTS_PER_RUN=20
CANDIDATE_ALLOWED_TYPES=carousel,short_video,voiceover_reflection,quote_post,mixed
CONTENT_PACKAGE_DIR=./data/packages
CONTENT_PACKAGE_CREATE_ZIP=true
CONTENT_PACKAGE_REQUIRE_APPROVAL=true
CONTENT_PACKAGE_INCLUDE_METADATA=true
CONTENT_PACKAGE_INCLUDE_PLATFORM_CAPTIONS=true
CONTENT_PACKAGE_TIMEZONE=Asia/Jakarta
CONTENT_PACKAGE_MAX_ZIP_SIZE_MB=200
CONTENT_PACKAGE_ALLOW_STALE_MEDIA=false
```

The service logs whether an API key is configured, but never logs the key value.

## Run Locally

From this folder:

```sh
cp .env.example .env
set -a
. ./.env
set +a
python3 app.py
```

Health check:

```sh
curl http://127.0.0.1:8097/health
```

## PNG Renderer Setup

PNG rendering uses local Node.js dependencies and Playwright Chromium. Install them in this project folder, not globally:

```sh
npm install
npm run install:browsers
```

Milestone 1 content generation still works without Node dependencies. Only render endpoints require Playwright.

## MP4 Renderer Setup

Video rendering uses FFmpeg and expects existing PNG slides from the PNG render step.

Install FFmpeg on the host or set `FFMPEG_PATH` to the binary path:

```sh
ffmpeg -version
```

The service calls FFmpeg with argument arrays, validates input PNG paths, captures FFmpeg stderr for readable failures, and writes MP4 output under `CONTENT_EXPORT_DIR`.

## Voiceover Setup

Voiceover mixing uses FFmpeg and FFprobe. Put audio files under `CONTENT_AUDIO_DIR`; absolute paths outside that directory are rejected.

Supported extensions by default:

```text
mp3, m4a, wav, ogg, oga
```

The service validates file existence, extension, size, audio stream presence, and duration before mixing. It does not generate voices, clone voices, or imitate any real person.

## API

### Generate Carousel

```sh
curl -s http://127.0.0.1:8097/api/v1/content/carousel \
  -H 'Content-Type: application/json' \
  -d '{
    "topic": "kerja keras, rezeki halal, dan keberkahan",
    "niche": "annotasi_hikmah",
    "tone": "calm_reflective",
    "slideCount": 7,
    "platform": "instagram"
  }'
```

### Generate Hikmah Carousel

```sh
curl -s http://127.0.0.1:8097/api/v1/content/hikmah \
  -H 'Content-Type: application/json' \
  -d '{"topic":"sabar menghadapi tekanan kerja"}'
```

### Get Full Content

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34
```

### Get Caption

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/caption
```

### Get Voiceover

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/voiceover
```

Alias for Telegram-style command naming:

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/voiceover-script
```

### Generate Ideas

```sh
curl -s http://127.0.0.1:8097/api/v1/content/ideas \
  -H 'Content-Type: application/json' \
  -d '{"niche":"muslim worker"}'
```

### Render PNG Carousel

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/render/png \
  -H 'Content-Type: application/json' \
  -d '{
    "format": "instagram_carousel",
    "template": "annotasi_hikmah_dark",
    "forceRegenerate": false
  }'
```

### Get Latest PNG Render

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/render/png
```

### Get Render Metadata

```sh
curl -s http://127.0.0.1:8097/api/v1/render/rnd_20260704_ab12cd34
```

### Render MP4 Video

Run PNG render first, then:

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/render/video \
  -H 'Content-Type: application/json' \
  -d '{
    "format": "shorts_vertical",
    "template": "annotasi_hikmah_dark",
    "motionPreset": "calm_zoom",
    "durationPerSlideSeconds": 5,
    "transitionSeconds": 0.5,
    "forceRegenerate": false,
    "includeVoiceover": false
  }'
```

### Get Latest MP4 Render

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/render/video
```

### Get Video Render Metadata

```sh
curl -s http://127.0.0.1:8097/api/v1/video-render/vid_20260704_ab12cd34
```

### Prepare Voiceover Mixing

```sh
curl -s -X POST http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/audio/prepare
```

### Mix Voiceover Audio

The audio path must be inside `CONTENT_AUDIO_DIR`.

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/audio/mix \
  -H 'Content-Type: application/json' \
  -d '{
    "audioFilePath": "./data/audio/cnt_20260704_ab12cd34/voiceover.m4a",
    "audioMode": "voiceover",
    "normalizeAudio": true,
    "fitMode": "trim_or_pad",
    "forceRegenerate": false
  }'
```

### Get Latest Audio Render

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/audio/latest
```

### Get Audio Render Metadata

```sh
curl -s http://127.0.0.1:8097/api/v1/audio-render/aud_20260704_ab12cd34
```

### Review Content

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/review
```

### Approve or Reject

```sh
curl -s -X POST http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/approve \
  -H 'Content-Type: application/json' \
  -d '{"reviewedBy":"internal","notes":"checked"}'
```

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/reject \
  -H 'Content-Type: application/json' \
  -d '{"reason":"terlalu umum dan kurang kuat"}'
```

### Edit Content

```sh
curl -s -X PATCH http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/slides/3 \
  -H 'Content-Type: application/json' \
  -d '{"text":"Rezeki bukan hanya soal banyak, tapi juga soal halal, tenang, dan berkah."}'
```

```sh
curl -s -X PATCH http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/caption \
  -H 'Content-Type: application/json' \
  -d '{"caption":"Caption baru..."}'
```

```sh
curl -s -X PATCH http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/voiceover \
  -H 'Content-Type: application/json' \
  -d '{"voiceoverScript":"Script voiceover baru..."}'
```

### Status

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/status
```

Manual status update:

```sh
curl -s -X PATCH http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/status \
  -H 'Content-Type: application/json' \
  -d '{"status":"approved"}'
```

### Schedule

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/schedule \
  -H 'Content-Type: application/json' \
  -d '{"platform":"instagram","scheduledDate":"2026-07-05","scheduledTime":null,"timezone":"Asia/Jakarta"}'
```

Unschedule:

```sh
curl -s -X DELETE http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/schedule
```

### Calendar

```sh
curl -s 'http://127.0.0.1:8097/api/v1/calendar?from=2026-07-04&to=2026-07-11'
```

Shortcuts:

```sh
curl -s http://127.0.0.1:8097/api/v1/calendar/today
curl -s http://127.0.0.1:8097/api/v1/calendar/week
curl -s http://127.0.0.1:8097/api/v1/calendar/month
curl -s http://127.0.0.1:8097/api/v1/calendar/next
```

### Uploaded

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/uploaded \
  -H 'Content-Type: application/json' \
  -d '{"platform":"instagram","url":"https://instagram.com/example"}'
```

### Content List

```sh
curl -s http://127.0.0.1:8097/api/v1/content-list
curl -s 'http://127.0.0.1:8097/api/v1/content-list?status=needs_review'
```

### Source Manager

```sh
curl -s http://127.0.0.1:8097/api/v1/sources \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Kajian Rezeki Halal",
    "speakerName": "Ustadz Example",
    "sourceUrl": "https://youtube.com/example",
    "platform": "youtube",
    "sourceType": "youtube_video",
    "permissionStatus": "allowed_with_credit",
    "topic": "rezeki halal"
  }'
```

```sh
curl -s http://127.0.0.1:8097/api/v1/sources
curl -s http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34
curl -s http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/review
```

Approve, restrict, or set credit:

```sh
curl -s -X POST http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/approve
curl -s http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/restrict \
  -H 'Content-Type: application/json' \
  -d '{"reason":"permission unclear"}'
curl -s http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/credit \
  -H 'Content-Type: application/json' \
  -d '{"creditText":"Sumber: Kajian Rezeki Halal - Ustadz Example"}'
```

### Transcript Manager

```sh
curl -s http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/transcript \
  -H 'Content-Type: application/json' \
  -d '{"transcriptText":"Bismillah... hari ini kita membahas rezeki halal..."}'
```

```sh
curl -s http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/transcript
curl -s -X POST http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/segments/generate
curl -s http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/segments
curl -s http://127.0.0.1:8097/api/v1/segments/seg_20260704_ab12cd34
```

Update segment risk or notes:

```sh
curl -s -X PATCH http://127.0.0.1:8097/api/v1/segments/seg_20260704_ab12cd34 \
  -H 'Content-Type: application/json' \
  -d '{"riskLevel":"medium","contextNotes":"Jangan dipotong tanpa konteks tentang ikhtiar."}'
```

Generate source-based ideas or content:

```sh
curl -s -X POST http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/ideas
curl -s http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/generate-content \
  -H 'Content-Type: application/json' \
  -d '{"topic":"rezeki halal untuk pekerja"}'
curl -s -X POST http://127.0.0.1:8097/api/v1/segments/seg_20260704_ab12cd34/generate-content
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/source
```

### Highlight Candidates

Generate transcript candidates from a source:

```sh
curl -s http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/highlights \
  -H 'Content-Type: application/json' \
  -d '{
    "candidateCount": 10,
    "preferredTypes": ["carousel", "short_video", "voiceover_reflection", "quote_post"],
    "allowHighRisk": false
  }'
```

Generate candidates from one segment:

```sh
curl -s http://127.0.0.1:8097/api/v1/segments/seg_20260704_ab12cd34/highlights \
  -H 'Content-Type: application/json' \
  -d '{"candidateCount":5}'
```

List and inspect candidates:

```sh
curl -s http://127.0.0.1:8097/api/v1/sources/src_20260704_ab12cd34/candidates
curl -s http://127.0.0.1:8097/api/v1/candidates/cand_20260704_ab12cd34
curl -s 'http://127.0.0.1:8097/api/v1/candidate-list?status=suggested'
```

Approve, reject, or generate content:

```sh
curl -s -X POST http://127.0.0.1:8097/api/v1/candidates/cand_20260704_ab12cd34/approve
curl -s http://127.0.0.1:8097/api/v1/candidates/cand_20260704_ab12cd34/reject \
  -H 'Content-Type: application/json' \
  -d '{"reason":"terlalu berisiko salah konteks"}'
curl -s -X POST http://127.0.0.1:8097/api/v1/candidates/cand_20260704_ab12cd34/generate-content
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/candidate
```

### Content Packages

Check readiness:

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/ready-to-post
```

Generate a package:

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/package \
  -H 'Content-Type: application/json' \
  -d '{
    "createZip": true,
    "includeMetadata": true,
    "includePlatformCaptions": true,
    "forceRegenerate": false
  }'
```

Inspect package status and paths:

```sh
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/package/latest
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/packages
curl -s http://127.0.0.1:8097/api/v1/packages/pkg_20260704_ab12cd34
curl -s http://127.0.0.1:8097/api/v1/content/cnt_20260704_ab12cd34/posting-checklist
```

## Hermes Integration

Recommended Telegram command mapping:

| Telegram command | Hermes action |
| --- | --- |
| `/carousel <topic>` | `POST /api/v1/content/carousel` with `{ "topic": "<topic>" }` |
| `/hikmah <topic>` | `POST /api/v1/content/hikmah` with `{ "topic": "<topic>" }` |
| `/caption <content_id>` | `GET /api/v1/content/{content_id}/caption` |
| `/voiceover <content_id>` | `GET /api/v1/content/{content_id}/voiceover` |
| `/voiceover_script <content_id>` | `GET /api/v1/content/{content_id}/voiceover-script` |
| `/content <content_id>` | `GET /api/v1/content/{content_id}` |
| `/ideas <niche>` | `POST /api/v1/content/ideas` with `{ "niche": "<niche>" }` |
| `/render <content_id>` | `POST /api/v1/content/{content_id}/render/png` |
| `/render_list <content_id>` | `GET /api/v1/content/{content_id}/render/png` |
| `/render_status <render_id>` | `GET /api/v1/render/{render_id}` |
| `/video <content_id>` | `POST /api/v1/content/{content_id}/render/video` |
| `/video_list <content_id>` | `GET /api/v1/content/{content_id}/render/video` |
| `/video_status <video_render_id>` | `GET /api/v1/video-render/{video_render_id}` |
| `/mixvoice <content_id>` | `POST /api/v1/content/{content_id}/audio/prepare` |
| `/mixvoice_file <content_id> <audio_file_path>` | `POST /api/v1/content/{content_id}/audio/mix` |
| `/audio_list <content_id>` | `GET /api/v1/content/{content_id}/audio/latest` |
| `/audio_status <audio_render_id>` | `GET /api/v1/audio-render/{audio_render_id}` |
| `/review <content_id>` | `GET /api/v1/content/{content_id}/review` |
| `/approve <content_id>` | `POST /api/v1/content/{content_id}/approve` |
| `/reject <content_id> <reason>` | `POST /api/v1/content/{content_id}/reject` |
| `/status <content_id>` | `GET /api/v1/content/{content_id}/status` |
| `/edit_slide <content_id> <slide_number> <text>` | `PATCH /api/v1/content/{content_id}/slides/{slide_number}` |
| `/edit_caption <content_id> <text>` | `PATCH /api/v1/content/{content_id}/caption` |
| `/edit_voiceover <content_id> <text>` | `PATCH /api/v1/content/{content_id}/voiceover` |
| `/schedule <content_id> <YYYY-MM-DD> <platform>` | `POST /api/v1/content/{content_id}/schedule` |
| `/unschedule <content_id>` | `DELETE /api/v1/content/{content_id}/schedule` |
| `/calendar today` | `GET /api/v1/calendar/today` |
| `/calendar week` | `GET /api/v1/calendar/week` |
| `/calendar month` | `GET /api/v1/calendar/month` |
| `/today` | `GET /api/v1/calendar/today` |
| `/next` | `GET /api/v1/calendar/next` |
| `/uploaded <content_id> <platform> <url_optional>` | `POST /api/v1/content/{content_id}/uploaded` |
| `/content_list <status_optional>` | `GET /api/v1/content-list?status=<status>` |
| `/source_add ...` | `POST /api/v1/sources` |
| `/source_list` | `GET /api/v1/sources` |
| `/source <source_id>` | `GET /api/v1/sources/{source_id}` |
| `/source_review <source_id>` | `GET /api/v1/sources/{source_id}/review` |
| `/source_approve <source_id>` | `POST /api/v1/sources/{source_id}/approve` |
| `/source_restrict <source_id> <reason>` | `POST /api/v1/sources/{source_id}/restrict` |
| `/source_credit <source_id> <credit_text>` | `POST /api/v1/sources/{source_id}/credit` |
| `/transcript_add <source_id> <text>` | `POST /api/v1/sources/{source_id}/transcript` |
| `/transcript <source_id>` | `GET /api/v1/sources/{source_id}/transcript` |
| `/segments_generate <source_id>` | `POST /api/v1/sources/{source_id}/segments/generate` |
| `/segments <source_id>` | `GET /api/v1/sources/{source_id}/segments` |
| `/segment <segment_id>` | `GET /api/v1/segments/{segment_id}` |
| `/segment_risk <segment_id> <risk>` | `PATCH /api/v1/segments/{segment_id}` |
| `/segment_notes <segment_id> <notes>` | `PATCH /api/v1/segments/{segment_id}` |
| `/ideas_from_source <source_id>` | `POST /api/v1/sources/{source_id}/ideas` |
| `/from_source <source_id> <topic_optional>` | `POST /api/v1/sources/{source_id}/generate-content` |
| `/from_segment <segment_id>` | `POST /api/v1/segments/{segment_id}/generate-content` |
| `/source_for_content <content_id>` | `GET /api/v1/content/{content_id}/source` |
| `/highlights_from_source <source_id>` | `POST /api/v1/sources/{source_id}/highlights` |
| `/highlights_from_segment <segment_id>` | `POST /api/v1/segments/{segment_id}/highlights` |
| `/candidates <source_id>` | `GET /api/v1/sources/{source_id}/candidates` |
| `/candidate <candidate_id>` | `GET /api/v1/candidates/{candidate_id}` |
| `/candidate_approve <candidate_id>` | `POST /api/v1/candidates/{candidate_id}/approve` |
| `/candidate_reject <candidate_id> <reason>` | `POST /api/v1/candidates/{candidate_id}/reject` |
| `/candidate_status <candidate_id>` | `GET /api/v1/candidates/{candidate_id}` |
| `/generate_from_candidate <candidate_id>` | `POST /api/v1/candidates/{candidate_id}/generate-content` |
| `/candidate_for_content <content_id>` | `GET /api/v1/content/{content_id}/candidate` |
| `/candidate_list <status_optional>` | `GET /api/v1/candidate-list?status=<status>` |
| `/highlights_help` | Show highlight/candidate help text in Hermes |
| `/package <content_id>` | `POST /api/v1/content/{content_id}/package` |
| `/package_status <content_id>` | `GET /api/v1/content/{content_id}/package/latest` |
| `/package_list <content_id>` | `GET /api/v1/content/{content_id}/packages` |
| `/package_path <package_id>` | `GET /api/v1/packages/{package_id}` |
| `/posting_checklist <content_id>` | `GET /api/v1/content/{content_id}/posting-checklist` |
| `/ready_to_post <content_id>` | `GET /api/v1/content/{content_id}/ready-to-post` |
| `/help` | Show the command list above |

Hermes should send every string in the response `telegramMessages` array as a separate Telegram message, in order. For `/render`, if Hermes supports sending local files or private download links, it can also send each `files[].path` PNG after the text response. For `/video`, Hermes can send `file.path` as a video if the bot adapter and Telegram file size limits allow it; otherwise return the path or private download link.

Pseudo-code:

```js
const response = await fetch(`${ANNOTASI_CONTENT_URL}/api/v1/content/hikmah`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ topic })
});

const payload = await response.json();
if (!response.ok) {
  await telegram.sendMessage(chatId, payload.error?.message || "Gagal membuat konten.");
  return;
}

for (const message of payload.telegramMessages) {
  await telegram.sendMessage(chatId, message);
}
```

Render pseudo-code:

```js
const response = await fetch(`${ANNOTASI_CONTENT_URL}/api/v1/content/${contentId}/render/png`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    format: "instagram_carousel",
    template: "annotasi_hikmah_dark",
    forceRegenerate: false
  })
});

const payload = await response.json();
if (!response.ok) {
  await telegram.sendMessage(chatId, payload.error?.message || "Gagal render PNG.");
  return;
}

for (const message of payload.telegramMessages) {
  await telegram.sendMessage(chatId, message);
}

for (const file of payload.files || []) {
  // Optional: send file.path when your Telegram adapter supports local file upload.
}
```

Video pseudo-code:

```js
const response = await fetch(`${ANNOTASI_CONTENT_URL}/api/v1/content/${contentId}/render/video`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    format: "shorts_vertical",
    template: "annotasi_hikmah_dark",
    motionPreset: "calm_zoom",
    durationPerSlideSeconds: 5,
    transitionSeconds: 0.5,
    forceRegenerate: false,
    includeVoiceover: false
  })
});

const payload = await response.json();
if (!response.ok) {
  await telegram.sendMessage(chatId, payload.error?.message || "Gagal render video.");
  return;
}

for (const message of payload.telegramMessages) {
  await telegram.sendMessage(chatId, message);
}

// Optional: send payload.file.path when Telegram file upload is supported.
```

Voiceover pseudo-code:

```js
const response = await fetch(`${ANNOTASI_CONTENT_URL}/api/v1/content/${contentId}/audio/mix`, {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    audioFilePath,
    audioMode: "voiceover",
    normalizeAudio: true,
    fitMode: "trim_or_pad",
    forceRegenerate: false
  })
});

const payload = await response.json();
if (!response.ok) {
  await telegram.sendMessage(chatId, payload.error?.message || "Gagal mix voiceover.");
  return;
}

for (const message of payload.telegramMessages) {
  await telegram.sendMessage(chatId, message);
}

// Optional: send payload.outputVideo.path when Telegram video upload is supported.
```

## Example Telegram Output

```text
Annotasi Hikmah Carousel

Title:
Kerja Keras dan Rezeki yang Berkah

Slide 1:
Kerja keras boleh. Tapi jangan sampai kehilangan berkah.

Slide 2:
Kadang kita mengejar rezeki, tapi lupa menjaga sumber keberkahannya.

Caption:
...

Voiceover:
Use /voiceover cnt_20260704_ab12cd34

Content ID:
cnt_20260704_ab12cd34

Reminder:
Review kembali sebelum upload agar tidak salah konteks.
```

## Example Voiceover Output

```text
Final Video dengan Voiceover

Content ID:
cnt_20260704_ab12cd34

Audio Render ID:
aud_20260704_ef56ab78

Source Video Render ID:
vid_20260704_1122aabb

Duration:
35.0 seconds

Output:
/absolute/path/data/exports/cnt_20260704_ab12cd34/aud_20260704_ef56ab78/final-voiceover.mp4

Reminder:
Review kembali sebelum upload agar tidak salah konteks.
```

## Example Video Output

```text
Annotasi Motion Video Rendered

Content ID:
cnt_20260704_ab12cd34

Video Render ID:
vid_20260704_ef56ab78

Format:
Vertical MP4 1080x1920

Slides:
7

Duration:
35.0 seconds

Output:
/absolute/path/data/exports/cnt_20260704_ab12cd34/vid_20260704_ef56ab78/final.mp4

Reminder:
Review kembali sebelum upload agar tidak salah konteks.
```

## Example Render Output

```text
Annotasi Carousel Rendered

Content ID:
cnt_20260704_ab12cd34

Render ID:
rnd_20260704_ef56ab78

Format:
instagram_carousel 1080x1350

Slides:
7 PNG files generated

Output:
- slide-01.png: /absolute/path/data/exports/cnt_20260704_ab12cd34/rnd_20260704_ef56ab78/slide-01.png
- slide-02.png: /absolute/path/data/exports/cnt_20260704_ab12cd34/rnd_20260704_ef56ab78/slide-02.png

Reminder:
Review kembali sebelum upload agar tidak salah konteks.
```

## Output Directory

Default local structure:

```text
./data/exports/{content_id}/{render_id}/slide-01.png
./data/exports/{content_id}/{render_id}/slide-02.png
./data/exports/{content_id}/{render_id}/slide-03.png
./data/exports/{content_id}/{video_render_id}/final.mp4
./data/exports/{content_id}/{video_render_id}/render-metadata.json
./data/audio/{content_id}/voiceover-original.m4a
./data/exports/{content_id}/{audio_render_id}/voiceover-normalized.wav
./data/exports/{content_id}/{audio_render_id}/final-voiceover.mp4
./data/exports/{content_id}/{audio_render_id}/audio-render-metadata.json
./data/sources/{source_id}.json
```

The base directory is configured with `CONTENT_EXPORT_DIR`.
Source records are stored under `SOURCE_STORAGE_DIR`.

## Workflow Data

Workflow metadata is stored in each content JSON record:

- `workflow.status`
- `workflow.reviewStatus`
- `workflow.reviewNotes`
- `workflow.rejectionReason`
- `workflow.approvedAt`
- `workflow.approvedBy`
- `workflow.scheduledDate`
- `workflow.scheduledTime`
- `workflow.scheduledPlatform`
- `workflow.scheduledTimezone`
- `workflow.uploadedAt`
- `workflow.uploadedPlatform`
- `workflow.uploadedUrl`
- `workflow.renderStale`
- `editHistory`

Supported statuses:

```text
idea, generated, needs_review, reviewed, edit_requested, approved,
png_rendered, video_rendered, voiceover_ready, scheduled, uploaded,
archived, rejected
```

Supported platforms:

```text
instagram, tiktok, youtube_shorts, facebook_reels, linkedin, manual
```

Render staleness rules:

- editing a slide marks PNG, video, and audio renders stale.
- editing a caption does not mark media stale.
- editing a voiceover script marks audio stale.
- successful PNG, video, or audio rendering clears its corresponding stale flag.

## Source Data

Source records are stored as JSON files with:

- `sourceId`
- `title`
- `speakerName`
- `sourceType`
- `platform`
- `sourceUrl`
- `localFilePath`
- `permissionStatus`
- `permissionNotes`
- `creditText`
- `topic`
- `category`
- `language`
- `durationSeconds`
- `sourceStatus`
- `contextNotes`
- `transcript`
- `generatedContent`

Supported source types:

```text
youtube_video, instagram_video, tiktok_video, podcast, webinar,
user_uploaded_video, manual_note, article, book, other
```

Supported source platforms:

```text
youtube, instagram, tiktok, spotify, website, local_file, manual, other
```

Supported permission statuses:

```text
unknown, allowed_for_dakwah, allowed_with_credit, own_content,
needs_permission, restricted, rejected
```

Permission rules:

- restricted or rejected sources are blocked from generation by default.
- unapproved sources are allowed for internal MVP generation when `SOURCE_REQUIRE_APPROVAL_FOR_GENERATION=false`, but responses include warnings.
- `allowed_for_dakwah` does not mean automatically safe for monetization.
- source credit is carried into generated content as `sourceCreditSuggestion` and `sourceLink.sourceCreditUsed`.

## Transcript Data

Each source can have one transcript object with:

- `transcriptId`
- `sourceId`
- `transcriptText`
- `language`
- `transcriptStatus`
- `segments`

Segments include:

- `segmentId`
- `transcriptId`
- `sourceId`
- `startTimeSeconds`
- `endTimeSeconds`
- `text`
- `topic`
- `contextNotes`
- `riskLevel`

Segmentation rules:

- timestamped lines such as `[00:01:20] text` keep their timestamp.
- ranges such as `00:01:20 - 00:02:10 text` keep start and end times.
- if no timestamps exist, segments are split by paragraphs/logical chunks.
- exact timestamps are not invented.
- untimestamped segments receive context note: `Timestamp tidak tersedia. Segment dibuat berdasarkan struktur teks.`
- risk level is a heuristic default and should be manually reviewed.

## Candidate Data

Clip candidates are stored as planning records inside the source JSON under `candidates`; this service does not create actual video clips. Content generated from a candidate receives `candidateLink`, and the candidate receives a `contentLinks` entry.

Candidate fields:

- `candidateId`
- `sourceId`
- `transcriptId`
- `segmentId`
- `candidateType`
- `title`
- `hook`
- `angle`
- `summary`
- `suggestedFormat`
- `suggestedDurationSeconds`
- `riskLevel`
- `needsContext`
- `contextWarning`
- `sourceCreditSuggestion`
- `candidateStatus`
- `aiReasoningSummary`
- `contentLinks`
- `createdAt`
- `updatedAt`

Candidate risk handling:

- restricted or rejected sources are blocked by default through `CANDIDATE_BLOCK_RESTRICTED_SOURCE=true`.
- unknown permission sources are allowed by default for MVP analysis through `CANDIDATE_ALLOW_UNKNOWN_PERMISSION=true`, but responses include warnings.
- high-risk candidates are filtered or blocked unless `CANDIDATE_ALLOW_HIGH_RISK=true` or the request explicitly allows high risk.
- `aiReasoningSummary` must be a short, user-safe rationale only; hidden chain-of-thought is not requested or stored.

## Content Package Data

Content package metadata is stored inside the content JSON record under `packages`, with `latestPackage` pointing to the newest package. Package files are written under:

```text
./data/packages/{content_id}/{package_id}/
```

Package folder structure:

```text
01-carousel/
02-video/
03-copy/
04-review/
05-metadata/
README.md
```

Generated copy files:

- `03-copy/title.txt`
- `03-copy/caption-instagram.txt`
- `03-copy/caption-tiktok.txt`
- `03-copy/caption-youtube-shorts.txt`
- `03-copy/hashtags.txt`
- `03-copy/voiceover-script.txt`
- `03-copy/source-credit.txt`

Generated review files:

- `04-review/posting-checklist.md`
- `04-review/dakwah-safety-checklist.md`
- `04-review/source-context.md`

Generated metadata files:

- `05-metadata/manifest.json`
- `05-metadata/content.json`
- `05-metadata/source.json` when linked source exists
- `05-metadata/candidate.json` when linked candidate exists
- `05-metadata/render-metadata.json`

Package metadata fields include `packageId`, `contentId`, `status`, `packageDir`, `zipPath`, included file counts, voiceover/source/candidate/checklist flags, warnings, timestamps, and error message.

Package statuses:

```text
not_started, packaging, completed, failed, stale
```

Readiness rules:

- content must exist.
- rejected content is blocked.
- title, caption, hashtags, posting checklist, and manifest must be available.
- when `CONTENT_PACKAGE_REQUIRE_APPROVAL=true`, content must be approved before packaging.
- missing PNG, video, source credit, or voiceover video produce readiness warnings and package warnings.

Staleness rules:

- editing slides, caption, or voiceover marks existing completed packages as `stale`.
- stale PNG/video/audio render flags are reported in readiness and package warnings.
- when `CONTENT_PACKAGE_ALLOW_STALE_MEDIA=false`, stale media blocks package creation until `/render`, `/video`, or `/mixvoice` is rerun.

ZIP behavior:

- when `CONTENT_PACKAGE_CREATE_ZIP=true`, the package folder is zipped as `{content_id}-{slugified-title}-{package_id}.zip`.
- ZIP creation failure does not fail a complete package folder; it is recorded as a warning.
- ZIPs larger than `CONTENT_PACKAGE_MAX_ZIP_SIZE_MB` are kept but reported as too large for Telegram-style sending.

## Template

Current template:

- `annotasi_hikmah_dark`
- 1080x1350 by default
- dark elegant background
- cream/gold accent
- top brand label: `Annotasi Hikmah`
- footer reminder: `Review kembali sebelum upload agar tidak salah konteks.`

Rendering is deterministic and does not call AI. The renderer only uses the stored slide text and metadata.

## Video Rendering

Current video renderer:

- `shorts_vertical`
- 1080x1920 by default
- 30 FPS by default
- 5 seconds per slide by default
- H.264 MP4 using `libx264`
- `yuv420p` pixel format
- dark 9:16 background
- centered original PNG slide
- supported motion presets: `calm_zoom`, `static`
- no AI calls
- no voice cloning
- voiceover audio mixing is handled by the Milestone 4 flow below

## Voiceover Mixing

Current audio mixer:

- voiceover audio only
- user-provided local file only
- audio must be inside `CONTENT_AUDIO_DIR`
- optional loudness normalization with FFmpeg `loudnorm`
- AAC output audio
- video stream copied from the source MP4
- source video duration is preserved
- if audio is longer, it is trimmed to video duration
- if audio is shorter, it ends naturally; the video continues
- no background music
- no AI voice generation
- no voice cloning or imitation

## Error Handling

The service handles:

- Empty topic or niche.
- Missing `AI_API_KEY`.
- AI endpoint unavailable or timed out.
- Invalid AI JSON.
- JSON validation failure.
- Storage read/write errors.
- Telegram message splitting through `telegramMessages`.
- Content ID not found for rendering.
- Render dependency unavailable.
- Template not found.
- Slide text too long to render without overflow.
- Output directory not writable.
- Duplicate render requests return existing completed files unless `forceRegenerate` is `true`.
- PNG render missing for video generation.
- PNG files missing.
- Unsupported motion preset.
- FFmpeg missing or unavailable.
- FFmpeg segment or concat failure.
- Generated MP4 missing or zero-byte.
- Duplicate video render requests return existing completed files unless `forceRegenerate` is `true`.
- Audio file missing.
- Audio path outside `CONTENT_AUDIO_DIR`.
- Unsupported audio format.
- Audio file too large.
- Invalid audio stream.
- FFprobe unavailable or duration detection failure.
- Voiceover mixing failure.
- Generated voiceover MP4 missing or zero-byte.
- Duplicate audio mix requests return existing completed files unless `forceRegenerate` is `true`.
- Slide number not found.
- Empty edit text.
- Invalid workflow status.
- Invalid platform.
- Invalid schedule date.
- Scheduling rejected content.
- Scheduling before approval when `CONTENT_REQUIRE_APPROVAL_BEFORE_SCHEDULE=true`.
- Duplicate schedule.
- Empty calendar results.
- Invalid source ID or segment ID.
- Source not found.
- Transcript not found.
- Transcript too long for direct input.
- Invalid source type, platform, permission status, or risk level.
- Restricted source generation blocked.
- Source-based generation without transcript.
- AI source ideas/content JSON validation failure.
- Candidate not found.
- Candidate must be approved before content generation.
- Candidate already converted to content.
- Duplicate candidate title detected.
- Restricted or rejected source blocked for highlight generation.
- Source permission unknown when unknown permission analysis is disabled.
- High-risk candidate blocked by configuration.
- AI returned no candidates.
- Long transcript analysis is truncated to `CANDIDATE_MAX_TRANSCRIPT_CHARS`.
- Package ID not found.
- Content not approved when `CONTENT_PACKAGE_REQUIRE_APPROVAL=true`.
- Content rejected before packaging.
- Missing caption or hashtags before packaging.
- Stale media blocked by `CONTENT_PACKAGE_ALLOW_STALE_MEDIA=false`.
- Missing PNG/MP4/voiceover assets reported as package warnings.
- Package directory not writable.
- Package file copy failure.
- Manifest or checklist write failure.
- ZIP creation failure recorded as a warning when folder package is complete.
- Duplicate package requests return the latest completed package unless `forceRegenerate=true`.

## Known Limitations

- No direct Telegram bot code is included because the Hermes repository was not available in the workspace.
- Storage is local JSON files, suitable for Milestone 1 but not multi-node deployments.
- PNG rendering requires local Playwright dependencies and Chromium.
- Telegram file upload is not included here because the Hermes adapter was not available.
- MP4 rendering requires FFmpeg on the host.
- Voiceover mixing requires FFmpeg and FFprobe on the host.
- Telegram voice note download/session handling is not implemented in this service because Hermes code is not available; use `/mixvoice_file` or wire Hermes uploads to `/audio/mix`.
- Background music is intentionally reserved for a future milestone.
- Telegram video upload is not included here because the Hermes adapter was not available.
- Auto-posting to social platforms is not implemented.
- Calendar is a planning layer only; it does not trigger scheduled jobs.
- No public dashboard is included.
- Transcript paste sessions are not implemented in this service; use direct `/transcript_add` or wire Hermes state to the transcript endpoint.
- Source segmentation is heuristic and should be reviewed manually.
- Source-based idea/content generation uses transcript excerpts, not full long-document retrieval.
- Highlight candidates are planning records only; this milestone does not create actual video clips.
- YouTube/Instagram/TikTok download is not implemented.
- Long transcript analysis is capped by `CANDIDATE_MAX_TRANSCRIPT_CHARS` and `CANDIDATE_MAX_SEGMENTS_PER_RUN`.
- AI risk level is a suggestion only; manual source/context review remains required before publishing.
- Package export does not auto-post to any social platform.
- Package ZIP is a local file only; Hermes must implement file sending if desired.
- Platform caption variants are deterministic and do not call AI.
- Package export copies existing rendered media; it does not render missing PNG/MP4 files automatically.

## Manual Test Guide

Do not run this against production services until the service is configured safely.

1. Generate content:

```text
/hikmah kerja keras dan rezeki halal
```

2. Copy the returned content ID.

3. Render PNG:

```text
/render <content_id>
```

4. Verify:

- 7 PNG files generated.
- each image is 1080x1350.
- text is readable.
- `Annotasi Hikmah` branding is visible.
- the footer reminder exists.
- no text overflow is visible.

5. Retrieve caption:

```text
/caption <content_id>
```

6. Confirm existing Milestone 1 commands still work.
- The service trusts Hermes for authentication and should be bound to localhost or protected by your existing reverse proxy.

## Manual Video Test Guide

1. Generate content:

```text
/hikmah kerja keras dan rezeki halal
```

2. Copy the returned content ID.

3. Render PNG carousel:

```text
/render <content_id>
```

4. Render MP4 video:

```text
/video <content_id>
```

5. Verify:

- MP4 file generated.
- resolution is 1080x1920.
- video is playable.
- all slides appear in order.
- each slide is readable.
- video duration roughly equals slide count x duration per slide.
- `Annotasi Hikmah` branding is visible.
- no visual overflow or cropping issue.

6. Confirm existing commands still work:

```text
/content <content_id>
/caption <content_id>
/voiceover <content_id>
```

## Manual Voiceover Test Guide

1. Generate content:

```text
/hikmah kerja keras dan rezeki halal
```

2. Retrieve voiceover script:

```text
/voiceover <content_id>
```

or:

```text
/voiceover_script <content_id>
```

3. Record your own voice reading the script.

4. Put the audio file under:

```text
./data/audio/{content_id}/voiceover.m4a
```

5. Render PNG and MP4:

```text
/render <content_id>
/video <content_id>
```

6. Mix voiceover:

```text
/mixvoice_file <content_id> ./data/audio/{content_id}/voiceover.m4a
```

7. Verify:

- `final-voiceover.mp4` is generated.
- video is playable.
- resolution remains 1080x1920.
- voiceover is audible.
- video duration remains close to the source video duration.
- no voice cloning or impersonation was used.
- existing commands still work.

## Manual Workflow Test Guide

1. Generate content:

```text
/hikmah kerja keras dan rezeki halal
```

2. Review content:

```text
/review <content_id>
```

3. Edit one slide:

```text
/edit_slide <content_id> 3 Rezeki bukan hanya soal banyak, tapi juga soal halal, tenang, dan berkah.
```

4. Check status:

```text
/status <content_id>
```

Expected: status should require review again, and media render flags should be stale or not started.

5. Approve content:

```text
/approve <content_id>
```

6. Render assets:

```text
/render <content_id>
/video <content_id>
```

7. Schedule content:

```text
/schedule <content_id> 2026-07-05 instagram
```

8. View calendar:

```text
/calendar week
```

9. Mark uploaded:

```text
/uploaded <content_id> instagram https://instagram.com/example
```

10. List uploaded:

```text
/content_list uploaded
```

## Manual Source Test Guide

1. Add source:

```text
/source_add Kajian Rezeki Halal | Ustadz Example | https://youtube.com/example | youtube | allowed_with_credit
```

2. Check source:

```text
/source <source_id>
```

3. Add credit:

```text
/source_credit <source_id> Sumber: Kajian Rezeki Halal - Ustadz Example
```

4. Review and approve source:

```text
/source_review <source_id>
/source_approve <source_id>
```

5. Add transcript:

```text
/transcript_add <source_id> <paste transcript text>
```

6. Generate and inspect segments:

```text
/segments_generate <source_id>
/segments <source_id>
/segment <segment_id>
```

7. Add segment context:

```text
/segment_notes <segment_id> Jangan dipotong tanpa konteks tentang ikhtiar sebelum tawakal.
```

8. Generate ideas and content:

```text
/ideas_from_source <source_id>
/from_source <source_id> rezeki halal untuk pekerja
```

9. Check linked source and review:

```text
/source_for_content <content_id>
/review <content_id>
```

Expected: source, credit, permission, segment, and risk context appear in the review output.

## Manual Candidate Test Guide

1. Generate highlights from a source:

```text
/highlights_from_source <source_id>
```

2. Generate highlights from one transcript segment:

```text
/highlights_from_segment <segment_id>
```

3. List and inspect candidates:

```text
/candidates <source_id>
/candidate <candidate_id>
/candidate_list suggested
```

4. Approve or reject a candidate:

```text
/candidate_approve <candidate_id>
/candidate_reject <candidate_id> terlalu berisiko salah konteks
```

5. Generate review-ready content from an approved candidate:

```text
/generate_from_candidate <candidate_id>
```

6. Check the candidate link from generated content:

```text
/candidate_for_content <content_id>
/review <content_id>
```

Expected: candidate ID, source, risk, context warning, source credit, and candidate checklist appear in review output. The generated content remains `needs_review`.

## Manual Package Test Guide

1. Complete the source-to-content flow:

```text
/source_add Kajian Rezeki Halal | Ustadz Example | https://youtube.com/example | youtube | allowed_with_credit
/source_credit <source_id> Sumber: Kajian Rezeki Halal - Ustadz Example
/source_approve <source_id>
/transcript_add <source_id> <paste transcript text>
/segments_generate <source_id>
/highlights_from_source <source_id>
/candidate_approve <candidate_id>
/generate_from_candidate <candidate_id>
```

2. Review and approve generated content:

```text
/review <content_id>
/approve <content_id>
```

3. Render media:

```text
/render <content_id>
/video <content_id>
/voiceover <content_id>
/mixvoice_file <content_id> /path/to/voiceover.m4a
```

4. Schedule and check readiness:

```text
/schedule <content_id> 2026-07-05 instagram
/ready_to_post <content_id>
```

5. Create and inspect package:

```text
/package <content_id>
/package_status <content_id>
/package_list <content_id>
/package_path <package_id>
/posting_checklist <content_id>
```

Expected package folders:

```text
01-carousel/
02-video/
03-copy/
04-review/
05-metadata/
README.md
```

6. After manual upload:

```text
/uploaded <content_id> instagram https://instagram.com/example
```

7. Confirm existing commands still work:

```text
/status <content_id>
/calendar week
/content_list packaged
/content_list uploaded
/source_for_content <content_id>
/candidate_for_content <content_id>
```

## MVP Complete

Milestone 8 completes the internal MVP of Annotasi Carousel Studio.

The MVP now supports AI content generation, PNG carousel rendering, MP4 vertical rendering, voiceover mixing, review/edit workflow, content calendar, source/transcript management, transcript highlight candidates, final package export, and manual posting checklist.

Recommended next step: use the tool for 30 days, produce 30 to 60 Annotasi Hikmah contents, publish manually, track performance, and identify workflow pain points before adding new major features.

Post-MVP ideas can wait until real usage data exists: performance tracker, simple web dashboard, template manager, topic bank, background music, subtitle overlay, local clip cutter, or analytics loop.


## Suggested Commit Message

```text
feat(content): add package export and posting checklist
```
