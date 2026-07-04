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
import subprocess
import sys
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib import error as urlerror
from urllib import request as urlrequest


AI_BASE_URL = os.getenv("AI_BASE_URL", "http://127.0.0.1:20128/v1")
AI_MODEL = os.getenv("AI_MODEL", "annotasi-coding")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "90"))
HOST = os.getenv("ANNOTASI_HOST", "127.0.0.1")
PORT = int(os.getenv("ANNOTASI_PORT", "8097"))
STORAGE_DIR = Path(os.getenv("CONTENT_STORAGE_DIR", "./data/content"))
EXPORT_DIR = Path(os.getenv("CONTENT_EXPORT_DIR", "./data/exports"))
DEFAULT_TEMPLATE = os.getenv("CAROUSEL_DEFAULT_TEMPLATE", "annotasi_hikmah_dark")
CAROUSEL_WIDTH = int(os.getenv("CAROUSEL_WIDTH", "1080"))
CAROUSEL_HEIGHT = int(os.getenv("CAROUSEL_HEIGHT", "1350"))
RENDER_TIMEOUT_SECONDS = float(os.getenv("CAROUSEL_RENDER_TIMEOUT_SECONDS", "60"))
VIDEO_DEFAULT_FORMAT = os.getenv("VIDEO_DEFAULT_FORMAT", "shorts_vertical")
VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))
VIDEO_DURATION_PER_SLIDE_SECONDS = float(os.getenv("VIDEO_DURATION_PER_SLIDE_SECONDS", "5"))
VIDEO_TRANSITION_SECONDS = float(os.getenv("VIDEO_TRANSITION_SECONDS", "0.5"))
VIDEO_DEFAULT_MOTION_PRESET = os.getenv("VIDEO_DEFAULT_MOTION_PRESET", "calm_zoom")
VIDEO_RENDER_TIMEOUT_SECONDS = float(os.getenv("VIDEO_RENDER_TIMEOUT_SECONDS", "180"))
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", "ffprobe")
CONTENT_AUDIO_DIR = Path(os.getenv("CONTENT_AUDIO_DIR", "./data/audio"))
AUDIO_MAX_FILE_SIZE_MB = float(os.getenv("AUDIO_MAX_FILE_SIZE_MB", "50"))
AUDIO_ALLOWED_EXTENSIONS = {
    part.strip().lower().lstrip(".")
    for part in os.getenv("AUDIO_ALLOWED_EXTENSIONS", "mp3,m4a,wav,ogg,oga").split(",")
    if part.strip()
}
AUDIO_NORMALIZE_ENABLED = os.getenv("AUDIO_NORMALIZE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
AUDIO_DEFAULT_FIT_MODE = os.getenv("AUDIO_DEFAULT_FIT_MODE", "trim_or_pad")
AUDIO_RENDER_TIMEOUT_SECONDS = float(os.getenv("AUDIO_RENDER_TIMEOUT_SECONDS", "180"))
AUDIO_OUTPUT_CODEC = os.getenv("AUDIO_OUTPUT_CODEC", "aac")
TELEGRAM_LIMIT = int(os.getenv("TELEGRAM_MESSAGE_LIMIT", "3900"))
SERVICE_DIR = Path(__file__).resolve().parent
NODE_RENDERER = SERVICE_DIR / "render_png.js"

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


def render_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"rnd_{stamp}_{secrets.token_hex(4)}"


def video_render_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"vid_{stamp}_{secrets.token_hex(4)}"


def audio_render_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"aud_{stamp}_{secrets.token_hex(4)}"


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


def parse_float(
    value: Any,
    default: float,
    field_name: str,
    status: HTTPStatus = HTTPStatus.BAD_REQUEST,
    code: str = "invalid_number",
) -> float:
    if value in (None, ""):
        return default
    try:
        return float(value)
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

    def find_render(self, item_render_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"rnd_\d{8}_[a-f0-9]{8}", item_render_id):
            raise AppError(HTTPStatus.BAD_REQUEST, "invalid_render_id", "Render ID format is invalid.")
        try:
            paths = list(self.root.glob("cnt_*.json"))
        except OSError as exc:
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_failure", "Could not list content.") from exc
        for path in paths:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            renders = record.get("renders") if isinstance(record, dict) else None
            if not isinstance(renders, list):
                continue
            for item in renders:
                if isinstance(item, dict) and item.get("renderId") == item_render_id:
                    return item
        raise AppError(HTTPStatus.NOT_FOUND, "render_not_found", "Render metadata was not found.")

    def find_video_render(self, item_video_render_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"vid_\d{8}_[a-f0-9]{8}", item_video_render_id):
            raise AppError(HTTPStatus.BAD_REQUEST, "invalid_video_render_id", "Video render ID format is invalid.")
        try:
            paths = list(self.root.glob("cnt_*.json"))
        except OSError as exc:
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_failure", "Could not list content.") from exc
        for path in paths:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            video_renders = record.get("videoRenders") if isinstance(record, dict) else None
            if not isinstance(video_renders, list):
                continue
            for item in video_renders:
                if isinstance(item, dict) and item.get("videoRenderId") == item_video_render_id:
                    return item
        raise AppError(HTTPStatus.NOT_FOUND, "video_render_not_found", "Video render metadata was not found.")

    def find_audio_render(self, item_audio_render_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"aud_\d{8}_[a-f0-9]{8}", item_audio_render_id):
            raise AppError(HTTPStatus.BAD_REQUEST, "invalid_audio_render_id", "Audio render ID format is invalid.")
        try:
            paths = list(self.root.glob("cnt_*.json"))
        except OSError as exc:
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_failure", "Could not list content.") from exc
        for path in paths:
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            audio_renders = record.get("audioRenders") if isinstance(record, dict) else None
            if not isinstance(audio_renders, list):
                continue
            for item in audio_renders:
                if isinstance(item, dict) and item.get("audioRenderId") == item_audio_render_id:
                    return item
        raise AppError(HTTPStatus.NOT_FOUND, "audio_render_not_found", "Audio render metadata was not found.")


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


def format_render_for_telegram(render: dict[str, Any]) -> list[str]:
    files = render.get("files") if isinstance(render.get("files"), list) else []
    lines = [
        "Annotasi Carousel Rendered",
        "",
        "Content ID:",
        str(render.get("contentId", "")),
        "",
        "Render ID:",
        str(render.get("renderId", "")),
        "",
        "Format:",
        f"{render.get('format', 'instagram_carousel')} {render.get('width')}x{render.get('height')}",
        "",
        "Slides:",
        f"{len(files)} PNG files generated",
        "",
        "Output:",
    ]
    for item in files:
        if isinstance(item, dict):
            lines.append(f"- {item.get('filename')}: {item.get('path')}")
    lines.extend(
        [
            "",
            "Reminder:",
            "Review kembali sebelum upload agar tidak salah konteks.",
        ]
    )
    return split_telegram_message("\n".join(lines).strip())


def validate_renderable_content(record: dict[str, Any]) -> list[dict[str, Any]]:
    content = record.get("content")
    if not isinstance(content, dict):
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_content", "Content package is invalid.")
    slides = content.get("slides")
    if not isinstance(slides, list) or not slides:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "no_slides", "Content package has no slides.")
    if not 5 <= len(slides) <= 8:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "unsupported_slide_count", "Slide count must be between 5 and 8.")
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_slide", f"Slide {index} is invalid.")
        text = str(slide.get("text") or "").strip()
        if not text:
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_slide", f"Slide {index} has no text.")
        if len(text) > 700:
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "slide_text_too_long", f"Slide {index} text is too long to render.")
    return slides


