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

## Files

- `app.py` - stdlib HTTP service, AI client, validation, storage, and Telegram formatting.
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
AI_TIMEOUT_SECONDS=90
TELEGRAM_MESSAGE_LIMIT=3900
LOG_LEVEL=INFO
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
| `/help` | Show the command list above |

Hermes should send every string in the response `telegramMessages` array as a separate Telegram message, in order.

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

## Error Handling

The service handles:

- Empty topic or niche.
- Missing `AI_API_KEY`.
- AI endpoint unavailable or timed out.
- Invalid AI JSON.
- JSON validation failure.
- Storage read/write errors.
- Telegram message splitting through `telegramMessages`.

## Known Limitations

- No direct Telegram bot code is included because the Hermes repository was not available in the workspace.
- Storage is local JSON files, suitable for Milestone 1 but not multi-node deployments.
- PNG and MP4 export are intentionally not implemented in this milestone.
- The service trusts Hermes for authentication and should be bound to localhost or protected by your existing reverse proxy.

## Suggested Next Milestone

Add PNG carousel rendering using HTML/CSS templates and Playwright screenshots at 1080x1350, then return downloadable files or paths through Telegram.

## Suggested Commit Message

```text
feat(content): add AI carousel generation workflow
```
