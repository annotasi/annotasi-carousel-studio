#!/usr/bin/env python3
"""Annotasi Carousel Studio content engine.

Milestone 1 standalone HTTP service. It intentionally uses only the Python
standard library so it can be dropped onto a VPS without a dependency install.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import sys
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest


AI_BASE_URL = os.getenv("AI_BASE_URL", "http://127.0.0.1:20128/v1")
AI_MODEL = os.getenv("AI_MODEL", "annotasi-coding")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "90"))
HOST = os.getenv("ANNOTASI_HOST", "127.0.0.1")
PORT = int(os.getenv("ANNOTASI_PORT", "8097"))
STORAGE_DIR = Path(os.getenv("CONTENT_STORAGE_DIR", "./data/content"))
TELEGRAM_LIMIT = int(os.getenv("TELEGRAM_MESSAGE_LIMIT", "3900"))

LOGGER = logging.getLogger("annotasi_carousel_studio")


class AppError(Exception):
    def __init__(self, status: HTTPStatus, code: str, message: str):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ValidationError(AppError):
    def __init__(self, message: str):
        super().__init__(HTTPStatus.BAD_GATEWAY, "ai_validation_failed", message)


def configure_logging() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def content_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"cnt_{stamp}_{secrets.token_hex(4)}"


def word_count(text: str) -> int:
    return len(re.findall(r"\S+", text.strip()))


def parse_int(
    value: Any,
    default: int,
    field_name: str,
    status: HTTPStatus = HTTPStatus.BAD_REQUEST,
    code: str = "invalid_number",
) -> int:
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise AppError(status, code, f"{field_name} must be a number.") from exc


def strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped)
    return stripped.strip()


def json_response(handler: BaseHTTPRequestHandler, status: HTTPStatus, body: dict[str, Any]) -> None:
    payload = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
    handler.send_response(status.value)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.end_headers()
    handler.wfile.write(payload)


def read_json_body(handler: BaseHTTPRequestHandler) -> dict[str, Any]:
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0:
        return {}
    try:
        raw = handler.rfile.read(length).decode("utf-8")
        body = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_json", "Request body must be valid JSON.") from exc
    if not isinstance(body, dict):
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_json", "Request body must be a JSON object.")
    return body


class JsonContentStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, item_id: str) -> Path:
        if not re.fullmatch(r"cnt_\d{8}_[a-f0-9]{8}", item_id):
            raise AppError(HTTPStatus.BAD_REQUEST, "invalid_content_id", "Content ID format is invalid.")
        return self.root / f"{item_id}.json"

    def save(self, record: dict[str, Any]) -> None:
        path = self.path_for(record["id"])
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_failure", "Could not save content.") from exc
        LOGGER.info("content_saved content_id=%s", record["id"])

    def get(self, item_id: str) -> dict[str, Any]:
        path = self.path_for(item_id)
        if not path.exists():
            raise AppError(HTTPStatus.NOT_FOUND, "content_not_found", "Content package was not found.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_failure", "Could not read content.") from exc
        except json.JSONDecodeError as exc:
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_corrupt", "Stored content is invalid.") from exc
        if not isinstance(data, dict):
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_corrupt", "Stored content is invalid.")
        return data


STORE = JsonContentStore(STORAGE_DIR)


def system_prompt() -> str:
    return """You create internal content packages for Annotasi Carousel Studio.

Language and style:
- Use Bahasa Indonesia.
- Calm, reflective, practical, and not clickbait.
- Suitable for Muslim workers and professionals.
- Keep carousel slide text short and readable.

Dakwah safety:
- Do not invent Quran verses.
- Do not invent hadith.
- Do not attribute statements to UAS, UAH, or any ustadz unless a source is provided.
- Do not imitate or clone any ustadz voice.
- Do not produce controversial fatwa-style answers.
- Use phrases like pengingat, hikmah, renungan, or catatan.
- If no source is provided, avoid Quran/hadith references and use general reminders.
- Include this exact reminder in safetyNotes: Review kembali sebelum upload agar tidak salah konteks.