def render_files_exist(render: dict[str, Any]) -> bool:
    files = render.get("files")
    if not isinstance(files, list) or not files:
        return False
    return all(isinstance(item, dict) and Path(str(item.get("path", ""))).exists() for item in files)


def latest_completed_render(
    record: dict[str, Any],
    *,
    output_format: str,
    template_name: str,
    width: int,
    height: int,
) -> Optional[dict[str, Any]]:
    renders = record.get("renders")
    if not isinstance(renders, list):
        return None
    for item in reversed(renders):
        if not isinstance(item, dict):
            continue
        if (
            item.get("status") == "completed"
            and item.get("format") == output_format
            and item.get("templateName") == template_name
            and item.get("width") == width
            and item.get("height") == height
            and render_files_exist(item)
        ):
            return item
    return None


def normalize_render_result(render: dict[str, Any]) -> dict[str, Any]:
    return {**render, "telegramMessages": format_render_for_telegram(render)}


def format_video_for_telegram(video_render: dict[str, Any]) -> list[str]:
    file_info = video_render.get("file") if isinstance(video_render.get("file"), dict) else {}
    lines = [
        "Annotasi Motion Video Rendered",
        "",
        "Content ID:",
        str(video_render.get("contentId", "")),
        "",
        "Video Render ID:",
        str(video_render.get("videoRenderId", "")),
        "",
        "Format:",
        f"Vertical MP4 {video_render.get('width')}x{video_render.get('height')}",
        "",
        "Slides:",
        str(video_render.get("slideCount", "")),
        "",
        "Duration:",
        f"{video_render.get('totalDurationSeconds')} seconds",
        "",
        "Output:",
        str(file_info.get("path") or file_info.get("filename") or "final.mp4"),
        "",
        "Reminder:",
        "Review kembali sebelum upload agar tidak salah konteks.",
    ]
    return split_telegram_message("\n".join(lines).strip())


def normalize_video_result(video_render: dict[str, Any]) -> dict[str, Any]:
    return {**video_render, "telegramMessages": format_video_for_telegram(video_render)}


def format_audio_prepare_for_telegram(session: dict[str, Any]) -> list[str]:
    lines = [
        "Voiceover Mixing Mode",
        "",
        "Content ID:",
        str(session.get("contentId", "")),
        "",
        "Audio Session ID:",
        str(session.get("audioSessionId", "")),
        "",
        "Silakan kirim voice note atau file audio untuk content ID ini melalui Hermes, atau gunakan:",
        f"/mixvoice_file {session.get('contentId', '')} <audio_file_path>",
        "",
        "Supported formats:",
        ", ".join(session.get("supportedFormats", [])),
        "",
        "Reminder:",
        "Gunakan suara kamu sendiri. Jangan gunakan voice cloning atau imitasi suara orang lain.",
    ]
    return split_telegram_message("\n".join(lines).strip())


def format_audio_for_telegram(audio_render: dict[str, Any]) -> list[str]:
    output_video = audio_render.get("outputVideo") if isinstance(audio_render.get("outputVideo"), dict) else {}
    lines = [
        "Final Video dengan Voiceover",
        "",
        "Content ID:",
        str(audio_render.get("contentId", "")),
        "",
        "Audio Render ID:",
        str(audio_render.get("audioRenderId", "")),
        "",
        "Source Video Render ID:",
        str(audio_render.get("sourceVideoRenderId", "")),
        "",
        "Duration:",
        f"{audio_render.get('finalDurationSeconds')} seconds",
        "",
        "Output:",
        str(output_video.get("path") or output_video.get("filename") or "final-voiceover.mp4"),
        "",
        "Reminder:",
        "Review kembali sebelum upload agar tidak salah konteks.",
    ]
    return split_telegram_message("\n".join(lines).strip())


def normalize_audio_result(audio_render: dict[str, Any]) -> dict[str, Any]:
    return {**audio_render, "telegramMessages": format_audio_for_telegram(audio_render)}


