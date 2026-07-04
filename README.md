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
AI_TIMEOUT_SECONDS=90
TELEGRAM_MESSAGE_LIMIT=3900
LOG_LEVEL=INFO
CAROUSEL_DEFAULT_TEMPLATE=annotasi_hikmah_dark
CAROUSEL_WIDTH=1080
CAROUSEL_HEIGHT=1350
CAROUSEL_RENDER_TIMEOUT_SECONDS=60
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

## Hermes Integration

Recommended Telegram command mapping:

| Telegram command | Hermes action |
| --- | --- |
| `/carousel <topic>` | `POST /api/v1/content/carousel` with `{ "topic": "<topic>" }` |
| `/hikmah <topic>` | `POST /api/v1/content/hikmah` with `{ "topic": "<topic>" }` |
| `/caption <content_id>` | `GET /api/v1/content/{content_id}/caption` |
| `/voiceover <content_id>` | `GET /api/v1/content/{content_id}/voiceover` |
| `/content <content_id>` | `GET /api/v1/content/{content_id}` |
| `/ideas <niche>` | `POST /api/v1/content/ideas` with `{ "niche": "<niche>" }` |
| `/render <content_id>` | `POST /api/v1/content/{content_id}/render/png` |
| `/render_list <content_id>` | `GET /api/v1/content/{content_id}/render/png` |
| `/render_status <render_id>` | `GET /api/v1/render/{render_id}` |
| `/help` | Show the command list above |

Hermes should send every string in the response `telegramMessages` array as a separate Telegram message, in order. For `/render`, if Hermes supports sending local files or private download links, it can also send each `files[].path` PNG after the text response.

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
```

The base directory is configured with `CONTENT_EXPORT_DIR`.

## Template

Current template:

- `annotasi_hikmah_dark`
- 1080x1350 by default
- dark elegant background
- cream/gold accent
- top brand label: `Annotasi Hikmah`
- footer reminder: `Review kembali sebelum upload agar tidak salah konteks.`

Rendering is deterministic and does not call AI. The renderer only uses the stored slide text and metadata.

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

## Known Limitations

- No direct Telegram bot code is included because the Hermes repository was not available in the workspace.
- Storage is local JSON files, suitable for Milestone 1 but not multi-node deployments.
- PNG rendering requires local Playwright dependencies and Chromium.
- Telegram file upload is not included here because the Hermes adapter was not available.
- MP4 export is intentionally not implemented in this milestone.

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

## Suggested Next Milestone

Add MP4 motion video rendering from PNG slides for Shorts/Reels/TikTok, with simple fade or zoom transitions and optional voiceover audio.

## Suggested Commit Message

```text
feat(content): add PNG carousel renderer
```