Return JSON only. Do not wrap it in markdown."""


def carousel_user_prompt(
    *,
    topic: str,
    niche: str,
    tone: str,
    slide_count: int,
    platform: str,
    source_context: str,
) -> str:
    source_rule = (
        "A source/transcript was provided. Include a source credit suggestion and warn that context must be reviewed."
        if source_context
        else "No source was provided. Do not invent Quran, hadith, speaker, book, or kajian references."
    )
    return f"""Create one content package.

Topic: {topic}
Niche: {niche}
Tone: {tone}
Platform: {platform}
Slide count: {slide_count}
Source rule: {source_rule}
Source/context, if any:
{source_context or "-"}

JSON schema:
{{
  "title": "string",
  "niche": "string",
  "tone": "string",
  "slides": [
    {{
      "slideNumber": 1,
      "type": "hook|body|closing",
      "text": "string",
      "visualDirection": "string"
    }}
  ],
  "caption": "string",
  "hashtags": ["string"],
  "voiceoverScript": "string",
  "videoStoryboard": [
    {{
      "sceneNumber": 1,
      "durationSeconds": 5,
      "visual": "string",
      "motion": "string",
      "voiceoverPart": "string"
    }}
  ],
  "safetyNotes": ["string"],
  "sourceCreditSuggestion": "string",
  "callToAction": "string"
}}

Rules:
- slides must contain 5 to 8 slides; prefer exactly {slide_count}.
- each slide text must be 25 words or fewer.
- use hook for slide 1, closing for the final slide, and body for the middle slides.
- hashtags should be relevant and not excessive.
- voiceover should fit roughly 30 to 60 seconds.
- videoStoryboard should map naturally to the slides.
- sourceCreditSuggestion should be a placeholder if no source was provided."""


def ideas_user_prompt(niche: str) -> str:
    return f"""Generate 10 content ideas for this niche: {niche}

Return JSON only:
{{
  "niche": "string",
  "ideas": [
    {{
      "title": "string",
      "angle": "string",
      "sampleHook": "string"
    }}
  ],
  "safetyNotes": ["string"]
}}