def audio_file_exists(audio_render: dict[str, Any]) -> bool:
    output_video = audio_render.get("outputVideo")
    if not isinstance(output_video, dict):
        return False
    path = Path(str(output_video.get("path") or ""))
    return path.exists() and path.is_file() and path.stat().st_size > 0


def latest_completed_audio_render(
    record: dict[str, Any],
    *,
    source_video_render_id: str,
    source_audio_path: str,
    audio_mode: str,
    normalize_audio: bool,
    fit_mode: str,
) -> Optional[dict[str, Any]]:
    audio_renders = record.get("audioRenders")
    if not isinstance(audio_renders, list):
        return None
    normalized_source = str(Path(source_audio_path).resolve())
    for item in reversed(audio_renders):
        if not isinstance(item, dict):
            continue
        if (
            item.get("status") == "completed"
            and item.get("sourceVideoRenderId") == source_video_render_id
            and item.get("sourceAudioPath") == normalized_source
            and item.get("audioMode") == audio_mode
            and item.get("normalizeAudio") == normalize_audio
            and item.get("fitMode") == fit_mode
            and audio_file_exists(item)
        ):
            return item
    return None


def latest_completed_video_for_audio(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    video_renders = record.get("videoRenders")
    if not isinstance(video_renders, list):
        return None
    for item in reversed(video_renders):
        if isinstance(item, dict) and item.get("status") == "completed" and video_file_exists(item):
            return item
    return None


def video_file_exists(video_render: dict[str, Any]) -> bool:
    file_info = video_render.get("file")
    if not isinstance(file_info, dict):
        return False
    path = Path(str(file_info.get("path") or ""))
    return path.exists() and path.is_file() and path.stat().st_size > 0


def latest_completed_video_render(
    record: dict[str, Any],
    *,
    output_format: str,
    template_name: str,
    motion_preset: str,
    width: int,
    height: int,
    fps: int,
    duration_per_slide: float,
    transition_seconds: float,
) -> Optional[dict[str, Any]]:
    video_renders = record.get("videoRenders")
    if not isinstance(video_renders, list):
        return None
    for item in reversed(video_renders):
        if not isinstance(item, dict):
            continue
        if (
            item.get("status") == "completed"
            and item.get("format") == output_format
            and item.get("templateName") == template_name
            and item.get("motionPreset") == motion_preset
            and item.get("width") == width
            and item.get("height") == height
            and item.get("fps") == fps
            and float(item.get("durationPerSlideSeconds", -1)) == duration_per_slide
            and float(item.get("transitionSeconds", -1)) == transition_seconds
            and video_file_exists(item)
        ):
            return item
    return None


def latest_completed_png_render(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    renders = record.get("renders")
    if not isinstance(renders, list):
        return None
    for item in reversed(renders):
        if (
            isinstance(item, dict)
            and item.get("status") == "completed"
            and item.get("format") == "instagram_carousel"
            and render_files_exist(item)
        ):
            return item
    return None


def validate_png_files(render: dict[str, Any], expected_slides: int) -> list[dict[str, Any]]:
    files = render.get("files")
    if not isinstance(files, list) or not files:
        raise AppError(HTTPStatus.NOT_FOUND, "png_render_not_found", "PNG render has no files. Run /render first.")
    ordered = sorted(
        [item for item in files if isinstance(item, dict)],
        key=lambda item: int(item.get("slideNumber") or 0),
    )
    if len(ordered) != expected_slides:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "png_file_count_mismatch", "PNG file count does not match slide count.")
    for index, item in enumerate(ordered, start=1):
        if int(item.get("slideNumber") or 0) != index:
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "png_file_count_mismatch", "PNG slide numbers are not sequential.")
        path = Path(str(item.get("path") or ""))
        if path.suffix.lower() != ".png":
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_png_file", f"Slide {index} file is not a PNG.")
        if not path.exists() or not path.is_file():
            raise AppError(HTTPStatus.NOT_FOUND, "png_files_missing", f"PNG file missing for slide {index}. Run /render again.")
        item["path"] = str(path)
    LOGGER.info("png_files_validated count=%d", len(ordered))
    return ordered