Use Bahasa Indonesia, calm wording, and the same dakwah safety rules."""


def call_ai_json(messages: list[dict[str, str]]) -> dict[str, Any]:
    if not AI_API_KEY:
        raise AppError(
            HTTPStatus.SERVICE_UNAVAILABLE,
            "missing_ai_api_key",
            "AI_API_KEY is not configured.",
        )

    url = f"{AI_BASE_URL.rstrip('/')}/chat/completions"
    payload = {
        "model": AI_MODEL,
        "messages": messages,
        "temperature": 0.55,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urlrequest.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AI_API_KEY}",
        },
        method="POST",
    )

    LOGGER.info("ai_request_started base_url=%s model=%s", AI_BASE_URL, AI_MODEL)
    started = time.time()
    try:
        with urlrequest.urlopen(req, timeout=AI_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        LOGGER.warning("ai_request_failed status=%s", exc.code)
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_http_error", "AI endpoint returned an error.") from exc
    except urlerror.URLError as exc:
        LOGGER.warning("ai_request_failed reason=%s", exc.reason)
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_unavailable", "AI endpoint is unavailable.") from exc
    except TimeoutError as exc:
        LOGGER.warning("ai_request_failed reason=timeout")
        raise AppError(HTTPStatus.GATEWAY_TIMEOUT, "ai_timeout", "AI endpoint timed out.") from exc

    LOGGER.info("ai_response_received elapsed_ms=%d", int((time.time() - started) * 1000))
    try:
        envelope = json.loads(raw)
        content = envelope["choices"][0]["message"]["content"]
        parsed = json.loads(strip_json_fence(content))
    except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
        LOGGER.warning("ai_invalid_json")
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_invalid_json", "AI returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_invalid_json", "AI JSON response must be an object.")
    return parsed


def normalize_hashtags(value: Any) -> list[str]:
    if isinstance(value, list):
        tags = [str(item).strip() for item in value if str(item).strip()]
    elif isinstance(value, str):
        tags = [part.strip() for part in re.split(r"[\s,]+", value) if part.strip()]
    else:
        tags = []
    normalized = []
    for tag in tags:
        tag = tag if tag.startswith("#") else f"#{tag.lstrip('#')}"
        if tag not in normalized:
            normalized.append(tag)
    return normalized[:12]


def validate_content(content: dict[str, Any]) -> dict[str, Any]:
    required_strings = ["title", "niche", "tone", "caption", "voiceoverScript", "sourceCreditSuggestion", "callToAction"]
    for key in required_strings:
        if not isinstance(content.get(key), str) or not content[key].strip():
            raise ValidationError(f"Missing or invalid field: {key}")
        content[key] = content[key].strip()

    slides = content.get("slides")
    if not isinstance(slides, list) or not 5 <= len(slides) <= 8:
        raise ValidationError("slides must contain 5 to 8 items.")
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise ValidationError("Each slide must be an object.")
        slide["slideNumber"] = parse_int(
            slide.get("slideNumber"),
            index,
            "slideNumber",
            HTTPStatus.BAD_GATEWAY,
            "ai_validation_failed",
        )
        if slide["slideNumber"] != index:
            slide["slideNumber"] = index
        if slide.get("type") not in {"hook", "body", "closing"}:
            raise ValidationError(f"Invalid slide type at slide {index}.")
        for key in ["text", "visualDirection"]:
            if not isinstance(slide.get(key), str) or not slide[key].strip():
                raise ValidationError(f"Missing {key} at slide {index}.")
            slide[key] = slide[key].strip()
        if word_count(slide["text"]) > 25:
            raise ValidationError(f"Slide {index} exceeds 25 words.")

    storyboard = content.get("videoStoryboard")
    if not isinstance(storyboard, list) or not storyboard:
        raise ValidationError("videoStoryboard must contain at least one scene.")
    for index, scene in enumerate(storyboard, start=1):
        if not isinstance(scene, dict):
            raise ValidationError("Each storyboard scene must be an object.")
        scene["sceneNumber"] = parse_int(
            scene.get("sceneNumber"),
            index,
            "sceneNumber",
            HTTPStatus.BAD_GATEWAY,
            "ai_validation_failed",
        )
        scene["durationSeconds"] = parse_int(
            scene.get("durationSeconds"),
            5,
            "durationSeconds",
            HTTPStatus.BAD_GATEWAY,
            "ai_validation_failed",
        )
        for key in ["visual", "motion", "voiceoverPart"]:
            if not isinstance(scene.get(key), str) or not scene[key].strip():
                raise ValidationError(f"Missing {key} at scene {index}.")
            scene[key] = scene[key].strip()

    content["hashtags"] = normalize_hashtags(content.get("hashtags"))
    if not content["hashtags"]:
        raise ValidationError("hashtags must contain at least one tag.")

    notes = content.get("safetyNotes")
    if isinstance(notes, list):
        safety_notes = [str(item).strip() for item in notes if str(item).strip()]
    else:
        safety_notes = []
    reminder = "Review kembali sebelum upload agar tidak salah konteks."
    if reminder not in safety_notes:
        safety_notes.append(reminder)
    content["safetyNotes"] = safety_notes

    LOGGER.info("json_validation_success slides=%d storyboard=%d", len(slides), len(storyboard))
    return content


def validate_ideas(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data.get("niche"), str) or not data["niche"].strip():
        raise ValidationError("Missing niche.")
    ideas = data.get("ideas")
    if not isinstance(ideas, list) or len(ideas) != 10:
        raise ValidationError("ideas must contain exactly 10 items.")
    for idea in ideas:
        if not isinstance(idea, dict):
            raise ValidationError("Each idea must be an object.")
        for key in ["title", "angle", "sampleHook"]:
            if not isinstance(idea.get(key), str) or not idea[key].strip():
                raise ValidationError(f"Missing idea field: {key}")
            idea[key] = idea[key].strip()
    notes = data.get("safetyNotes")
    data["safetyNotes"] = [str(item).strip() for item in notes if str(item).strip()] if isinstance(notes, list) else []
    return data


def split_telegram_message(text: str) -> list[str]:
    if len(text) <= TELEGRAM_LIMIT:
        return [text]
    chunks: list[str] = []
    current = ""
    for block in text.split("\n\n"):
        candidate = f"{current}\n\n{block}".strip() if current else block
        if len(candidate) <= TELEGRAM_LIMIT:
            current = candidate
            continue
        if current:
            chunks.append(current)
        if len(block) <= TELEGRAM_LIMIT:
            current = block
        else:
            for start in range(0, len(block), TELEGRAM_LIMIT):
                chunks.append(block[start : start + TELEGRAM_LIMIT])
            current = ""
    if current:
        chunks.append(current)
    return chunks


def format_full_for_telegram(record: dict[str, Any], include_voiceover: bool = False) -> list[str]:
    content = record["content"]
    lines = [
        "Annotasi Hikmah Carousel",
        "",
        "Title:",
        content["title"],
        "",
    ]
    for slide in content["slides"]:
        lines.extend(
            [
                f"Slide {slide['slideNumber']}:",
                slide["text"],
                "",
            ]
        )
    lines.extend(
        [
            "Caption:",
            content["caption"],
            "",
            "Hashtags:",
            " ".join(content["hashtags"]),
            "",
        ]
    )
    if include_voiceover:
        lines.extend(["Voiceover:", content["voiceoverScript"], ""])
    else:
        lines.extend(["Voiceover:", f"Use /voiceover {record['id']}", ""])
    lines.extend(
        [
            "Content ID:",
            record["id"],
            "",
            "Reminder:",
            "Review kembali sebelum upload agar tidak salah konteks.",
        ]
    )
    return split_telegram_message("\n".join(lines).strip())


def format_caption_for_telegram(record: dict[str, Any]) -> list[str]:
    content = record["content"]
    text = "\n".join(
        [
            f"Caption for {record['id']}",
            "",
            content["caption"],
            "",
            " ".join(content["hashtags"]),
        ]
    )
    return split_telegram_message(text)


def format_voiceover_for_telegram(record: dict[str, Any]) -> list[str]:
    content = record["content"]
    text = "\n".join([f"Voiceover for {record['id']}", "", content["voiceoverScript"]])
    return split_telegram_message(text)


def generate_content(body: dict[str, Any], default_niche: str) -> dict[str, Any]:
    topic = str(body.get("topic") or "").strip()
    if not topic:
        raise AppError(HTTPStatus.BAD_REQUEST, "empty_topic", "Topic is required.")

    slide_count = parse_int(body.get("slideCount"), 7, "slideCount")
    if not 5 <= slide_count <= 8:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_slide_count", "slideCount must be between 5 and 8.")

    niche = str(body.get("niche") or default_niche).strip()
    tone = str(body.get("tone") or "calm_reflective").strip()
    platform = str(body.get("platform") or "instagram").strip()
    source_context = str(body.get("sourceContext") or "").strip()

    LOGGER.info("command_received command=carousel topic_length=%d niche=%s", len(topic), niche)
    LOGGER.info("topic_parsed topic=%s", topic[:120])

    content = call_ai_json(
        [
            {"role": "system", "content": system_prompt()},
            {
                "role": "user",
                "content": carousel_user_prompt(
                    topic=topic,
                    niche=niche,
                    tone=tone,
                    slide_count=slide_count,
                    platform=platform,
                    source_context=source_context,
                ),
            },
        ]
    )
    content = validate_content(content)
    item_id = content_id()
    record = {
        "id": item_id,
        "status": "generated",
        "topic": topic,
        "niche": niche,
        "tone": tone,
        "platform": platform,
        "content": content,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    STORE.save(record)
    messages = format_full_for_telegram(record, include_voiceover=False)
    LOGGER.info("response_prepared content_id=%s telegram_messages=%d", item_id, len(messages))
    return {"id": item_id, "status": "generated", "content": content, "telegramMessages": messages}


def generate_ideas(body: dict[str, Any]) -> dict[str, Any]:
    niche = str(body.get("niche") or "").strip()
    if not niche:
        raise AppError(HTTPStatus.BAD_REQUEST, "empty_niche", "Niche is required.")
    LOGGER.info("command_received command=ideas niche=%s", niche)
    ideas = call_ai_json(
        [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": ideas_user_prompt(niche)},
        ]
    )
    ideas = validate_ideas(ideas)
    lines = [f"Annotasi Ideas: {ideas['niche']}", ""]
    for index, idea in enumerate(ideas["ideas"], start=1):
        lines.extend([f"{index}. {idea['title']}", idea["angle"], f"Hook: {idea['sampleHook']}", ""])
    return {"status": "generated", "ideas": ideas, "telegramMessages": split_telegram_message("\n".join(lines).strip())}


class AnnotasiHandler(BaseHTTPRequestHandler):
    server_version = "AnnotasiCarouselStudio/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.info("http_client %s", format % args)

    def do_GET(self) -> None:
        try:
            self.handle_get()
        except AppError as exc:
            json_response(self, exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except Exception:
            LOGGER.exception("unhandled_error")
            json_response(
                self,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": {"code": "internal_error", "message": "Unexpected server error."}},
            )

    def do_POST(self) -> None:
        try:
            self.handle_post()
        except AppError as exc:
            LOGGER.warning("request_failed code=%s message=%s", exc.code, exc.message)
            json_response(self, exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except Exception:
            LOGGER.exception("unhandled_error")
            json_response(
                self,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": {"code": "internal_error", "message": "Unexpected server error."}},
            )

    def handle_get(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/")
        if path == "/health":
            json_response(self, HTTPStatus.OK, {"status": "ok", "service": "annotasi-carousel-studio"})
            return

        match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})(?:/(caption|voiceover))?", path)
        if not match:
            raise AppError(HTTPStatus.NOT_FOUND, "not_found", "Route not found.")

        item_id, view = match.groups()
        record = STORE.get(item_id)
        if view == "caption":
            body = {
                "id": item_id,
                "caption": record["content"]["caption"],
                "hashtags": record["content"]["hashtags"],
                "telegramMessages": format_caption_for_telegram(record),
            }
        elif view == "voiceover":
            body = {
                "id": item_id,
                "voiceoverScript": record["content"]["voiceoverScript"],
                "telegramMessages": format_voiceover_for_telegram(record),
            }
        else:
            body = {**record, "telegramMessages": format_full_for_telegram(record, include_voiceover=True)}
        json_response(self, HTTPStatus.OK, body)

    def handle_post(self) -> None:
        path = self.path.split("?", 1)[0].rstrip("/")
        body = read_json_body(self)
        if path == "/api/v1/content/carousel":
            json_response(self, HTTPStatus.OK, generate_content(body, "annotasi_hikmah"))
            return
        if path == "/api/v1/content/hikmah":
            body.setdefault("niche", "annotasi_hikmah")
            body.setdefault("tone", "calm_reflective")
            json_response(self, HTTPStatus.OK, generate_content(body, "annotasi_hikmah"))
            return
        if path == "/api/v1/content/ideas":
            json_response(self, HTTPStatus.OK, generate_ideas(body))
            return
        raise AppError(HTTPStatus.NOT_FOUND, "not_found", "Route not found.")


def main() -> int:
    configure_logging()
    LOGGER.info("service_starting host=%s port=%s storage_dir=%s", HOST, PORT, STORAGE_DIR)
    LOGGER.info("ai_config base_url=%s model=%s api_key_configured=%s", AI_BASE_URL, AI_MODEL, bool(AI_API_KEY))
    server = ThreadingHTTPServer((HOST, PORT), AnnotasiHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        LOGGER.info("service_stopping")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