def check_ffmpeg_available() -> None:
    try:
        completed = subprocess.run(
            [FFMPEG_PATH, "-version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffmpeg_not_found", "FFmpeg is not installed or FFMPEG_PATH is invalid.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffmpeg_unavailable", "FFmpeg availability check timed out.") from exc
    if completed.returncode != 0:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffmpeg_unavailable", "FFmpeg is unavailable.")
    LOGGER.info("ffmpeg_availability_checked")


def check_ffprobe_available() -> None:
    try:
        completed = subprocess.run(
            [FFPROBE_PATH, "-version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffprobe_not_found", "FFprobe is not installed or FFPROBE_PATH is invalid.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffprobe_unavailable", "FFprobe availability check timed out.") from exc
    if completed.returncode != 0:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffprobe_unavailable", "FFprobe is unavailable.")


def run_ffmpeg(args: list[str], timeout: float, failure_code: str, failure_message: str) -> None:
    try:
        completed = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffmpeg_not_found", "FFmpeg is not installed or FFMPEG_PATH is invalid.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(HTTPStatus.GATEWAY_TIMEOUT, "video_render_timeout", "FFmpeg video rendering timed out.") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else failure_message
        raise AppError(HTTPStatus.BAD_GATEWAY, failure_code, f"{failure_message}: {detail[:300]}")


def run_ffprobe_json(args: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffprobe_not_found", "FFprobe is not installed or FFPROBE_PATH is invalid.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(HTTPStatus.GATEWAY_TIMEOUT, "ffprobe_timeout", "FFprobe timed out.") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "FFprobe failed."
        raise AppError(HTTPStatus.BAD_GATEWAY, "ffprobe_failed", f"FFprobe failed: {detail[:300]}")
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AppError(HTTPStatus.BAD_GATEWAY, "ffprobe_invalid_json", "FFprobe returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise AppError(HTTPStatus.BAD_GATEWAY, "ffprobe_invalid_json", "FFprobe returned invalid JSON.")
    return data


def probe_media(path: Path) -> dict[str, Any]:
    return run_ffprobe_json(
        [
            FFPROBE_PATH,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type",
            "-of",
            "json",
            str(path),
        ]
    )


def media_duration_seconds(probe: dict[str, Any], field_name: str) -> float:
    format_info = probe.get("format")
    if not isinstance(format_info, dict):
        raise AppError(HTTPStatus.BAD_GATEWAY, "duration_detection_failed", f"Could not detect {field_name} duration.")
    try:
        duration = float(format_info.get("duration"))
    except (TypeError, ValueError) as exc:
        raise AppError(HTTPStatus.BAD_GATEWAY, "duration_detection_failed", f"Could not detect {field_name} duration.") from exc
    if duration <= 0:
        raise AppError(HTTPStatus.BAD_GATEWAY, "duration_detection_failed", f"{field_name} duration is invalid.")
    return round(duration, 3)


def probe_has_stream(probe: dict[str, Any], stream_type: str) -> bool:
    streams = probe.get("streams")
    if not isinstance(streams, list):
        return False
    return any(isinstance(stream, dict) and stream.get("codec_type") == stream_type for stream in streams)


def resolve_allowed_audio_path(raw_path: str) -> Path:
    if not raw_path or "\x00" in raw_path:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_audio_path", "Audio file path is invalid.")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (SERVICE_DIR / path).resolve()
    else:
        path = path.resolve()
    allowed_root = CONTENT_AUDIO_DIR.resolve()
    try:
        path.relative_to(allowed_root)
    except ValueError as exc:
        raise AppError(
            HTTPStatus.BAD_REQUEST,
            "audio_path_not_allowed",
            f"Audio file must be inside CONTENT_AUDIO_DIR: {allowed_root}",
        ) from exc
    return path


def validate_audio_file(raw_path: str) -> tuple[Path, float]:
    LOGGER.info("audio_validation_started")
    path = resolve_allowed_audio_path(raw_path)
    if not path.exists() or not path.is_file():
        raise AppError(HTTPStatus.NOT_FOUND, "audio_file_missing", "Audio file was not found.")
    extension = path.suffix.lower().lstrip(".")
    if extension not in AUDIO_ALLOWED_EXTENSIONS:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "unsupported_audio_format", "Audio format is not supported.")
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > AUDIO_MAX_FILE_SIZE_MB:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "audio_too_large", "Audio file exceeds configured size limit.")
    probe = probe_media(path)
    if not probe_has_stream(probe, "audio"):
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_audio_stream", "Audio file has no valid audio stream.")
    duration = media_duration_seconds(probe, "audio")
    LOGGER.info("audio_validation_completed duration_seconds=%s size_mb=%.2f", duration, size_mb)
    return path, duration


def normalize_voiceover_audio(source_path: Path, output_path: Path, video_duration: float) -> None:
    LOGGER.info("normalization_started")
    args = [
        FFMPEG_PATH,
        "-y",
        "-i",
        str(source_path),
        "-t",
        f"{video_duration:.3f}",
        "-vn",
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    run_ffmpeg(args, AUDIO_RENDER_TIMEOUT_SECONDS, "audio_normalization_failed", "FFmpeg failed to normalize audio")
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise AppError(HTTPStatus.BAD_GATEWAY, "audio_normalization_failed", "Normalized audio file is missing or empty.")
    LOGGER.info("normalization_completed")


def mix_voiceover_video(source_video: Path, source_audio: Path, output_video: Path, video_duration: float) -> None:
    LOGGER.info("mixing_started")
    args = [
        FFMPEG_PATH,
        "-y",
        "-i",
        str(source_video),
        "-i",
        str(source_audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        AUDIO_OUTPUT_CODEC,
        "-b:a",
        "192k",
        "-t",
        f"{video_duration:.3f}",
        "-movflags",
        "+faststart",
        str(output_video),
    ]
    run_ffmpeg(args, AUDIO_RENDER_TIMEOUT_SECONDS, "audio_mixing_failed", "FFmpeg failed to mix audio into video")
    if not output_video.exists() or output_video.stat().st_size <= 0:
        raise AppError(HTTPStatus.BAD_GATEWAY, "audio_output_missing", "Generated voiceover MP4 is missing or empty.")
    LOGGER.info("mixing_completed")


def write_audio_metadata(output_dir: Path, audio_render: dict[str, Any]) -> None:
    metadata_path = output_dir / "audio-render-metadata.json"
    try:
        metadata_path.write_text(json.dumps(audio_render, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "metadata_write_failed", "Could not write audio metadata.") from exc


def prepare_audio_session(item_id: str) -> dict[str, Any]:
    LOGGER.info("audio_prepare_request_received content_id=%s", item_id)
    record = STORE.get(item_id)
    validate_renderable_content(record)
    audio_dir = (CONTENT_AUDIO_DIR / item_id).resolve()
    try:
        audio_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "audio_directory_not_writable", "Audio directory is not writable.") from exc
    session = {
        "contentId": item_id,
        "audioSessionId": audio_render_id(),
        "status": "waiting_for_audio",
        "supportedFormats": sorted(AUDIO_ALLOWED_EXTENSIONS),
        "audioDirectory": str(audio_dir),
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    if not isinstance(record.get("audioSessions"), list):
        record["audioSessions"] = []
    record["audioSessions"].append(session)
    record["latestAudioSession"] = session
    record["updatedAt"] = now_iso()
    STORE.save(record)
    return {**session, "telegramMessages": format_audio_prepare_for_telegram(session)}


def render_content_audio_mix(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    audio_file_path = str(body.get("audioFilePath") or "").strip()
    if not audio_file_path:
        raise AppError(HTTPStatus.BAD_REQUEST, "missing_audio_file_path", "audioFilePath is required.")
    audio_mode = str(body.get("audioMode") or "voiceover").strip()
    normalize_audio = bool(body.get("normalizeAudio", AUDIO_NORMALIZE_ENABLED))
    fit_mode = str(body.get("fitMode") or AUDIO_DEFAULT_FIT_MODE).strip()
    force_regenerate = bool(body.get("forceRegenerate", False))

    if audio_mode != "voiceover":
        raise AppError(HTTPStatus.BAD_REQUEST, "unsupported_audio_mode", "Only voiceover audio mode is supported.")
    if fit_mode != "trim_or_pad":
        raise AppError(HTTPStatus.BAD_REQUEST, "unsupported_fit_mode", "Only trim_or_pad fit mode is supported.")

    LOGGER.info("audio_mix_request_received content_id=%s mode=%s", item_id, audio_mode)
    record = STORE.get(item_id)
    validate_renderable_content(record)
    LOGGER.info("content_loaded content_id=%s", item_id)

    video_render = latest_completed_video_for_audio(record)
    if not video_render:
        raise AppError(HTTPStatus.NOT_FOUND, "video_render_not_found", "Video render not found. Run /video <content_id> first.")
    source_video = Path(str(video_render.get("file", {}).get("path") if isinstance(video_render.get("file"), dict) else ""))
    if not source_video.exists() or not source_video.is_file() or source_video.stat().st_size <= 0:
        raise AppError(HTTPStatus.NOT_FOUND, "source_mp4_missing", "Source MP4 is missing. Run /video again.")
    LOGGER.info("video_render_loaded content_id=%s video_render_id=%s", item_id, video_render.get("videoRenderId"))

    check_ffmpeg_available()
    check_ffprobe_available()

    video_probe = probe_media(source_video)
    if not probe_has_stream(video_probe, "video"):
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_source_video", "Source MP4 has no valid video stream.")
    video_duration = media_duration_seconds(video_probe, "video")

    audio_path, audio_duration = validate_audio_file(audio_file_path)
    LOGGER.info("audio_video_durations_detected video_seconds=%s audio_seconds=%s", video_duration, audio_duration)

    existing = latest_completed_audio_render(
        record,
        source_video_render_id=str(video_render.get("videoRenderId") or ""),
        source_audio_path=str(audio_path),
        audio_mode=audio_mode,
        normalize_audio=normalize_audio,
        fit_mode=fit_mode,
    )
    if existing and not force_regenerate:
        LOGGER.info("duplicate_audio_render_returned content_id=%s audio_render_id=%s", item_id, existing.get("audioRenderId"))
        return normalize_audio_result(existing)

    item_audio_render_id = audio_render_id()
    output_dir = (EXPORT_DIR / item_id / item_audio_render_id).resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "output_not_writable", "Output directory is not writable.") from exc

    normalized_audio_path = output_dir / "voiceover-normalized.wav" if normalize_audio else None
    output_video_path = output_dir / "final-voiceover.mp4"
    audio_render = {
        "contentId": item_id,
        "audioRenderId": item_audio_render_id,
        "status": "processing",
        "sourceVideoRenderId": video_render.get("videoRenderId"),
        "sourceAudioPath": str(audio_path),
        "normalizedAudioPath": str(normalized_audio_path) if normalized_audio_path else "",
        "audioFile": {"filename": audio_path.name, "path": str(audio_path)},
        "outputVideo": {"filename": "final-voiceover.mp4", "path": str(output_video_path), "mimeType": "video/mp4"},
        "audioMode": audio_mode,
        "normalizeAudio": normalize_audio,
        "fitMode": fit_mode,
        "videoDurationSeconds": video_duration,
        "audioDurationSeconds": audio_duration,
        "finalDurationSeconds": video_duration,
        "statusMessage": "",
        "errorMessage": "",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    if not isinstance(record.get("audioRenders"), list):
        record["audioRenders"] = []
    record["audioRenders"].append(audio_render)
    record["latestAudioRender"] = audio_render
    record["updatedAt"] = now_iso()
    STORE.save(record)

    try:
        audio_to_mix = audio_path
        if normalize_audio and normalized_audio_path:
            normalize_voiceover_audio(audio_path, normalized_audio_path, video_duration)
            audio_to_mix = normalized_audio_path
        mix_voiceover_video(source_video, audio_to_mix, output_video_path, video_duration)
        final_probe = probe_media(output_video_path)
        if not probe_has_stream(final_probe, "video") or not probe_has_stream(final_probe, "audio"):
            raise AppError(HTTPStatus.BAD_GATEWAY, "invalid_audio_output", "Generated MP4 is missing video or audio stream.")
        audio_render["finalDurationSeconds"] = media_duration_seconds(final_probe, "final video")
    except AppError as exc:
        audio_render["status"] = "failed"
        audio_render["errorMessage"] = exc.message
        audio_render["updatedAt"] = now_iso()
        record["latestAudioRender"] = audio_render
        record["updatedAt"] = now_iso()
        STORE.save(record)
        raise

    audio_render["status"] = "completed"
    audio_render["updatedAt"] = now_iso()
    write_audio_metadata(output_dir, audio_render)
    record["latestAudioRender"] = audio_render
    record["updatedAt"] = now_iso()
    STORE.save(record)
    LOGGER.info("audio_metadata_stored content_id=%s audio_render_id=%s", item_id, item_audio_render_id)
    return normalize_audio_result(audio_render)


def video_filter_for_slide(
    *,
    motion_preset: str,
    width: int,
    height: int,
    fps: int,
    duration: float,
    transition: float,
) -> str:
    frames = max(1, int(round(duration * fps)))
    safe_transition = max(0.0, min(transition, duration / 2))
    fade_in = min(0.25, safe_transition)
    fade_out_start = max(0.0, duration - safe_transition)
    foreground_width = width
    foreground_height = min(height, int(round(width * 1.25)))
    base_scale = (
        f"[0:v]scale={foreground_width}:{foreground_height}:force_original_aspect_ratio=decrease,"
        f"pad={foreground_width}:{foreground_height}:(ow-iw)/2:(oh-ih)/2:color=#12110d"
    )
    if motion_preset == "calm_zoom":
        foreground = (
            f"{base_scale},"
            f"zoompan=z='min(zoom+0.00035,1.035)':d={frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={foreground_width}x{foreground_height}:"
            f"fps={fps}[fg]"
        )
    else:
        foreground = f"{base_scale},setsar=1[fg]"
    return (
        f"{foreground};"
        f"[1:v][fg]overlay=(W-w)/2:(H-h)/2:format=auto,"
        f"format=yuv420p,"
        f"fade=t=in:st=0:d={fade_in:.3f},"
        f"fade=t=out:st={fade_out_start:.3f}:d={safe_transition:.3f}[v]"
    )


def create_video_segment(
    *,
    png_path: Path,
    segment_path: Path,
    motion_preset: str,
    width: int,
    height: int,
    fps: int,
    duration: float,
    transition: float,
) -> None:
    filter_graph = video_filter_for_slide(
        motion_preset=motion_preset,
        width=width,
        height=height,
        fps=fps,
        duration=duration,
        transition=transition,
    )
    args = [
        FFMPEG_PATH,
        "-y",
        "-loop",
        "1",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(png_path),
        "-f",
        "lavfi",
        "-t",
        f"{duration:.3f}",
        "-i",
        f"color=c=#12110d:s={width}x{height}:r={fps}",
        "-filter_complex",
        filter_graph,
        "-map",
        "[v]",
        "-frames:v",
        str(max(1, int(round(duration * fps)))),
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(segment_path),
    ]
    run_ffmpeg(args, VIDEO_RENDER_TIMEOUT_SECONDS, "ffmpeg_segment_failed", "FFmpeg failed to render a slide segment")


def concat_segments(segment_paths: list[Path], concat_file: Path, output_path: Path) -> None:
    lines = []
    for segment_path in segment_paths:
        escaped = str(segment_path).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args = [
        FFMPEG_PATH,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    run_ffmpeg(args, VIDEO_RENDER_TIMEOUT_SECONDS, "ffmpeg_concat_failed", "FFmpeg failed to export final MP4")


def write_video_metadata(output_dir: Path, video_render: dict[str, Any]) -> None:
    metadata_path = output_dir / "render-metadata.json"
    try:
        metadata_path.write_text(json.dumps(video_render, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "metadata_write_failed", "Could not write video metadata.") from exc


def render_content_video(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    output_format = str(body.get("format") or VIDEO_DEFAULT_FORMAT).strip()
    template_name = str(body.get("template") or DEFAULT_TEMPLATE).strip()
    motion_preset = str(body.get("motionPreset") or VIDEO_DEFAULT_MOTION_PRESET).strip()
    force_regenerate = bool(body.get("forceRegenerate", False))
    width = parse_int(body.get("width"), VIDEO_WIDTH, "width")
    height = parse_int(body.get("height"), VIDEO_HEIGHT, "height")
    fps = parse_int(body.get("fps"), VIDEO_FPS, "fps")
    duration_per_slide = parse_float(body.get("durationPerSlideSeconds"), VIDEO_DURATION_PER_SLIDE_SECONDS, "durationPerSlideSeconds")
    transition_seconds = parse_float(body.get("transitionSeconds"), VIDEO_TRANSITION_SECONDS, "transitionSeconds")

    if output_format != "shorts_vertical":
        raise AppError(HTTPStatus.BAD_REQUEST, "unsupported_format", "Only shorts_vertical is supported.")
    if template_name != "annotasi_hikmah_dark":
        raise AppError(HTTPStatus.BAD_REQUEST, "template_not_found", "Template was not found.")
    if motion_preset not in {"calm_zoom", "static"}:
        raise AppError(HTTPStatus.BAD_REQUEST, "unsupported_motion_preset", "Only calm_zoom and static are supported.")
    if width <= 0 or height <= 0 or fps <= 0:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_video_settings", "Video dimensions and fps must be positive.")
    if duration_per_slide <= 0 or transition_seconds < 0:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_video_settings", "Video durations must be valid positive numbers.")
    if body.get("includeVoiceover") or body.get("voiceoverAudioPath"):
        raise AppError(HTTPStatus.BAD_REQUEST, "voiceover_not_supported", "Voiceover audio mixing is reserved for a future milestone.")
    if body.get("backgroundMusicPath"):
        raise AppError(HTTPStatus.BAD_REQUEST, "background_music_not_supported", "Background music mixing is reserved for a future milestone.")

    LOGGER.info("video_render_request_received content_id=%s format=%s preset=%s", item_id, output_format, motion_preset)
    record = STORE.get(item_id)
    slides = validate_renderable_content(record)
    LOGGER.info("content_loaded content_id=%s slides=%d", item_id, len(slides))

    png_render = latest_completed_png_render(record)
    if not png_render:
        raise AppError(HTTPStatus.NOT_FOUND, "png_render_not_found", "PNG render not found. Run /render <content_id> first.")
    png_files = validate_png_files(png_render, len(slides))
    LOGGER.info("png_render_loaded content_id=%s render_id=%s", item_id, png_render.get("renderId"))

    existing = latest_completed_video_render(
        record,
        output_format=output_format,
        template_name=template_name,
        motion_preset=motion_preset,
        width=width,
        height=height,
        fps=fps,
        duration_per_slide=duration_per_slide,
        transition_seconds=transition_seconds,
    )
    if existing and not force_regenerate:
        LOGGER.info("duplicate_video_render_returned content_id=%s video_render_id=%s", item_id, existing.get("videoRenderId"))
        return normalize_video_result(existing)

    check_ffmpeg_available()

    item_video_render_id = video_render_id()
    output_dir = (EXPORT_DIR / item_id / item_video_render_id).resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "output_not_writable", "Output directory is not writable.") from exc

    total_duration = round(len(png_files) * duration_per_slide, 3)
    output_path = output_dir / "final.mp4"
    video_render = {
        "contentId": item_id,
        "videoRenderId": item_video_render_id,
        "status": "rendering",
        "sourcePngRenderId": png_render.get("renderId"),
        "format": output_format,
        "templateName": template_name,
        "motionPreset": motion_preset,
        "width": width,
        "height": height,
        "fps": fps,
        "durationPerSlideSeconds": duration_per_slide,
        "transitionSeconds": transition_seconds,
        "totalDurationSeconds": total_duration,
        "slideCount": len(png_files),
        "file": {"filename": "final.mp4", "path": str(output_path), "mimeType": "video/mp4"},
        "errorMessage": "",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    if not isinstance(record.get("videoRenders"), list):
        record["videoRenders"] = []
    record["videoRenders"].append(video_render)
    record["latestVideoRender"] = video_render
    record["updatedAt"] = now_iso()
    STORE.save(record)

    try:
        LOGGER.info("video_render_plan_created content_id=%s video_render_id=%s slides=%d", item_id, item_video_render_id, len(png_files))
        segment_paths = []
        for file_info in png_files:
            slide_number = int(file_info["slideNumber"])
            LOGGER.info("segment_generation_started content_id=%s video_render_id=%s slide=%d", item_id, item_video_render_id, slide_number)
            segment_path = output_dir / f"segment-{slide_number:02d}.mp4"
            create_video_segment(
                png_path=Path(str(file_info["path"])),
                segment_path=segment_path,
                motion_preset=motion_preset,
                width=width,
                height=height,
                fps=fps,
                duration=duration_per_slide,
                transition=transition_seconds,
            )
            if not segment_path.exists() or segment_path.stat().st_size <= 0:
                raise AppError(HTTPStatus.BAD_GATEWAY, "segment_missing", f"Segment missing for slide {slide_number}.")
            segment_paths.append(segment_path)
            LOGGER.info("segment_generation_completed content_id=%s video_render_id=%s slide=%d", item_id, item_video_render_id, slide_number)

        LOGGER.info("final_video_export_started content_id=%s video_render_id=%s", item_id, item_video_render_id)
        concat_segments(segment_paths, output_dir / "segments.txt", output_path)
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise AppError(HTTPStatus.BAD_GATEWAY, "video_output_missing", "Generated MP4 is missing or empty.")
        LOGGER.info("final_video_export_completed content_id=%s video_render_id=%s", item_id, item_video_render_id)
    except AppError as exc:
        video_render["status"] = "failed"
        video_render["errorMessage"] = exc.message
        video_render["updatedAt"] = now_iso()
        record["latestVideoRender"] = video_render
        record["updatedAt"] = now_iso()
        STORE.save(record)
        raise

    video_render["status"] = "completed"
    video_render["updatedAt"] = now_iso()
    write_video_metadata(output_dir, video_render)
    record["latestVideoRender"] = video_render
    record["updatedAt"] = now_iso()
    STORE.save(record)
    LOGGER.info("video_metadata_stored content_id=%s video_render_id=%s", item_id, item_video_render_id)
    return normalize_video_result(video_render)


def call_png_renderer(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not NODE_RENDERER.exists():
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "render_dependency_unavailable", "PNG renderer script is unavailable.")
    try:
        completed = subprocess.run(
            ["node", str(NODE_RENDERER)],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=RENDER_TIMEOUT_SECONDS,
            cwd=str(SERVICE_DIR),
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "render_dependency_unavailable", "Node.js is required for PNG rendering.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(HTTPStatus.GATEWAY_TIMEOUT, "render_timeout", "PNG rendering timed out.") from exc

    if completed.returncode != 0:
        message = "PNG generation failed."
        code = "png_generation_failed"
        try:
            error_body = json.loads(completed.stdout or "{}")
            if isinstance(error_body, dict):
                code = str(error_body.get("code") or code)
                message = str(error_body.get("message") or message)
        except json.JSONDecodeError:
            if completed.stderr.strip():
                message = completed.stderr.strip()[:300]
        status_by_code = {
            "render_dependency_unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
            "template_not_found": HTTPStatus.BAD_REQUEST,
            "slide_text_too_long": HTTPStatus.UNPROCESSABLE_ENTITY,
            "no_slides": HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_slide": HTTPStatus.UNPROCESSABLE_ENTITY,
        }
        raise AppError(status_by_code.get(code, HTTPStatus.BAD_GATEWAY), code, message)

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AppError(HTTPStatus.BAD_GATEWAY, "png_generation_failed", "PNG renderer returned invalid JSON.") from exc
    files = result.get("files") if isinstance(result, dict) else None
    if not isinstance(files, list) or not files:
        raise AppError(HTTPStatus.BAD_GATEWAY, "png_generation_failed", "PNG renderer did not return files.")
    return files


def render_content_png(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    output_format = str(body.get("format") or "instagram_carousel").strip()
    template_name = str(body.get("template") or DEFAULT_TEMPLATE).strip()
    force_regenerate = bool(body.get("forceRegenerate", False))
    width = parse_int(body.get("width"), CAROUSEL_WIDTH, "width")
    height = parse_int(body.get("height"), CAROUSEL_HEIGHT, "height")

    if output_format != "instagram_carousel":
        raise AppError(HTTPStatus.BAD_REQUEST, "unsupported_format", "Only instagram_carousel is supported.")
    if template_name != "annotasi_hikmah_dark":
        raise AppError(HTTPStatus.BAD_REQUEST, "template_not_found", "Template was not found.")
    if width <= 0 or height <= 0:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_dimensions", "Render dimensions must be positive.")

    LOGGER.info("render_request_received content_id=%s format=%s template=%s", item_id, output_format, template_name)
    record = STORE.get(item_id)
    slides = validate_renderable_content(record)
    LOGGER.info("content_loaded content_id=%s slides=%d", item_id, len(slides))

    existing = latest_completed_render(
        record,
        output_format=output_format,
        template_name=template_name,
        width=width,
        height=height,
    )
    if existing and not force_regenerate:
        LOGGER.info("duplicate_render_returned content_id=%s render_id=%s", item_id, existing.get("renderId"))
        return normalize_render_result(existing)

    item_render_id = render_id()
    output_dir = (EXPORT_DIR / item_id / item_render_id).resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "output_not_writable", "Output directory is not writable.") from exc
    LOGGER.info("output_directory_prepared content_id=%s render_id=%s", item_id, item_render_id)
    LOGGER.info("template_selected template=%s", template_name)

    content = record["content"]
    render = {
        "contentId": item_id,
        "renderId": item_render_id,
        "status": "rendering",
        "format": output_format,
        "templateName": template_name,
        "width": width,
        "height": height,
        "files": [],
        "errorMessage": "",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    if not isinstance(record.get("renders"), list):
        record["renders"] = []
    record["renders"].append(render)
    record["latestRender"] = render
    record["updatedAt"] = now_iso()
    STORE.save(record)

    renderer_payload = {
        "contentId": item_id,
        "renderId": item_render_id,
        "format": output_format,
        "templateName": template_name,
        "width": width,
        "height": height,
        "outputDir": str(output_dir),
        "brand": {
            "primary": "Annotasi Hikmah",
            "subtitle": "Pengingat singkat untuk Muslim yang sedang bekerja, berjuang, dan memperbaiki hidup.",
            "footer": "Review kembali sebelum upload agar tidak salah konteks.",
        },
        "content": {
            "title": content.get("title", ""),
            "callToAction": content.get("callToAction", ""),
            "sourceCreditSuggestion": content.get("sourceCreditSuggestion", ""),
            "slides": slides,
        },
    }

    try:
        files = call_png_renderer(renderer_payload)
    except AppError as exc:
        render["status"] = "failed"
        render["errorMessage"] = exc.message
        render["updatedAt"] = now_iso()
        record["latestRender"] = render
        record["updatedAt"] = now_iso()
        STORE.save(record)
        raise

    render["status"] = "completed"
    render["files"] = files
    render["updatedAt"] = now_iso()
    record["latestRender"] = render
    record["updatedAt"] = now_iso()
    STORE.save(record)
    LOGGER.info("render_completed content_id=%s render_id=%s files=%d", item_id, item_render_id, len(files))
    return normalize_render_result(render)


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

        render_match = re.fullmatch(r"/api/v1/render/(rnd_\d{8}_[a-f0-9]{8})", path)
        if render_match:
            render = STORE.find_render(render_match.group(1))
            json_response(self, HTTPStatus.OK, normalize_render_result(render))
            return

        video_render_match = re.fullmatch(r"/api/v1/video-render/(vid_\d{8}_[a-f0-9]{8})", path)
        if video_render_match:
            video_render = STORE.find_video_render(video_render_match.group(1))
            json_response(self, HTTPStatus.OK, normalize_video_result(video_render))
            return

        audio_render_match = re.fullmatch(r"/api/v1/audio-render/(aud_\d{8}_[a-f0-9]{8})", path)
        if audio_render_match:
            audio_render = STORE.find_audio_render(audio_render_match.group(1))
            json_response(self, HTTPStatus.OK, normalize_audio_result(audio_render))
            return

        latest_audio_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/audio/latest", path)
        if latest_audio_match:
            record = STORE.get(latest_audio_match.group(1))
            audio_render = record.get("latestAudioRender")
            if not isinstance(audio_render, dict):
                raise AppError(HTTPStatus.NOT_FOUND, "audio_render_not_found", "No audio render exists for this content.")
            json_response(self, HTTPStatus.OK, normalize_audio_result(audio_render))
            return

        latest_video_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/render/video", path)
        if latest_video_match:
            record = STORE.get(latest_video_match.group(1))
            video_render = record.get("latestVideoRender")
            if not isinstance(video_render, dict):
                raise AppError(HTTPStatus.NOT_FOUND, "video_render_not_found", "No video render exists for this content.")
            json_response(self, HTTPStatus.OK, normalize_video_result(video_render))
            return

        png_render_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/render/png", path)
        if png_render_match:
            record = STORE.get(png_render_match.group(1))
            render = record.get("latestRender")
            if not isinstance(render, dict):
                raise AppError(HTTPStatus.NOT_FOUND, "render_not_found", "No PNG render exists for this content.")
            json_response(self, HTTPStatus.OK, normalize_render_result(render))
            return

        match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})(?:/(caption|voiceover|voiceover-script))?", path)
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
        elif view in {"voiceover", "voiceover-script"}:
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
        audio_prepare_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/audio/prepare", path)
        if audio_prepare_match:
            json_response(self, HTTPStatus.OK, prepare_audio_session(audio_prepare_match.group(1)))
            return
        audio_mix_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/audio/mix", path)
        if audio_mix_match:
            json_response(self, HTTPStatus.OK, render_content_audio_mix(audio_mix_match.group(1), body))
            return
        video_render_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/render/video", path)
        if video_render_match:
            json_response(self, HTTPStatus.OK, render_content_video(video_render_match.group(1), body))
            return
        png_render_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/render/png", path)
        if png_render_match:
            json_response(self, HTTPStatus.OK, render_content_png(png_render_match.group(1), body))
            return
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
