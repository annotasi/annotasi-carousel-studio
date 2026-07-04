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
import shutil
import subprocess
import sys
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib import error as urlerror
from urllib import parse as urlparse
from urllib import request as urlrequest
try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.8 fallback.
    ZoneInfo = None  # type: ignore


AI_BASE_URL = os.getenv("AI_BASE_URL", "http://127.0.0.1:20128/v1")
AI_MODEL = os.getenv("AI_MODEL", "annotasi-coding")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "90"))
HOST = os.getenv("ANNOTASI_HOST", "127.0.0.1")
PORT = int(os.getenv("ANNOTASI_PORT", "8097"))
STORAGE_DIR = Path(os.getenv("CONTENT_STORAGE_DIR", "./data/content"))
SOURCE_STORAGE_DIR = Path(os.getenv("SOURCE_STORAGE_DIR", "./data/sources"))
EXPORT_DIR = Path(os.getenv("CONTENT_EXPORT_DIR", "./data/exports"))
PACKAGE_DIR = Path(os.getenv("CONTENT_PACKAGE_DIR", "./data/packages"))
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
CONTENT_TIMEZONE = os.getenv("CONTENT_TIMEZONE", "Asia/Jakarta")
CONTENT_DEFAULT_CALENDAR_DAYS = int(os.getenv("CONTENT_DEFAULT_CALENDAR_DAYS", "7"))
CONTENT_ALLOW_SCHEDULE_REJECTED = os.getenv("CONTENT_ALLOW_SCHEDULE_REJECTED", "false").lower() in {"1", "true", "yes", "on"}
CONTENT_REQUIRE_APPROVAL_BEFORE_SCHEDULE = os.getenv("CONTENT_REQUIRE_APPROVAL_BEFORE_SCHEDULE", "true").lower() in {"1", "true", "yes", "on"}
SOURCE_REQUIRE_APPROVAL_FOR_GENERATION = os.getenv("SOURCE_REQUIRE_APPROVAL_FOR_GENERATION", "false").lower() in {"1", "true", "yes", "on"}
SOURCE_BLOCK_RESTRICTED_GENERATION = os.getenv("SOURCE_BLOCK_RESTRICTED_GENERATION", "true").lower() in {"1", "true", "yes", "on"}
TRANSCRIPT_MAX_CHARS_DIRECT = int(os.getenv("TRANSCRIPT_MAX_CHARS_DIRECT", "12000"))
TRANSCRIPT_SEGMENT_MIN_WORDS = int(os.getenv("TRANSCRIPT_SEGMENT_MIN_WORDS", "300"))
TRANSCRIPT_SEGMENT_MAX_WORDS = int(os.getenv("TRANSCRIPT_SEGMENT_MAX_WORDS", "800"))
SOURCE_DEFAULT_LANGUAGE = os.getenv("SOURCE_DEFAULT_LANGUAGE", "id")
SOURCE_DEFAULT_PERMISSION_STATUS = os.getenv("SOURCE_DEFAULT_PERMISSION_STATUS", "unknown")
CANDIDATE_BLOCK_RESTRICTED_SOURCE = os.getenv("CANDIDATE_BLOCK_RESTRICTED_SOURCE", "true").lower() in {"1", "true", "yes", "on"}
CANDIDATE_ALLOW_UNKNOWN_PERMISSION = os.getenv("CANDIDATE_ALLOW_UNKNOWN_PERMISSION", "true").lower() in {"1", "true", "yes", "on"}
CANDIDATE_ALLOW_HIGH_RISK = os.getenv("CANDIDATE_ALLOW_HIGH_RISK", "false").lower() in {"1", "true", "yes", "on"}
CANDIDATE_DEFAULT_COUNT = int(os.getenv("CANDIDATE_DEFAULT_COUNT", "10"))
CANDIDATE_MAX_TRANSCRIPT_CHARS = int(os.getenv("CANDIDATE_MAX_TRANSCRIPT_CHARS", "30000"))
CANDIDATE_MAX_SEGMENTS_PER_RUN = int(os.getenv("CANDIDATE_MAX_SEGMENTS_PER_RUN", "20"))
CANDIDATE_ALLOWED_TYPES = {
    part.strip().lower()
    for part in os.getenv("CANDIDATE_ALLOWED_TYPES", "carousel,short_video,voiceover_reflection,quote_post,mixed").split(",")
    if part.strip()
}
CONTENT_PACKAGE_CREATE_ZIP = os.getenv("CONTENT_PACKAGE_CREATE_ZIP", "true").lower() in {"1", "true", "yes", "on"}
CONTENT_PACKAGE_REQUIRE_APPROVAL = os.getenv("CONTENT_PACKAGE_REQUIRE_APPROVAL", "true").lower() in {"1", "true", "yes", "on"}
CONTENT_PACKAGE_INCLUDE_METADATA = os.getenv("CONTENT_PACKAGE_INCLUDE_METADATA", "true").lower() in {"1", "true", "yes", "on"}
CONTENT_PACKAGE_INCLUDE_PLATFORM_CAPTIONS = os.getenv("CONTENT_PACKAGE_INCLUDE_PLATFORM_CAPTIONS", "true").lower() in {"1", "true", "yes", "on"}
CONTENT_PACKAGE_TIMEZONE = os.getenv("CONTENT_PACKAGE_TIMEZONE", CONTENT_TIMEZONE)
CONTENT_PACKAGE_MAX_ZIP_SIZE_MB = float(os.getenv("CONTENT_PACKAGE_MAX_ZIP_SIZE_MB", "200"))
CONTENT_PACKAGE_ALLOW_STALE_MEDIA = os.getenv("CONTENT_PACKAGE_ALLOW_STALE_MEDIA", "false").lower() in {"1", "true", "yes", "on"}
TELEGRAM_LIMIT = int(os.getenv("TELEGRAM_MESSAGE_LIMIT", "3900"))
SERVICE_DIR = Path(__file__).resolve().parent
NODE_RENDERER = SERVICE_DIR / "render_png.js"
VALID_WORKFLOW_STATUSES = {
    "idea",
    "generated",
    "needs_review",
    "reviewed",
    "edit_requested",
    "approved",
    "png_rendered",
    "video_rendered",
    "voiceover_ready",
    "scheduled",
    "uploaded",
    "archived",
    "rejected",
}
SCHEDULABLE_STATUSES = {"approved", "png_rendered", "video_rendered", "voiceover_ready", "scheduled", "uploaded"}
SUPPORTED_PLATFORMS = {"instagram", "tiktok", "youtube_shorts", "facebook_reels", "linkedin", "manual"}
SUPPORTED_SOURCE_TYPES = {
    "youtube_video",
    "instagram_video",
    "tiktok_video",
    "podcast",
    "webinar",
    "user_uploaded_video",
    "manual_note",
    "article",
    "book",
    "other",
}
SUPPORTED_SOURCE_PLATFORMS = {"youtube", "instagram", "tiktok", "spotify", "website", "local_file", "manual", "other"}
SUPPORTED_PERMISSION_STATUSES = {
    "unknown",
    "allowed_for_dakwah",
    "allowed_with_credit",
    "own_content",
    "needs_permission",
    "restricted",
    "rejected",
}
SUPPORTED_SOURCE_STATUSES = {"draft", "needs_review", "approved", "restricted", "archived"}
SUPPORTED_TRANSCRIPT_STATUSES = {"available", "draft", "archived"}
SUPPORTED_RISK_LEVELS = {"low", "medium", "high"}
SUPPORTED_CANDIDATE_TYPES = {"carousel", "short_video", "voiceover_reflection", "quote_post", "mixed"}
SUPPORTED_CANDIDATE_STATUSES = {"suggested", "needs_review", "approved", "rejected", "converted_to_content", "archived"}
SUPPORTED_PACKAGE_STATUSES = {"not_started", "packaging", "completed", "failed", "stale"}

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


def local_today() -> date:
    if ZoneInfo:
        try:
            return datetime.now(ZoneInfo(CONTENT_TIMEZONE)).date()
        except Exception:
            pass
    return datetime.now().date()


def parse_date(value: str, field_name: str = "date") -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_schedule_date", f"{field_name} must use YYYY-MM-DD format.") from exc


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


def package_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"pkg_{stamp}_{secrets.token_hex(4)}"


def source_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"src_{stamp}_{secrets.token_hex(4)}"


def transcript_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"tr_{stamp}_{secrets.token_hex(4)}"


def segment_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"seg_{stamp}_{secrets.token_hex(4)}"


def candidate_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"cand_{stamp}_{secrets.token_hex(4)}"


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


def parse_bool(value: Any, default: bool = False) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return default


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

    def list_records(self) -> list[dict[str, Any]]:
        try:
            paths = list(self.root.glob("cnt_*.json"))
        except OSError as exc:
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_failure", "Could not list content.") from exc
        records = []
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                records.append(data)
        records.sort(key=lambda item: str(item.get("createdAt") or item.get("created_at") or ""), reverse=True)
        return records

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

    def find_package(self, item_package_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
        if not re.fullmatch(r"pkg_\d{8}_[a-f0-9]{8}", item_package_id):
            raise AppError(HTTPStatus.BAD_REQUEST, "invalid_package_id", "Package ID format is invalid.")
        for record in self.list_records():
            packages = record.get("packages")
            if not isinstance(packages, list):
                continue
            for item in packages:
                if isinstance(item, dict) and item.get("packageId") == item_package_id:
                    return record, item
        raise AppError(HTTPStatus.NOT_FOUND, "package_not_found", "Package metadata was not found.")


class JsonSourceStore:
    def __init__(self, root: Path):
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def path_for(self, item_id: str) -> Path:
        if not re.fullmatch(r"src_\d{8}_[a-f0-9]{8}", item_id):
            raise AppError(HTTPStatus.BAD_REQUEST, "invalid_source_id", "Source ID format is invalid.")
        return self.root / f"{item_id}.json"

    def save(self, record: dict[str, Any]) -> None:
        path = self.path_for(record["sourceId"])
        tmp = path.with_suffix(".tmp")
        try:
            tmp.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            tmp.replace(path)
        except OSError as exc:
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_failure", "Could not save source.") from exc
        LOGGER.info("source_saved source_id=%s", record["sourceId"])

    def get(self, item_id: str) -> dict[str, Any]:
        path = self.path_for(item_id)
        if not path.exists():
            raise AppError(HTTPStatus.NOT_FOUND, "source_not_found", "Source was not found.")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except OSError as exc:
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_failure", "Could not read source.") from exc
        except json.JSONDecodeError as exc:
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_corrupt", "Stored source is invalid.") from exc
        if not isinstance(data, dict):
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_corrupt", "Stored source is invalid.")
        return data

    def list_records(self) -> list[dict[str, Any]]:
        try:
            paths = list(self.root.glob("src_*.json"))
        except OSError as exc:
            raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "storage_failure", "Could not list sources.") from exc
        records = []
        for path in paths:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(data, dict):
                records.append(data)
        records.sort(key=lambda item: str(item.get("createdAt") or ""), reverse=True)
        return records

    def find_segment(self, item_segment_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        if not re.fullmatch(r"seg_\d{8}_[a-f0-9]{8}", item_segment_id):
            raise AppError(HTTPStatus.BAD_REQUEST, "invalid_segment_id", "Segment ID format is invalid.")
        for source in self.list_records():
            transcript = source.get("transcript")
            if not isinstance(transcript, dict):
                continue
            segments = transcript.get("segments")
            if not isinstance(segments, list):
                continue
            for segment in segments:
                if isinstance(segment, dict) and segment.get("segmentId") == item_segment_id:
                    return source, transcript, segment
        raise AppError(HTTPStatus.NOT_FOUND, "segment_not_found", "Segment was not found.")


STORE = JsonContentStore(STORAGE_DIR)
SOURCE_STORE = JsonSourceStore(SOURCE_STORAGE_DIR)


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


def ideas_from_source_prompt(source: dict[str, Any], transcript_text: str) -> str:
    return f"""Generate 10 safe content ideas from this source.

Source:
- sourceId: {source.get("sourceId")}
- title: {source.get("title")}
- speakerName: {source.get("speakerName")}
- platform: {source.get("platform")}
- sourceUrl: {source.get("sourceUrl")}
- permissionStatus: {source.get("permissionStatus")}
- creditText: {source.get("creditText")}
- contextNotes: {source.get("contextNotes")}

Transcript/context excerpt:
{transcript_text[:6000] or "-"}

Rules:
- Bahasa Indonesia.
- Do not invent Quran verses.
- Do not invent hadith.
- Do not produce fatwa-style conclusions.
- Do not add speaker attribution beyond the source metadata.
- Prefer pengingat, hikmah, renungan, or catatan framing.
- For each idea, mark riskLevel low, medium, or high.
- Mark needsContext true if the idea needs previous/next context.
- sourceCreditRequired should be true unless this is own_content/internal note.

Return JSON only:
{{
  "sourceId": "string",
  "ideas": [
    {{
      "title": "string",
      "angle": "string",
      "suggestedTopic": "string",
      "riskLevel": "low|medium|high",
      "needsContext": true,
      "sourceCreditRequired": true,
      "notes": "string"
    }}
  ],
  "safetyNotes": ["string"]
}}"""


def source_content_prompt(source: dict[str, Any], transcript_text: str, topic: str, segment: Optional[dict[str, Any]] = None) -> str:
    segment_context = ""
    if segment:
        segment_context = f"""
Segment:
- segmentId: {segment.get("segmentId")}
- riskLevel: {segment.get("riskLevel")}
- contextNotes: {segment.get("contextNotes")}
- text: {segment.get("text")}
"""
    return f"""Create one Annotasi Hikmah carousel package from the source context.

Requested topic: {topic or source.get("topic") or source.get("title")}

Source:
- sourceId: {source.get("sourceId")}
- sourceTitle: {source.get("title")}
- speakerName: {source.get("speakerName")}
- sourceUrl: {source.get("sourceUrl")}
- creditText: {source.get("creditText")}
- permissionStatus: {source.get("permissionStatus")}
- sourceStatus: {source.get("sourceStatus")}
- contextNotes: {source.get("contextNotes")}
{segment_context}

Transcript/context:
{transcript_text[:7000] or "-"}

Rules:
- Bahasa Indonesia.
- Do not invent Quran verses.
- Do not invent hadith.
- Do not make fatwa-style conclusions.
- Do not attribute any claim to the speaker unless it is supported by the source context.
- If context is partial, add manual review warning in safetyNotes.
- Always include a source credit suggestion.
- Keep tone calm, reflective, respectful, not clickbait.
- Default to 7 slides, each slide short and readable.

Return JSON only using this schema:
{{
  "title": "string",
  "niche": "string",
  "tone": "string",
  "source": {{
    "sourceId": "string",
    "sourceTitle": "string",
    "speakerName": "string",
    "sourceUrl": "string",
    "creditText": "string",
    "permissionStatus": "string",
    "segmentId": "string|null",
    "riskLevel": "low|medium|high"
  }},
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
}}"""


def highlight_candidates_prompt(
    source: dict[str, Any],
    transcript: dict[str, Any],
    context_text: str,
    *,
    candidate_count: int,
    preferred_types: list[str],
    segment: Optional[dict[str, Any]] = None,
) -> str:
    segment_context = ""
    if segment:
        segment_context = f"""
Focus segment:
- segmentId: {segment.get("segmentId")}
- riskLevel: {segment.get("riskLevel")}
- contextNotes: {segment.get("contextNotes")}
- text: {segment.get("text")}
"""
    return f"""Analyze this source transcript and suggest safe content candidates.

Source:
- sourceId: {source.get("sourceId")}
- title: {source.get("title")}
- speakerName: {source.get("speakerName")}
- sourceUrl: {source.get("sourceUrl")}
- platform: {source.get("platform")}
- permissionStatus: {source.get("permissionStatus")}
- creditText: {source.get("creditText")}

Transcript:
- transcriptId: {transcript.get("transcriptId")}
{segment_context}

Context text:
{context_text[:CANDIDATE_MAX_TRANSCRIPT_CHARS]}

Candidate count: {candidate_count}
Preferred types: {", ".join(preferred_types)}

Safety rules:
- Bahasa Indonesia.
- Do not invent Quran verses.
- Do not invent hadith.
- Do not create fatwa-style conclusions.
- Do not attribute anything to a speaker unless it exists in source metadata/transcript.
- Do not exaggerate or clickbait.
- Do not cut meaning out of context.
- For medium/high risk candidates, include contextWarning.
- aiReasoningSummary must be short and user-safe; do not include hidden chain-of-thought.
- Prefer hikmah, renungan, catatan, or pengingat framing.

Return JSON only:
{{
  "sourceId": "string",
  "transcriptId": "string",
  "analysisSummary": "string",
  "candidates": [
    {{
      "candidateType": "carousel|short_video|voiceover_reflection|quote_post|mixed",
      "segmentId": "string|null",
      "title": "string",
      "hook": "string",
      "angle": "string",
      "summary": "string",
      "suggestedFormat": "string",
      "suggestedDurationSeconds": 45,
      "riskLevel": "low|medium|high",
      "needsContext": true,
      "contextWarning": "string",
      "sourceCreditSuggestion": "string",
      "aiReasoningSummary": "string"
    }}
  ],
  "safetyNotes": ["string"]
}}"""


def candidate_content_prompt(source: dict[str, Any], transcript: dict[str, Any], candidate: dict[str, Any], segment: Optional[dict[str, Any]]) -> str:
    segment_text = str(segment.get("text") or "") if segment else ""
    transcript_excerpt = str(transcript.get("transcriptText") or "")[:5000]
    return f"""Generate one Annotasi Hikmah carousel package from this approved content candidate.

Candidate:
- candidateId: {candidate.get("candidateId")}
- type: {candidate.get("candidateType")}
- title: {candidate.get("title")}
- hook: {candidate.get("hook")}
- angle: {candidate.get("angle")}
- summary: {candidate.get("summary")}
- riskLevel: {candidate.get("riskLevel")}
- needsContext: {candidate.get("needsContext")}
- contextWarning: {candidate.get("contextWarning")}

Source:
- sourceId: {source.get("sourceId")}
- sourceTitle: {source.get("title")}
- speakerName: {source.get("speakerName")}
- sourceUrl: {source.get("sourceUrl")}
- creditText: {source.get("creditText")}
- permissionStatus: {source.get("permissionStatus")}
- segmentId: {candidate.get("segmentId") or ""}

Segment/context:
{segment_text or transcript_excerpt}

Rules:
- Bahasa Indonesia.
- Do not invent Quran verses.
- Do not invent hadith.
- Do not make fatwa-style conclusions.
- Do not add claims beyond the source context.
- Keep calm, reflective, respectful, not clickbait.
- Include source credit suggestion.
- Content status will be needs_review; do not auto-approve.

Return JSON only using this schema:
{{
  "title": "string",
  "niche": "string",
  "tone": "string",
  "source": {{
    "sourceId": "string",
    "sourceTitle": "string",
    "speakerName": "string",
    "sourceUrl": "string",
    "creditText": "string",
    "permissionStatus": "string",
    "segmentId": "string|null",
    "candidateId": "string",
    "riskLevel": "low|medium|high"
  }},
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
}}"""


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


def is_dakwah_content(record: dict[str, Any]) -> bool:
    niche = str(record.get("niche") or record.get("content", {}).get("niche") or "").lower()
    topic = str(record.get("topic") or "").lower()
    return any(marker in f"{niche} {topic}" for marker in ["hikmah", "muslim", "dakwah", "annotasi_hikmah"])


def review_checklist(record: dict[str, Any]) -> list[dict[str, Any]]:
    if is_dakwah_content(record):
        items = [
            "Source/context checked",
            "No invented Quran/hadith",
            "No misleading attribution",
            "No wrong context",
            "Title not clickbait",
            "Caption respectful",
            "Visual appropriate",
            "Voiceover own voice",
            "Ready before upload",
        ]
    else:
        items = [
            "Hook is clear",
            "Content is useful",
            "No misleading claim",
            "Caption is ready",
            "CTA is appropriate",
            "Format fits selected platform",
        ]
    checked = set(record.get("workflow", {}).get("checkedItems") or [])
    return [{"label": item, "checked": item in checked} for item in items]


def ensure_workflow(record: dict[str, Any]) -> dict[str, Any]:
    workflow = record.get("workflow")
    if not isinstance(workflow, dict):
        workflow = {}
        record["workflow"] = workflow
    status = str(workflow.get("status") or record.get("status") or "generated")
    if status not in VALID_WORKFLOW_STATUSES:
        status = "generated"
    workflow.setdefault("status", status)
    workflow.setdefault("reviewStatus", "not_reviewed")
    workflow.setdefault("reviewNotes", "")
    workflow.setdefault("rejectionReason", "")
    workflow.setdefault("approvedAt", "")
    workflow.setdefault("approvedBy", "")
    workflow.setdefault("scheduledDate", "")
    workflow.setdefault("scheduledTime", "")
    workflow.setdefault("scheduledPlatform", "")
    workflow.setdefault("scheduledTimezone", CONTENT_TIMEZONE)
    workflow.setdefault("uploadedAt", "")
    workflow.setdefault("uploadedPlatform", "")
    workflow.setdefault("uploadedUrl", "")
    workflow.setdefault("lastEditedAt", "")
    workflow.setdefault("renderStale", {"png": False, "video": False, "audio": False})
    record["status"] = workflow["status"]
    return workflow


def set_workflow_status(record: dict[str, Any], status: str) -> None:
    if status not in VALID_WORKFLOW_STATUSES:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_status", "Workflow status is invalid.")
    workflow = ensure_workflow(record)
    workflow["status"] = status
    record["status"] = status
    record["updatedAt"] = now_iso()


def mark_render_stale(record: dict[str, Any], *, png: bool = False, video: bool = False, audio: bool = False) -> None:
    workflow = ensure_workflow(record)
    stale = workflow.get("renderStale")
    if not isinstance(stale, dict):
        stale = {"png": False, "video": False, "audio": False}
        workflow["renderStale"] = stale
    stale["png"] = bool(stale.get("png") or png)
    stale["video"] = bool(stale.get("video") or video)
    stale["audio"] = bool(stale.get("audio") or audio)
    LOGGER.info("render_marked_stale content_id=%s png=%s video=%s audio=%s", record.get("id"), stale["png"], stale["video"], stale["audio"])


def clear_render_stale(record: dict[str, Any], kind: str) -> None:
    stale = ensure_workflow(record).get("renderStale")
    if isinstance(stale, dict) and kind in stale:
        stale[kind] = False


def latest_package(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    packages = record.get("packages")
    if not isinstance(packages, list):
        return None
    for item in reversed(packages):
        if isinstance(item, dict):
            return item
    return None


def package_summary(record: dict[str, Any]) -> dict[str, Any]:
    package = latest_package(record)
    if not package:
        return {"status": "not_started", "packageId": "", "packageDir": "", "zipPath": "", "stale": False}
    stale = package.get("status") == "stale"
    return {
        "status": package.get("status", "not_started"),
        "packageId": package.get("packageId", ""),
        "packageDir": package.get("packageDir", ""),
        "zipPath": package.get("zipPath", ""),
        "stale": stale,
    }


def mark_packages_stale(record: dict[str, Any]) -> None:
    packages = record.get("packages")
    if not isinstance(packages, list):
        return
    changed = False
    for item in packages:
        if isinstance(item, dict) and item.get("status") == "completed":
            item["status"] = "stale"
            item["updatedAt"] = now_iso()
            changed = True
    if changed:
        LOGGER.info("packages_marked_stale content_id=%s", record.get("id"))


def append_edit_history(record: dict[str, Any], field_name: str, old_value: Any, new_value: Any, edited_by: str = "internal") -> None:
    history = record.get("editHistory")
    if not isinstance(history, list):
        history = []
        record["editHistory"] = history
    history.append(
        {
            "editId": f"edt_{datetime.now(timezone.utc).strftime('%Y%m%d')}_{secrets.token_hex(4)}",
            "contentId": record.get("id"),
            "fieldName": field_name,
            "oldValue": old_value,
            "newValue": new_value,
            "editedAt": now_iso(),
            "editedBy": edited_by,
        }
    )
    ensure_workflow(record)["lastEditedAt"] = now_iso()
    mark_packages_stale(record)


def media_status(record: dict[str, Any], key: str, latest_key: str) -> str:
    latest = record.get(latest_key)
    stale = ensure_workflow(record).get("renderStale", {})
    if isinstance(latest, dict) and latest.get("status") == "completed":
        if isinstance(stale, dict) and stale.get(key):
            return "stale"
        return "completed"
    return "not_started"


def workflow_summary(record: dict[str, Any]) -> dict[str, Any]:
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    workflow = ensure_workflow(record)
    return {
        "id": record.get("id"),
        "title": content.get("title", ""),
        "topic": record.get("topic", ""),
        "niche": record.get("niche", ""),
        "status": workflow.get("status"),
        "png": media_status(record, "png", "latestRender"),
        "video": media_status(record, "video", "latestVideoRender"),
        "voiceover": media_status(record, "audio", "latestAudioRender"),
        "schedule": {
            "date": workflow.get("scheduledDate", ""),
            "time": workflow.get("scheduledTime", ""),
            "platform": workflow.get("scheduledPlatform", ""),
            "timezone": workflow.get("scheduledTimezone", CONTENT_TIMEZONE),
        },
        "uploaded": {
            "at": workflow.get("uploadedAt", ""),
            "platform": workflow.get("uploadedPlatform", ""),
            "url": workflow.get("uploadedUrl", ""),
        },
        "package": package_summary(record),
        "renderStale": workflow.get("renderStale", {}),
    }


def format_review_for_telegram(record: dict[str, Any]) -> list[str]:
    summary = workflow_summary(record)
    checklist = review_checklist(record)
    slides = record.get("content", {}).get("slides") if isinstance(record.get("content"), dict) else []
    lines = [
        "Review Content",
        "",
        "Content ID:",
        str(summary["id"]),
        "",
        "Title:",
        str(summary["title"]),
        "",
        "Status:",
        str(summary["status"]),
        "",
        "Slides:",
        f"{len(slides) if isinstance(slides, list) else 0} slides",
        "",
    ]
    link = record.get("sourceLink")
    if isinstance(link, dict) and link.get("sourceId"):
        try:
            linked_source = SOURCE_STORE.get(str(link["sourceId"]))
            candidate_link = record.get("candidateLink")
            linked_candidate = None
            if isinstance(candidate_link, dict) and candidate_link.get("candidateId"):
                try:
                    _source, linked_candidate = find_candidate(str(candidate_link["candidateId"]))
                except AppError:
                    linked_candidate = None
            lines.extend(
                [
                    "Source:",
                    f"{linked_source.get('sourceId')} - {linked_source.get('title')}",
                    "",
                    "Speaker:",
                    str(linked_source.get("speakerName") or "-"),
                    "",
                    "Permission:",
                    str(linked_source.get("permissionStatus") or "-"),
                    "",
                    "Credit:",
                    str(linked_source.get("creditText") or "-"),
                    "",
                    "Segment:",
                    str(link.get("segmentId") or "none"),
                    "",
                    "Risk:",
                    str(link.get("riskLevel") or "medium"),
                    "",
                ]
            )
            if linked_candidate:
                lines.extend(
                    [
                        "Candidate:",
                        str(linked_candidate.get("candidateId")),
                        "",
                        "Candidate type:",
                        str(linked_candidate.get("candidateType")),
                        "",
                        "Candidate risk:",
                        str(linked_candidate.get("riskLevel")),
                        "",
                        "Needs context:",
                        "yes" if linked_candidate.get("needsContext") else "no",
                        "",
                        "Context warning:",
                        str(linked_candidate.get("contextWarning") or "-"),
                        "",
                        "Candidate checklist:",
                        "[ ] Candidate context reviewed",
                        "[ ] Candidate risk level checked",
                        "[ ] Source credit included",
                        "[ ] Segment meaning not changed",
                        "[ ] Hook is not clickbait",
                        "[ ] Generated content matches candidate angle",
                        "",
                    ]
                )
            lines.extend(
                [
                    "Source checklist:",
                    "[ ] Source is linked",
                    "[ ] Credit text is included",
                    "[ ] Permission status reviewed",
                    "[ ] Segment context reviewed",
                    "[ ] No meaning is cut out of context",
                    "",
                ]
            )
        except AppError:
            lines.extend(["Source:", f"{link.get('sourceId')} (not found)", ""])
    else:
        lines.extend(
            [
                "Source:",
                "Content has no linked source. If inspired by kajian/video, add source before posting.",
                "",
            ]
        )
    lines.append("Checklist:")
    for item in checklist:
        marker = "[x]" if item["checked"] else "[ ]"
        lines.append(f"{marker} {item['label']}")
    lines.extend(
        [
            "",
            "Available actions:",
            f"/approve {summary['id']}",
            f"/reject {summary['id']} <reason>",
            f"/edit_slide {summary['id']} 3 <new text>",
            f"/edit_caption {summary['id']} <new caption>",
            f"/status {summary['id']}",
            "",
            "Reminder:",
            "Review kembali sebelum upload agar tidak salah konteks.",
        ]
    )
    return split_telegram_message("\n".join(lines).strip())


def format_status_for_telegram(record: dict[str, Any]) -> list[str]:
    summary = workflow_summary(record)
    schedule = summary["schedule"]
    uploaded = summary["uploaded"]
    package = summary["package"]
    schedule_text = "not scheduled"
    if schedule["date"]:
        schedule_text = f"{schedule['date']} {schedule['time'] or ''} {schedule['platform']}".strip()
    uploaded_text = "no"
    if uploaded["at"]:
        uploaded_text = f"yes ({uploaded['platform']}) {uploaded['url']}".strip()
    text = "\n".join(
        [
            "Content Status",
            "",
            "Content ID:",
            str(summary["id"]),
            "",
            "Status:",
            str(summary["status"]),
            "",
            "PNG:",
            str(summary["png"]),
            "",
            "Video:",
            str(summary["video"]),
            "",
            "Voiceover:",
            str(summary["voiceover"]),
            "",
            "Package:",
            str(package.get("status") or "not_started"),
            "",
            "Schedule:",
            schedule_text,
            "",
            "Uploaded:",
            uploaded_text,
        ]
    )
    return split_telegram_message(text)


def format_calendar_for_telegram(items: list[dict[str, Any]], title: str, empty_message: str) -> list[str]:
    if not items:
        return [empty_message]
    lines = [title, ""]
    for index, record in enumerate(items, start=1):
        summary = workflow_summary(record)
        schedule = summary["schedule"]
        lines.extend(
            [
                f"{index}. {summary['id']}",
                f"Title: {summary['title']}",
                f"Date: {schedule['date']}",
                f"Platform: {schedule['platform']}",
                f"Status: {summary['status']}",
                "",
            ]
        )
    return split_telegram_message("\n".join(lines).strip())


def format_content_list_for_telegram(records: list[dict[str, Any]], status: str = "") -> list[str]:
    lines = ["Content List", "", "Status:", status or "all", ""]
    if not records:
        lines.append("No content found.")
        return split_telegram_message("\n".join(lines).strip())
    for index, record in enumerate(records, start=1):
        summary = workflow_summary(record)
        lines.append(f"{index}. {summary['id']} - {summary['title']} ({summary['status']})")
    return split_telegram_message("\n".join(lines).strip())


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
    stale = ensure_workflow(record).get("renderStale", {})
    if isinstance(stale, dict) and stale.get("png"):
        return None
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
    stale = ensure_workflow(record).get("renderStale", {})
    if isinstance(stale, dict) and stale.get("audio"):
        return None
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
    stale = ensure_workflow(record).get("renderStale", {})
    if isinstance(stale, dict) and stale.get("video"):
        return None
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
    stale = ensure_workflow(record).get("renderStale", {})
    if isinstance(stale, dict) and stale.get("png"):
        return None
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
    clear_render_stale(record, "audio")
    if ensure_workflow(record).get("status") not in {"scheduled", "uploaded", "archived", "rejected"}:
        set_workflow_status(record, "voiceover_ready")
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
    clear_render_stale(record, "video")
    if ensure_workflow(record).get("status") not in {"scheduled", "uploaded", "archived", "rejected"}:
        set_workflow_status(record, "video_rendered")
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
    clear_render_stale(record, "png")
    if ensure_workflow(record).get("status") not in {"scheduled", "uploaded", "archived", "rejected"}:
        set_workflow_status(record, "png_rendered")
    record["updatedAt"] = now_iso()
    STORE.save(record)
    LOGGER.info("render_completed content_id=%s render_id=%s files=%d", item_id, item_render_id, len(files))
    return normalize_render_result(render)


def get_review(item_id: str) -> dict[str, Any]:
    LOGGER.info("review_requested content_id=%s", item_id)
    record = STORE.get(item_id)
    ensure_workflow(record)
    return {
        "contentId": item_id,
        "summary": workflow_summary(record),
        "checklist": review_checklist(record),
        "telegramMessages": format_review_for_telegram(record),
    }


def get_content_status(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    return {"contentId": item_id, "summary": workflow_summary(record), "telegramMessages": format_status_for_telegram(record)}


def approve_content(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    record = STORE.get(item_id)
    workflow = ensure_workflow(record)
    if workflow.get("status") == "rejected":
        raise AppError(HTTPStatus.CONFLICT, "cannot_approve_rejected", "Change status before approving rejected content.")
    workflow["reviewStatus"] = "approved"
    workflow["reviewNotes"] = str(body.get("notes") or "").strip()
    workflow["approvedBy"] = str(body.get("reviewedBy") or "internal").strip()
    workflow["approvedAt"] = now_iso()
    set_workflow_status(record, "approved")
    STORE.save(record)
    LOGGER.info("content_approved content_id=%s", item_id)
    text = "\n".join(
        [
            "Content approved.",
            "",
            "Content ID:",
            item_id,
            "",
            "Next actions:",
            f"/render {item_id}",
            f"/video {item_id}",
            f"/schedule {item_id} 2026-07-05 instagram",
        ]
    )
    return {"contentId": item_id, "summary": workflow_summary(record), "telegramMessages": split_telegram_message(text)}


def reject_content(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    reason = str(body.get("reason") or "").strip()
    if not reason:
        raise AppError(HTTPStatus.BAD_REQUEST, "missing_rejection_reason", "Rejection reason is required.")
    record = STORE.get(item_id)
    workflow = ensure_workflow(record)
    workflow["reviewStatus"] = "rejected"
    workflow["rejectionReason"] = reason
    set_workflow_status(record, "rejected")
    STORE.save(record)
    LOGGER.info("content_rejected content_id=%s", item_id)
    text = "\n".join(["Content rejected.", "", "Reason:", reason, "", "Status:", "rejected"])
    return {"contentId": item_id, "summary": workflow_summary(record), "telegramMessages": split_telegram_message(text)}


def update_content_status(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    status = str(body.get("status") or "").strip()
    record = STORE.get(item_id)
    set_workflow_status(record, status)
    STORE.save(record)
    return get_content_status(item_id)


def edit_slide(item_id: str, slide_number: int, body: dict[str, Any]) -> dict[str, Any]:
    new_text = str(body.get("text") or "").strip()
    if not new_text:
        raise AppError(HTTPStatus.BAD_REQUEST, "empty_edit_text", "Slide text cannot be empty.")
    record = STORE.get(item_id)
    slides = validate_renderable_content(record)
    if not 1 <= slide_number <= len(slides):
        raise AppError(HTTPStatus.NOT_FOUND, "slide_not_found", "Slide number was not found.")
    slide = slides[slide_number - 1]
    old_text = str(slide.get("text") or "")
    slide["text"] = new_text
    append_edit_history(record, f"slides.{slide_number}.text", old_text, new_text, str(body.get("editedBy") or "internal"))
    mark_render_stale(record, png=True, video=True, audio=True)
    set_workflow_status(record, "needs_review")
    STORE.save(record)
    LOGGER.info("slide_edited content_id=%s slide=%d", item_id, slide_number)
    text = "\n".join(
        [
            "Slide updated.",
            "",
            "Content ID:",
            item_id,
            "",
            "Slide:",
            str(slide_number),
            "",
            "New text:",
            new_text,
            "",
            "Status:",
            "needs_review",
            "",
            "Reminder:",
            "Render ulang PNG dan video setelah edit.",
        ]
    )
    return {"contentId": item_id, "slideNumber": slide_number, "summary": workflow_summary(record), "telegramMessages": split_telegram_message(text)}


def edit_caption(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    new_caption = str(body.get("caption") or "").strip()
    if not new_caption:
        raise AppError(HTTPStatus.BAD_REQUEST, "empty_edit_text", "Caption cannot be empty.")
    record = STORE.get(item_id)
    content = record.get("content")
    if not isinstance(content, dict):
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_content", "Content package is invalid.")
    old_caption = str(content.get("caption") or "")
    content["caption"] = new_caption
    append_edit_history(record, "caption", old_caption, new_caption, str(body.get("editedBy") or "internal"))
    set_workflow_status(record, "needs_review")
    STORE.save(record)
    LOGGER.info("caption_edited content_id=%s", item_id)
    return {"contentId": item_id, "summary": workflow_summary(record), "telegramMessages": split_telegram_message(f"Caption updated.\n\nContent ID:\n{item_id}\n\nStatus:\nneeds_review")}


def edit_voiceover(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    new_script = str(body.get("voiceoverScript") or "").strip()
    if not new_script:
        raise AppError(HTTPStatus.BAD_REQUEST, "empty_edit_text", "Voiceover script cannot be empty.")
    record = STORE.get(item_id)
    content = record.get("content")
    if not isinstance(content, dict):
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_content", "Content package is invalid.")
    old_script = str(content.get("voiceoverScript") or "")
    content["voiceoverScript"] = new_script
    append_edit_history(record, "voiceoverScript", old_script, new_script, str(body.get("editedBy") or "internal"))
    mark_render_stale(record, audio=True)
    set_workflow_status(record, "needs_review")
    STORE.save(record)
    LOGGER.info("voiceover_edited content_id=%s", item_id)
    return {"contentId": item_id, "summary": workflow_summary(record), "telegramMessages": split_telegram_message(f"Voiceover script updated.\n\nContent ID:\n{item_id}\n\nStatus:\nneeds_review")}


def validate_platform(platform: str) -> str:
    normalized = platform.strip().lower()
    if normalized not in SUPPORTED_PLATFORMS:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_platform", "Platform is invalid.")
    return normalized


def schedule_content(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    platform = validate_platform(str(body.get("platform") or ""))
    scheduled_date = parse_date(str(body.get("scheduledDate") or ""))
    scheduled_time = str(body.get("scheduledTime") or "").strip()
    tz = str(body.get("timezone") or CONTENT_TIMEZONE).strip()
    record = STORE.get(item_id)
    workflow = ensure_workflow(record)
    if workflow.get("status") == "rejected" and not CONTENT_ALLOW_SCHEDULE_REJECTED:
        raise AppError(HTTPStatus.CONFLICT, "cannot_schedule_rejected", "Rejected content cannot be scheduled.")
    if CONTENT_REQUIRE_APPROVAL_BEFORE_SCHEDULE and workflow.get("status") not in SCHEDULABLE_STATUSES:
        raise AppError(HTTPStatus.CONFLICT, "approval_required", "Approve content before scheduling.")
    if workflow.get("scheduledDate") and workflow.get("scheduledPlatform"):
        raise AppError(HTTPStatus.CONFLICT, "duplicate_schedule", "Content is already scheduled. Unschedule it first.")
    workflow["scheduledDate"] = scheduled_date.isoformat()
    workflow["scheduledTime"] = scheduled_time
    workflow["scheduledPlatform"] = platform
    workflow["scheduledTimezone"] = tz
    set_workflow_status(record, "scheduled")
    STORE.save(record)
    LOGGER.info("content_scheduled content_id=%s date=%s platform=%s", item_id, scheduled_date.isoformat(), platform)
    text = "\n".join(["Content scheduled.", "", "Content ID:", item_id, "", "Date:", scheduled_date.isoformat(), "", "Platform:", platform, "", "Status:", "scheduled"])
    return {"contentId": item_id, "summary": workflow_summary(record), "telegramMessages": split_telegram_message(text)}


def unschedule_content(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    workflow = ensure_workflow(record)
    workflow["scheduledDate"] = ""
    workflow["scheduledTime"] = ""
    workflow["scheduledPlatform"] = ""
    if workflow.get("status") == "scheduled":
        set_workflow_status(record, "approved")
    else:
        record["updatedAt"] = now_iso()
    STORE.save(record)
    LOGGER.info("content_unscheduled content_id=%s", item_id)
    return {"contentId": item_id, "summary": workflow_summary(record), "telegramMessages": split_telegram_message(f"Content unscheduled.\n\nContent ID:\n{item_id}")}


def mark_uploaded(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    platform = validate_platform(str(body.get("platform") or ""))
    record = STORE.get(item_id)
    workflow = ensure_workflow(record)
    workflow["uploadedPlatform"] = platform
    workflow["uploadedUrl"] = str(body.get("url") or "").strip()
    workflow["uploadedAt"] = str(body.get("uploadedAt") or now_iso()).strip()
    set_workflow_status(record, "uploaded")
    STORE.save(record)
    LOGGER.info("content_marked_uploaded content_id=%s platform=%s", item_id, platform)
    text = "\n".join(["Content marked as uploaded.", "", "Content ID:", item_id, "", "Platform:", platform, "", "URL:", workflow["uploadedUrl"] or "-", "", "Status:", "uploaded"])
    return {"contentId": item_id, "summary": workflow_summary(record), "telegramMessages": split_telegram_message(text)}


def calendar_items(from_date: date, to_date: date, platform: str = "", status: str = "") -> list[dict[str, Any]]:
    items = []
    for record in STORE.list_records():
        workflow = ensure_workflow(record)
        scheduled = str(workflow.get("scheduledDate") or "")
        if not scheduled:
            continue
        try:
            item_date = date.fromisoformat(scheduled)
        except ValueError:
            continue
        if item_date < from_date or item_date > to_date:
            continue
        if platform and workflow.get("scheduledPlatform") != platform:
            continue
        if status and workflow.get("status") != status:
            continue
        items.append(record)
    items.sort(key=lambda item: (ensure_workflow(item).get("scheduledDate") or "", ensure_workflow(item).get("scheduledTime") or ""))
    return items


def query_calendar(params: dict[str, list[str]]) -> dict[str, Any]:
    today = local_today()
    from_value = params.get("from", [today.isoformat()])[0]
    to_value = params.get("to", [(today + timedelta(days=CONTENT_DEFAULT_CALENDAR_DAYS - 1)).isoformat()])[0]
    from_date = parse_date(from_value, "from")
    to_date = parse_date(to_value, "to")
    if to_date < from_date:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_date_range", "Calendar to date must be after from date.")
    platform = params.get("platform", [""])[0].strip().lower()
    if platform:
        platform = validate_platform(platform)
    status = params.get("status", [""])[0].strip()
    if status and status not in VALID_WORKFLOW_STATUSES:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_status", "Workflow status is invalid.")
    LOGGER.info("calendar_requested from=%s to=%s", from_date.isoformat(), to_date.isoformat())
    items = calendar_items(from_date, to_date, platform, status)
    title = f"Content Calendar\n\n{from_date.isoformat()} to {to_date.isoformat()}"
    return {
        "from": from_date.isoformat(),
        "to": to_date.isoformat(),
        "items": [workflow_summary(item) for item in items],
        "telegramMessages": format_calendar_for_telegram(items, title, "Calendar has no scheduled content."),
    }


def list_content_by_status(status: str = "", limit: int = 20) -> dict[str, Any]:
    if status and status != "packaged" and status not in VALID_WORKFLOW_STATUSES:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_status", "Workflow status is invalid.")
    records = []
    for record in STORE.list_records():
        workflow = ensure_workflow(record)
        if status == "packaged":
            package = latest_package(record)
            if not package or package.get("status") not in {"completed", "stale"}:
                continue
        elif status and workflow.get("status") != status:
            continue
        records.append(record)
        if len(records) >= limit:
            break
    return {
        "status": status or "all",
        "items": [workflow_summary(record) for record in records],
        "telegramMessages": format_content_list_for_telegram(records, status),
    }


def validate_source_type(value: str) -> str:
    normalized = (value or "other").strip().lower()
    if normalized not in SUPPORTED_SOURCE_TYPES:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_source_type", "Source type is invalid.")
    return normalized


def validate_source_platform(value: str) -> str:
    normalized = (value or "other").strip().lower()
    if normalized not in SUPPORTED_SOURCE_PLATFORMS:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_source_platform", "Source platform is invalid.")
    return normalized


def validate_permission_status(value: str) -> str:
    normalized = (value or SOURCE_DEFAULT_PERMISSION_STATUS).strip().lower()
    if normalized not in SUPPORTED_PERMISSION_STATUSES:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_permission_status", "Permission status is invalid.")
    return normalized


def validate_source_status(value: str) -> str:
    normalized = (value or "draft").strip().lower()
    if normalized not in SUPPORTED_SOURCE_STATUSES:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_source_status", "Source status is invalid.")
    return normalized


def validate_risk_level(value: str) -> str:
    normalized = (value or "low").strip().lower()
    if normalized not in SUPPORTED_RISK_LEVELS:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_risk_level", "Risk level is invalid.")
    return normalized


def validate_candidate_type(value: str) -> str:
    normalized = (value or "mixed").strip().lower()
    if normalized not in SUPPORTED_CANDIDATE_TYPES:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_candidate_type", "Candidate type is invalid.")
    return normalized


def validate_candidate_status(value: str) -> str:
    normalized = (value or "suggested").strip().lower()
    if normalized not in SUPPORTED_CANDIDATE_STATUSES:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_candidate_status", "Candidate status is invalid.")
    return normalized


def source_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = source.get("candidates")
    return candidates if isinstance(candidates, list) else []


def candidate_counts(source: dict[str, Any]) -> dict[str, int]:
    counts = {"total": 0, "approved": 0, "converted_to_content": 0, "rejected": 0}
    for candidate in source_candidates(source):
        counts["total"] += 1
        status = str(candidate.get("candidateStatus") or "")
        if status in counts:
            counts[status] += 1
    return counts


def source_summary(source: dict[str, Any]) -> dict[str, Any]:
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
    segments = transcript.get("segments") if isinstance(transcript, dict) else []
    links = source.get("generatedContent") if isinstance(source.get("generatedContent"), list) else []
    counts = candidate_counts(source)
    return {
        "sourceId": source.get("sourceId"),
        "title": source.get("title", ""),
        "speakerName": source.get("speakerName", ""),
        "sourceType": source.get("sourceType", ""),
        "platform": source.get("platform", ""),
        "sourceUrl": source.get("sourceUrl", ""),
        "permissionStatus": source.get("permissionStatus", ""),
        "creditText": source.get("creditText", ""),
        "topic": source.get("topic", ""),
        "sourceStatus": source.get("sourceStatus", ""),
        "transcriptAvailable": bool(transcript.get("transcriptText")),
        "segmentCount": len(segments) if isinstance(segments, list) else 0,
        "generatedContentCount": len(links),
        "candidateCount": counts["total"],
        "approvedCandidateCount": counts["approved"],
        "convertedCandidateCount": counts["converted_to_content"],
        "rejectedCandidateCount": counts["rejected"],
        "contextNotes": source.get("contextNotes", ""),
    }


def format_source_list_for_telegram(sources: list[dict[str, Any]]) -> list[str]:
    if not sources:
        return ["Source List\n\nNo sources found."]
    lines = ["Source List", ""]
    for index, source in enumerate(sources, start=1):
        summary = source_summary(source)
        lines.extend(
            [
                f"{index}. {summary['sourceId']} - {summary['title']}",
                f"Speaker: {summary['speakerName'] or '-'}",
                f"Permission: {summary['permissionStatus']}",
                f"Status: {summary['sourceStatus']}",
                "",
            ]
        )
    return split_telegram_message("\n".join(lines).strip())


def format_source_detail_for_telegram(source: dict[str, Any]) -> list[str]:
    summary = source_summary(source)
    transcript_status = "available" if summary["transcriptAvailable"] else "not_available"
    text = "\n".join(
        [
            "Source Detail",
            "",
            "Source ID:",
            str(summary["sourceId"]),
            "",
            "Title:",
            str(summary["title"]),
            "",
            "Speaker:",
            str(summary["speakerName"] or "-"),
            "",
            "URL:",
            str(summary["sourceUrl"] or "-"),
            "",
            "Permission:",
            str(summary["permissionStatus"]),
            "",
            "Credit:",
            str(summary["creditText"] or "-"),
            "",
            "Status:",
            str(summary["sourceStatus"]),
            "",
            "Transcript:",
            transcript_status,
            "",
            "Generated content:",
            f"{summary['generatedContentCount']} items",
            "",
            "Candidates:",
            f"{summary['candidateCount']} total, {summary['approvedCandidateCount']} approved, {summary['convertedCandidateCount']} converted, {summary['rejectedCandidateCount']} rejected",
            "",
            "Notes:",
            str(summary["contextNotes"] or "-"),
        ]
    )
    return split_telegram_message(text)


def format_source_review_for_telegram(source: dict[str, Any]) -> list[str]:
    checklist = [
        "Source URL is valid",
        "Speaker/source is clear",
        "Permission status is checked",
        "Credit text is ready",
        "Topic is appropriate",
        "No misleading use intended",
        "Not a restricted source",
        "Monetization risk understood",
        "Manual context review required before posting",
    ]
    lines = [
        "Source Review",
        "",
        "Source ID:",
        str(source.get("sourceId")),
        "",
        "Title:",
        str(source.get("title", "")),
        "",
        "Permission:",
        str(source.get("permissionStatus", "")),
        "",
        "Checklist:",
    ]
    lines.extend([f"[ ] {item}" for item in checklist])
    lines.extend(
        [
            "",
            "Reminder:",
            "Boleh disebarkan untuk dakwah belum tentu otomatis aman untuk monetisasi. Tetap beri sumber dan nilai tambah.",
        ]
    )
    return split_telegram_message("\n".join(lines).strip())


def format_transcript_summary_for_telegram(source: dict[str, Any]) -> list[str]:
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
    text = str(transcript.get("transcriptText") or "")
    segments = transcript.get("segments") if isinstance(transcript.get("segments"), list) else []
    preview = text[:500] + ("..." if len(text) > 500 else "")
    lines = [
        "Transcript Summary",
        "",
        "Source ID:",
        str(source.get("sourceId")),
        "",
        "Transcript ID:",
        str(transcript.get("transcriptId") or "-"),
        "",
        "Length:",
        f"{len(text)} characters",
        "",
        "Segments:",
        str(len(segments)),
        "",
        "Status:",
        str(transcript.get("transcriptStatus") or "not_available"),
        "",
        "Preview:",
        preview or "-",
    ]
    return split_telegram_message("\n".join(lines).strip())


def time_label(seconds: Any) -> str:
    if seconds is None:
        return "unknown"
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "unknown"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def format_segments_for_telegram(source: dict[str, Any]) -> list[str]:
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
    segments = transcript.get("segments") if isinstance(transcript.get("segments"), list) else []
    if not segments:
        return ["Transcript Segments\n\nNo segments found."]
    lines = ["Transcript Segments", ""]
    for index, segment in enumerate(segments, start=1):
        preview = str(segment.get("text") or "")[:180]
        lines.extend(
            [
                f"{index}. {segment.get('segmentId')}",
                f"Time: {time_label(segment.get('startTimeSeconds'))} - {time_label(segment.get('endTimeSeconds'))}",
                f"Topic: {segment.get('topic') or '-'}",
                f"Risk: {segment.get('riskLevel')}",
                f"Preview: {preview}",
                "",
            ]
        )
    return split_telegram_message("\n".join(lines).strip())


def format_segment_detail_for_telegram(source: dict[str, Any], segment: dict[str, Any]) -> list[str]:
    linked_count = sum(1 for candidate in source_candidates(source) if candidate.get("segmentId") == segment.get("segmentId"))
    text = "\n".join(
        [
            "Segment Detail",
            "",
            "Segment ID:",
            str(segment.get("segmentId")),
            "",
            "Source:",
            str(source.get("sourceId")),
            "",
            "Time:",
            f"{time_label(segment.get('startTimeSeconds'))} - {time_label(segment.get('endTimeSeconds'))}",
            "",
            "Risk:",
            str(segment.get("riskLevel")),
            "",
            "Text:",
            str(segment.get("text") or ""),
            "",
            "Context notes:",
            str(segment.get("contextNotes") or "-"),
            "",
            "Linked candidates:",
            str(linked_count),
        ]
    )
    return split_telegram_message(text)


def format_candidates_for_telegram(source: dict[str, Any], candidates: list[dict[str, Any]]) -> list[str]:
    if not candidates:
        return [f"Candidate List\n\nSource:\n{source.get('sourceId')}\n\nNo candidates found."]
    lines = ["Candidate List", "", "Source:", str(source.get("sourceId")), ""]
    for index, candidate in enumerate(candidates, start=1):
        lines.extend(
            [
                f"{index}. {candidate.get('candidateId')} - {candidate.get('title')}",
                f"Type: {candidate.get('candidateType')}",
                f"Risk: {candidate.get('riskLevel')}",
                f"Status: {candidate.get('candidateStatus')}",
                "",
            ]
        )
    return split_telegram_message("\n".join(lines).strip())


def format_candidate_detail_for_telegram(source: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    lines = [
        "Candidate Detail",
        "",
        "Candidate ID:",
        str(candidate.get("candidateId")),
        "",
        "Source:",
        f"{source.get('sourceId')} - {source.get('title')}",
        "",
        "Segment:",
        str(candidate.get("segmentId") or "none"),
        "",
        "Type:",
        str(candidate.get("candidateType")),
        "",
        "Title:",
        str(candidate.get("title")),
        "",
        "Hook:",
        str(candidate.get("hook")),
        "",
        "Angle:",
        str(candidate.get("angle")),
        "",
        "Risk:",
        str(candidate.get("riskLevel")),
        "",
        "Needs context:",
        "yes" if candidate.get("needsContext") else "no",
        "",
        "Context warning:",
        str(candidate.get("contextWarning") or "-"),
        "",
        "Source credit:",
        str(candidate.get("sourceCreditSuggestion") or source.get("creditText") or "-"),
        "",
        "Status:",
        str(candidate.get("candidateStatus")),
        "",
        "Next actions:",
        f"/candidate_approve {candidate.get('candidateId')}",
        f"/candidate_reject {candidate.get('candidateId')} <reason>",
        f"/generate_from_candidate {candidate.get('candidateId')}",
    ]
    return split_telegram_message("\n".join(lines).strip())


def create_source(body: dict[str, Any]) -> dict[str, Any]:
    title = str(body.get("title") or "").strip()
    if not title:
        raise AppError(HTTPStatus.BAD_REQUEST, "missing_source_title", "Source title is required.")
    item_id = source_id()
    speaker = str(body.get("speakerName") or body.get("speaker") or "").strip()
    credit = str(body.get("creditText") or "").strip()
    if not credit and title:
        credit = f"Sumber: {title}" + (f" - {speaker}" if speaker else "")
    record = {
        "sourceId": item_id,
        "title": title,
        "speakerName": speaker,
        "sourceType": validate_source_type(str(body.get("sourceType") or body.get("type") or "other")),
        "platform": validate_source_platform(str(body.get("platform") or "other")),
        "sourceUrl": str(body.get("sourceUrl") or body.get("url") or "").strip(),
        "localFilePath": str(body.get("localFilePath") or "").strip(),
        "permissionStatus": validate_permission_status(str(body.get("permissionStatus") or body.get("permission") or SOURCE_DEFAULT_PERMISSION_STATUS)),
        "permissionNotes": str(body.get("permissionNotes") or "").strip(),
        "creditText": credit,
        "topic": str(body.get("topic") or "").strip(),
        "category": str(body.get("category") or "").strip(),
        "language": str(body.get("language") or SOURCE_DEFAULT_LANGUAGE).strip(),
        "durationSeconds": parse_float(body.get("durationSeconds"), 0, "durationSeconds"),
        "sourceStatus": validate_source_status(str(body.get("sourceStatus") or "needs_review")),
        "contextNotes": str(body.get("contextNotes") or "").strip(),
        "transcript": None,
        "generatedContent": [],
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    SOURCE_STORE.save(record)
    LOGGER.info("source_added source_id=%s", item_id)
    text = "\n".join(
        [
            "Source added",
            "",
            "Source ID:",
            item_id,
            "",
            "Title:",
            title,
            "",
            "Speaker:",
            speaker or "-",
            "",
            "Permission:",
            record["permissionStatus"],
            "",
            "Next actions:",
            f"/source_review {item_id}",
            f"/transcript_add {item_id} <paste transcript>",
            "/source_list",
        ]
    )
    return {**record, "telegramMessages": split_telegram_message(text)}


def list_sources(params: dict[str, list[str]]) -> dict[str, Any]:
    status = params.get("status", [""])[0].strip()
    permission = params.get("permissionStatus", params.get("permission", [""]))[0].strip()
    platform = params.get("platform", [""])[0].strip()
    topic = params.get("topic", [""])[0].strip().lower()
    records = []
    for source in SOURCE_STORE.list_records():
        if status and source.get("sourceStatus") != status:
            continue
        if permission and source.get("permissionStatus") != permission:
            continue
        if platform and source.get("platform") != platform:
            continue
        if topic and topic not in str(source.get("topic", "")).lower() and topic not in str(source.get("title", "")).lower():
            continue
        records.append(source)
    return {"sources": [source_summary(item) for item in records], "telegramMessages": format_source_list_for_telegram(records)}


def update_source(source_id_value: str, body: dict[str, Any]) -> dict[str, Any]:
    source = SOURCE_STORE.get(source_id_value)
    field_map = {
        "title": "title",
        "speakerName": "speakerName",
        "speaker": "speakerName",
        "sourceUrl": "sourceUrl",
        "url": "sourceUrl",
        "localFilePath": "localFilePath",
        "permissionNotes": "permissionNotes",
        "creditText": "creditText",
        "topic": "topic",
        "category": "category",
        "language": "language",
        "contextNotes": "contextNotes",
    }
    for incoming, target in field_map.items():
        if incoming in body:
            source[target] = str(body.get(incoming) or "").strip()
    if "sourceType" in body or "type" in body:
        source["sourceType"] = validate_source_type(str(body.get("sourceType") or body.get("type")))
    if "platform" in body:
        source["platform"] = validate_source_platform(str(body.get("platform")))
    if "permissionStatus" in body or "permission" in body:
        source["permissionStatus"] = validate_permission_status(str(body.get("permissionStatus") or body.get("permission")))
    if "sourceStatus" in body:
        source["sourceStatus"] = validate_source_status(str(body.get("sourceStatus")))
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    return {**source, "telegramMessages": format_source_detail_for_telegram(source)}


def approve_source(source_id_value: str) -> dict[str, Any]:
    source = SOURCE_STORE.get(source_id_value)
    source["sourceStatus"] = "approved"
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("source_approved source_id=%s", source_id_value)
    return {**source, "telegramMessages": split_telegram_message(f"Source approved.\n\nYou can now generate content using:\n/from_source {source_id_value}")}


def restrict_source(source_id_value: str, body: dict[str, Any]) -> dict[str, Any]:
    reason = str(body.get("reason") or "").strip()
    source = SOURCE_STORE.get(source_id_value)
    source["sourceStatus"] = "restricted"
    source["permissionStatus"] = "restricted"
    source["permissionNotes"] = reason
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("source_restricted source_id=%s", source_id_value)
    return {**source, "telegramMessages": split_telegram_message(f"Source restricted.\n\nReason:\n{reason or '-'}")}


def set_source_credit(source_id_value: str, body: dict[str, Any]) -> dict[str, Any]:
    credit_text = str(body.get("creditText") or body.get("credit") or "").strip()
    if not credit_text:
        raise AppError(HTTPStatus.BAD_REQUEST, "missing_credit_text", "Credit text is required.")
    source = SOURCE_STORE.get(source_id_value)
    source["creditText"] = credit_text
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    return {**source, "telegramMessages": split_telegram_message(f"Source credit updated.\n\nSource ID:\n{source_id_value}\n\nCredit:\n{credit_text}")}


def add_transcript(source_id_value: str, body: dict[str, Any]) -> dict[str, Any]:
    transcript_text = str(body.get("transcriptText") or body.get("text") or "").strip()
    if not transcript_text:
        raise AppError(HTTPStatus.BAD_REQUEST, "empty_transcript", "Transcript text is required.")
    if len(transcript_text) > TRANSCRIPT_MAX_CHARS_DIRECT:
        raise AppError(HTTPStatus.BAD_REQUEST, "transcript_too_long", "Transcript is too long for direct input.")
    source = SOURCE_STORE.get(source_id_value)
    transcript = {
        "transcriptId": transcript_id(),
        "sourceId": source_id_value,
        "transcriptText": transcript_text,
        "language": str(body.get("language") or source.get("language") or SOURCE_DEFAULT_LANGUAGE),
        "transcriptStatus": "available",
        "segments": [],
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    source["transcript"] = transcript
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("transcript_added source_id=%s transcript_id=%s chars=%d", source_id_value, transcript["transcriptId"], len(transcript_text))
    text = "\n".join(
        [
            "Transcript saved.",
            "",
            "Transcript ID:",
            transcript["transcriptId"],
            "",
            "Source ID:",
            source_id_value,
            "",
            "Length:",
            f"{len(transcript_text)} characters",
            "",
            "Next actions:",
            f"/transcript {source_id_value}",
            f"/segments_generate {source_id_value}",
            f"/ideas_from_source {source_id_value}",
        ]
    )
    return {**transcript, "telegramMessages": split_telegram_message(text)}


TIMESTAMP_LINE_RE = re.compile(r"^\s*(?:\[|\()?(\d{1,2}:)?(\d{1,2}):(\d{2})(?:\]|\))?(?:\s*-\s*(?:(\d{1,2}:)?(\d{1,2}):(\d{2}))?)?\s*(.*)$")


def parse_timestamp_parts(hour: Optional[str], minute: str, second: str) -> int:
    h = int(hour[:-1]) if hour else 0
    return h * 3600 + int(minute) * 60 + int(second)


def segment_risk_for_text(text: str) -> str:
    lowered = text.lower()
    high_markers = ["hadits", "hadith", "quran", "alquran", "ayat", "fatwa", "haram", "halal", "riba"]
    medium_markers = ["ustadz", "hukum", "dalil", "dosa", "surga", "neraka"]
    if any(marker in lowered for marker in high_markers):
        return "high"
    if any(marker in lowered for marker in medium_markers):
        return "medium"
    return "low"


def generate_segments(source_id_value: str) -> dict[str, Any]:
    source = SOURCE_STORE.get(source_id_value)
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else None
    if not transcript or not transcript.get("transcriptText"):
        raise AppError(HTTPStatus.NOT_FOUND, "transcript_not_found", "Transcript was not found.")
    LOGGER.info("transcript_segmentation_started source_id=%s", source_id_value)
    text = str(transcript["transcriptText"])
    segments = []
    timestamped = []
    for line in text.splitlines():
        match = TIMESTAMP_LINE_RE.match(line)
        if match and match.group(7).strip():
            start = parse_timestamp_parts(match.group(1), match.group(2), match.group(3))
            end = parse_timestamp_parts(match.group(4), match.group(5), match.group(6)) if match.group(5) else None
            timestamped.append((start, end, match.group(7).strip()))
    if timestamped:
        for index, (start, end, segment_text) in enumerate(timestamped):
            next_start = timestamped[index + 1][0] if index + 1 < len(timestamped) else None
            segments.append(
                {
                    "segmentId": segment_id(),
                    "transcriptId": transcript["transcriptId"],
                    "sourceId": source_id_value,
                    "startTimeSeconds": start,
                    "endTimeSeconds": end if end is not None else next_start,
                    "text": segment_text,
                    "topic": source.get("topic", ""),
                    "contextNotes": "",
                    "riskLevel": segment_risk_for_text(segment_text),
                    "createdAt": now_iso(),
                    "updatedAt": now_iso(),
                }
            )
    else:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
        chunk = []
        count = 0
        for paragraph in paragraphs or [text]:
            words = paragraph.split()
            if chunk and count + len(words) > TRANSCRIPT_SEGMENT_MAX_WORDS:
                segment_text = "\n\n".join(chunk)
                segments.append(
                    {
                        "segmentId": segment_id(),
                        "transcriptId": transcript["transcriptId"],
                        "sourceId": source_id_value,
                        "startTimeSeconds": None,
                        "endTimeSeconds": None,
                        "text": segment_text,
                        "topic": source.get("topic", ""),
                        "contextNotes": "Timestamp tidak tersedia. Segment dibuat berdasarkan struktur teks.",
                        "riskLevel": segment_risk_for_text(segment_text),
                        "createdAt": now_iso(),
                        "updatedAt": now_iso(),
                    }
                )
                chunk = []
                count = 0
            chunk.append(paragraph)
            count += len(words)
        if chunk:
            segment_text = "\n\n".join(chunk)
            segments.append(
                {
                    "segmentId": segment_id(),
                    "transcriptId": transcript["transcriptId"],
                    "sourceId": source_id_value,
                    "startTimeSeconds": None,
                    "endTimeSeconds": None,
                    "text": segment_text,
                    "topic": source.get("topic", ""),
                    "contextNotes": "Timestamp tidak tersedia. Segment dibuat berdasarkan struktur teks.",
                    "riskLevel": segment_risk_for_text(segment_text),
                    "createdAt": now_iso(),
                    "updatedAt": now_iso(),
                }
            )
    transcript["segments"] = segments
    transcript["updatedAt"] = now_iso()
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("transcript_segmentation_completed source_id=%s segments=%d", source_id_value, len(segments))
    message = f"Segments generated\n\nSource ID:\n{source_id_value}\n\nSegments:\n{len(segments)}\n\nReminder:\nJika tidak ada timestamp asli, segment hanya berbasis paragraf/logika, bukan waktu video akurat."
    return {"sourceId": source_id_value, "segments": segments, "telegramMessages": split_telegram_message(message)}


def update_segment(item_segment_id: str, body: dict[str, Any]) -> dict[str, Any]:
    source, transcript, segment = SOURCE_STORE.find_segment(item_segment_id)
    if "riskLevel" in body or "risk" in body:
        segment["riskLevel"] = validate_risk_level(str(body.get("riskLevel") or body.get("risk")))
    if "contextNotes" in body or "notes" in body:
        segment["contextNotes"] = str(body.get("contextNotes") or body.get("notes") or "").strip()
    segment["updatedAt"] = now_iso()
    transcript["updatedAt"] = now_iso()
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("segment_updated segment_id=%s", item_segment_id)
    return {**segment, "telegramMessages": format_segment_detail_for_telegram(source, segment)}


def find_candidate(item_candidate_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not re.fullmatch(r"cand_\d{8}_[a-f0-9]{8}", item_candidate_id):
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_candidate_id", "Candidate ID format is invalid.")
    for source in SOURCE_STORE.list_records():
        for candidate in source_candidates(source):
            if candidate.get("candidateId") == item_candidate_id:
                return source, candidate
    raise AppError(HTTPStatus.NOT_FOUND, "candidate_not_found", "Candidate was not found.")


def normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def validate_candidate_payload(item: dict[str, Any], source: dict[str, Any], transcript: dict[str, Any], default_segment_id: str = "") -> dict[str, Any]:
    title = str(item.get("title") or "").strip()
    hook = str(item.get("hook") or "").strip()
    if not title or not hook:
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_validation_failed", "AI candidate response is missing title or hook.")
    risk = validate_risk_level(str(item.get("riskLevel") or "medium"))
    try:
        candidate_type = validate_candidate_type(str(item.get("candidateType") or "mixed"))
    except AppError:
        candidate_type = "mixed"
    if candidate_type not in CANDIDATE_ALLOWED_TYPES:
        candidate_type = "mixed"
    reasoning = str(item.get("aiReasoningSummary") or "").strip()
    if len(reasoning.split()) > 60:
        reasoning = "Candidate dipilih karena relevan dengan sumber dan perlu ditinjau manual sebelum dipakai."
    candidate = {
        "candidateId": candidate_id(),
        "sourceId": source["sourceId"],
        "transcriptId": transcript.get("transcriptId", ""),
        "segmentId": str(item.get("segmentId") or default_segment_id or "").strip(),
        "candidateType": candidate_type,
        "title": title[:140],
        "hook": hook[:240],
        "angle": str(item.get("angle") or "").strip()[:500],
        "summary": str(item.get("summary") or "").strip()[:800],
        "suggestedFormat": str(item.get("suggestedFormat") or candidate_type).strip(),
        "suggestedDurationSeconds": parse_int(item.get("suggestedDurationSeconds"), 45, "suggestedDurationSeconds"),
        "riskLevel": risk,
        "needsContext": parse_bool(item.get("needsContext"), risk != "low"),
        "contextWarning": str(item.get("contextWarning") or "").strip()[:500],
        "sourceCreditSuggestion": str(item.get("sourceCreditSuggestion") or source.get("creditText") or "").strip(),
        "candidateStatus": "suggested",
        "aiReasoningSummary": reasoning[:500],
        "contentLinks": [],
        "rejectionReason": "",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    if candidate["riskLevel"] in {"medium", "high"} and not candidate["contextWarning"]:
        candidate["contextWarning"] = "Review konteks sumber/segment secara manual sebelum dipakai."
    return candidate


def candidate_permission_warnings(source: dict[str, Any]) -> list[str]:
    permission = str(source.get("permissionStatus") or "unknown")
    status = str(source.get("sourceStatus") or "draft")
    warnings = []
    if status == "restricted" or permission in {"restricted", "rejected"}:
        if CANDIDATE_BLOCK_RESTRICTED_SOURCE:
            raise AppError(HTTPStatus.CONFLICT, "source_restricted", "Source is restricted or rejected.")
        warnings.append("Source is restricted or rejected. Manual review is required.")
    if permission == "unknown":
        if not CANDIDATE_ALLOW_UNKNOWN_PERMISSION:
            raise AppError(HTTPStatus.CONFLICT, "source_permission_unknown", "Source permission is unknown.")
        warnings.append("Source permission is unknown. Review permission and credit before posting.")
    if permission == "needs_permission":
        warnings.append("Source needs permission. Do not publish without permission review.")
    if permission == "allowed_for_dakwah":
        warnings.append("Boleh disebarkan untuk dakwah belum tentu otomatis aman untuk monetisasi. Tetap beri sumber dan nilai tambah.")
    return warnings


def candidate_context_from_source(source: dict[str, Any], max_segments: int) -> tuple[dict[str, Any], str]:
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else None
    if not transcript or not transcript.get("transcriptText"):
        raise AppError(HTTPStatus.NOT_FOUND, "transcript_not_found", "Transcript is required for highlight generation.")
    segments = transcript.get("segments") if isinstance(transcript.get("segments"), list) else []
    if segments:
        selected = segments[:max_segments]
        context = "\n\n".join(
            f"segmentId={segment.get('segmentId')} risk={segment.get('riskLevel')}\n{segment.get('text')}"
            for segment in selected
        )
    else:
        context = str(transcript.get("transcriptText") or "")
    if len(context) > CANDIDATE_MAX_TRANSCRIPT_CHARS:
        context = context[:CANDIDATE_MAX_TRANSCRIPT_CHARS] + "\n\n[Transcript truncated for analysis. Manual review required.]"
    return transcript, context


def save_candidates(source: dict[str, Any], new_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = source.get("candidates")
    if not isinstance(candidates, list):
        candidates = []
        source["candidates"] = candidates
    existing_titles = {normalized_title(str(item.get("title") or "")) for item in candidates if isinstance(item, dict)}
    saved = []
    for candidate in new_candidates:
        key = normalized_title(candidate["title"])
        if not key or key in existing_titles:
            continue
        candidates.append(candidate)
        existing_titles.add(key)
        saved.append(candidate)
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("candidates_saved source_id=%s count=%d", source.get("sourceId"), len(saved))
    return saved


def generate_highlights_from_source(source_id_value: str, body: dict[str, Any]) -> dict[str, Any]:
    source = SOURCE_STORE.get(source_id_value)
    warnings = candidate_permission_warnings(source)
    candidate_count = max(1, min(parse_int(body.get("candidateCount"), CANDIDATE_DEFAULT_COUNT, "candidateCount"), 10))
    preferred = body.get("preferredTypes")
    preferred_types = [validate_candidate_type(str(item)) for item in preferred] if isinstance(preferred, list) else sorted(CANDIDATE_ALLOWED_TYPES)
    transcript, context = candidate_context_from_source(source, min(parse_int(body.get("maxSegments"), CANDIDATE_MAX_SEGMENTS_PER_RUN, "maxSegments"), CANDIDATE_MAX_SEGMENTS_PER_RUN))
    LOGGER.info("highlight_generation_requested source_id=%s", source_id_value)
    result = call_ai_json(
        [
            {"role": "system", "content": system_prompt()},
            {
                "role": "user",
                "content": highlight_candidates_prompt(
                    source,
                    transcript,
                    context,
                    candidate_count=candidate_count,
                    preferred_types=preferred_types,
                ),
            },
        ]
    )
    raw_candidates = result.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_no_candidates", "AI returned no candidates.")
    candidates = [validate_candidate_payload(item, source, transcript) for item in raw_candidates if isinstance(item, dict)]
    allow_high_risk = parse_bool(body.get("allowHighRisk"), CANDIDATE_ALLOW_HIGH_RISK)
    candidates = [item for item in candidates if allow_high_risk or item["riskLevel"] != "high"]
    if not candidates:
        raise AppError(HTTPStatus.CONFLICT, "high_risk_candidate_blocked", "Only high-risk candidates were returned and high-risk candidates are blocked.")
    saved = save_candidates(source, candidates[:candidate_count])
    if not saved:
        raise AppError(HTTPStatus.CONFLICT, "duplicate_candidate", "No new candidates were saved.")
    lines = ["Highlight Candidates Generated", "", "Source:", source_id_value, "", "Title:", str(source.get("title")), "", "Candidates:", ""]
    for index, candidate in enumerate(saved, start=1):
        lines.extend([f"{index}. {candidate['candidateId']}", f"Type: {candidate['candidateType']}", f"Title: {candidate['title']}", f"Risk: {candidate['riskLevel']}", f"Needs context: {'yes' if candidate['needsContext'] else 'no'}", ""])
    if warnings:
        lines.extend(["Warnings:", *[f"- {warning}" for warning in warnings], ""])
    lines.extend(["Next actions:", f"/candidate {saved[0]['candidateId']}", f"/candidate_approve {saved[0]['candidateId']}", f"/generate_from_candidate {saved[0]['candidateId']}", "", "Reminder:", "Review kembali konteks sebelum upload agar tidak salah makna."])
    return {"sourceId": source_id_value, "analysisSummary": result.get("analysisSummary", ""), "warnings": warnings, "candidates": saved, "telegramMessages": split_telegram_message("\n".join(lines).strip())}


def generate_highlights_from_segment(item_segment_id: str, body: dict[str, Any]) -> dict[str, Any]:
    source, transcript, segment = SOURCE_STORE.find_segment(item_segment_id)
    warnings = candidate_permission_warnings(source)
    if segment.get("riskLevel") == "high":
        warnings.append("Segment risk is high. Manual context review is required.")
    candidate_count = max(1, min(parse_int(body.get("candidateCount"), 5, "candidateCount"), 5))
    result = call_ai_json(
        [
            {"role": "system", "content": system_prompt()},
            {
                "role": "user",
                "content": highlight_candidates_prompt(
                    source,
                    transcript,
                    str(segment.get("text") or ""),
                    candidate_count=candidate_count,
                    preferred_types=sorted(CANDIDATE_ALLOWED_TYPES),
                    segment=segment,
                ),
            },
        ]
    )
    raw_candidates = result.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_no_candidates", "AI returned no candidates.")
    candidates = [validate_candidate_payload(item, source, transcript, item_segment_id) for item in raw_candidates if isinstance(item, dict)]
    allow_high_risk = parse_bool(body.get("allowHighRisk"), CANDIDATE_ALLOW_HIGH_RISK)
    candidates = [item for item in candidates if allow_high_risk or item["riskLevel"] != "high"]
    if not candidates:
        raise AppError(HTTPStatus.CONFLICT, "high_risk_candidate_blocked", "Only high-risk candidates were returned and high-risk candidates are blocked.")
    saved = save_candidates(source, candidates[:candidate_count])
    if not saved:
        raise AppError(HTTPStatus.CONFLICT, "duplicate_candidate", "No new candidates were saved.")
    return {"sourceId": source["sourceId"], "segmentId": item_segment_id, "warnings": warnings, "candidates": saved, "telegramMessages": format_candidates_for_telegram(source, saved)}


def list_candidates_for_source(source_id_value: str, status: str = "") -> dict[str, Any]:
    source = SOURCE_STORE.get(source_id_value)
    if status:
        status = validate_candidate_status(status)
    candidates = [candidate for candidate in source_candidates(source) if not status or candidate.get("candidateStatus") == status]
    return {"sourceId": source_id_value, "candidates": candidates, "telegramMessages": format_candidates_for_telegram(source, candidates)}


def list_candidates_by_status(status: str = "", limit: int = 20) -> dict[str, Any]:
    if status:
        status = validate_candidate_status(status)
    items = []
    for source in SOURCE_STORE.list_records():
        for candidate in source_candidates(source):
            if status and candidate.get("candidateStatus") != status:
                continue
            items.append((source, candidate))
    items.sort(key=lambda pair: str(pair[1].get("createdAt") or ""), reverse=True)
    selected = items[: max(1, min(limit, 100))]
    lines = ["Candidate List", "", "Status:", status or "all", ""]
    for index, (_source, candidate) in enumerate(selected, start=1):
        lines.append(f"{index}. {candidate.get('candidateId')} - {candidate.get('title')} ({candidate.get('candidateStatus')})")
    if not selected:
        lines.append("No candidates found.")
    return {"status": status or "all", "candidates": [candidate for _source, candidate in selected], "telegramMessages": split_telegram_message("\n".join(lines).strip())}


def approve_candidate(item_candidate_id: str) -> dict[str, Any]:
    source, candidate = find_candidate(item_candidate_id)
    if candidate.get("candidateStatus") == "rejected":
        raise AppError(HTTPStatus.CONFLICT, "candidate_already_rejected", "Rejected candidate cannot be approved without manual status change.")
    candidate["candidateStatus"] = "approved"
    candidate["updatedAt"] = now_iso()
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("candidate_approved candidate_id=%s", item_candidate_id)
    return {**candidate, "telegramMessages": split_telegram_message(f"Candidate approved.\n\nNext action:\n/generate_from_candidate {item_candidate_id}")}


def reject_candidate(item_candidate_id: str, body: dict[str, Any]) -> dict[str, Any]:
    reason = str(body.get("reason") or "").strip()
    source, candidate = find_candidate(item_candidate_id)
    candidate["candidateStatus"] = "rejected"
    candidate["rejectionReason"] = reason
    candidate["updatedAt"] = now_iso()
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("candidate_rejected candidate_id=%s", item_candidate_id)
    return {**candidate, "telegramMessages": split_telegram_message(f"Candidate rejected.\n\nReason:\n{reason or '-'}")}


def generate_content_from_candidate(item_candidate_id: str, body: dict[str, Any]) -> dict[str, Any]:
    source, candidate = find_candidate(item_candidate_id)
    if candidate.get("candidateStatus") == "rejected":
        raise AppError(HTTPStatus.CONFLICT, "candidate_already_rejected", "Candidate is rejected.")
    if candidate.get("candidateStatus") == "converted_to_content":
        raise AppError(HTTPStatus.CONFLICT, "candidate_already_converted", "Candidate has already been converted to content.")
    if candidate.get("candidateStatus") != "approved":
        raise AppError(HTTPStatus.CONFLICT, "candidate_not_approved", "Candidate must be approved before content generation.")
    allow_high_risk = parse_bool(body.get("allowHighRisk"), CANDIDATE_ALLOW_HIGH_RISK)
    if candidate.get("riskLevel") == "high" and not allow_high_risk:
        raise AppError(HTTPStatus.CONFLICT, "high_risk_candidate_blocked", "High-risk candidate is blocked by configuration.")
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
    segment = None
    if candidate.get("segmentId"):
        try:
            _source, _transcript, segment = SOURCE_STORE.find_segment(str(candidate["segmentId"]))
        except AppError:
            segment = None
    content = call_ai_json(
        [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": candidate_content_prompt(source, transcript, candidate, segment)},
        ]
    )
    content = validate_content(content)
    warnings = []
    if candidate.get("needsContext"):
        warnings.append(str(candidate.get("contextWarning") or "Review candidate context manually."))
    if candidate.get("riskLevel") in {"medium", "high"}:
        warnings.append(f"Candidate risk is {candidate.get('riskLevel')}. Manual review required.")
    content["safetyNotes"].extend([warning for warning in warnings if warning])
    item_id = content_id()
    record = {
        "id": item_id,
        "status": "needs_review",
        "topic": candidate.get("title") or source.get("topic") or source.get("title"),
        "niche": "annotasi_hikmah",
        "tone": "calm_reflective",
        "platform": "instagram",
        "content": content,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    ensure_workflow(record)
    set_workflow_status(record, "needs_review")
    transcript_dict = transcript if isinstance(transcript, dict) else None
    source_link = link_source_to_content(record, source, transcript_dict, segment)
    candidate_link = {"candidateId": item_candidate_id, "contentId": item_id, "createdAt": now_iso()}
    record["candidateLink"] = {**candidate_link, "sourceId": source.get("sourceId"), "segmentId": candidate.get("segmentId"), "riskLevel": candidate.get("riskLevel")}
    links = candidate.get("contentLinks")
    if not isinstance(links, list):
        links = []
        candidate["contentLinks"] = links
    links.append(candidate_link)
    candidate["candidateStatus"] = "converted_to_content"
    candidate["updatedAt"] = now_iso()
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    STORE.save(record)
    LOGGER.info("content_generated_from_candidate candidate_id=%s content_id=%s", item_candidate_id, item_id)
    lines = [
        "Content Generated from Candidate",
        "",
        "Content ID:",
        item_id,
        "",
        "Candidate:",
        item_candidate_id,
        "",
        "Title:",
        str(content.get("title")),
        "",
        "Status:",
        "needs_review",
        "",
        "Next actions:",
        f"/review {item_id}",
        f"/approve {item_id}",
        f"/render {item_id}",
        "",
        "Reminder:",
        "Review kembali sebelum upload agar tidak salah konteks.",
    ]
    return {"id": item_id, "status": "needs_review", "content": content, "sourceLink": source_link, "candidateLink": record["candidateLink"], "warnings": warnings, "telegramMessages": split_telegram_message("\n".join(lines).strip())}


def candidate_for_content(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    link = record.get("candidateLink")
    if not isinstance(link, dict) or not link.get("candidateId"):
        raise AppError(HTTPStatus.NOT_FOUND, "candidate_link_not_found", "Content has no linked candidate.")
    source, candidate = find_candidate(str(link["candidateId"]))
    lines = [
        "Content Candidate",
        "",
        "Content ID:",
        item_id,
        "",
        "Candidate ID:",
        str(candidate.get("candidateId")),
        "",
        "Source:",
        str(source.get("sourceId")),
        "",
        "Segment:",
        str(candidate.get("segmentId") or "none"),
        "",
        "Risk:",
        str(candidate.get("riskLevel")),
    ]
    return {"contentId": item_id, "candidate": candidate, "source": source_summary(source), "telegramMessages": split_telegram_message("\n".join(lines).strip())}


def slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug[:80].strip("-") or fallback).lower()


def ensure_path_inside(path: Path, roots: list[Path], code: str = "path_not_allowed") -> Path:
    resolved = path.expanduser().resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise AppError(HTTPStatus.BAD_REQUEST, code, "File path is outside allowed directories.")


def write_text_file(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "package_write_failed", f"Could not write {path.name}.") from exc


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    write_text_file(path, json.dumps(payload, ensure_ascii=False, indent=2))


def safe_copy_file(source_path: Path, target_path: Path) -> None:
    source = ensure_path_inside(source_path, [EXPORT_DIR, CONTENT_AUDIO_DIR, PACKAGE_DIR])
    target = ensure_path_inside(target_path, [PACKAGE_DIR])
    if not source.exists() or not source.is_file() or source.stat().st_size <= 0:
        raise AppError(HTTPStatus.NOT_FOUND, "package_asset_missing", f"Asset is missing: {source.name}")
    if source.name.startswith(".env"):
        raise AppError(HTTPStatus.BAD_REQUEST, "package_asset_blocked", "Environment files cannot be packaged.")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "package_copy_failed", f"Could not copy {source.name}.") from exc


def content_text_fields(record: dict[str, Any]) -> tuple[str, str, list[str], str, str]:
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    title = str(content.get("title") or record.get("topic") or "").strip()
    caption = str(content.get("caption") or "").strip()
    hashtags = content.get("hashtags")
    if not isinstance(hashtags, list):
        hashtags = []
    hashtags = [str(item).strip() for item in hashtags if str(item).strip()]
    voiceover = str(content.get("voiceoverScript") or "").strip()
    source_credit = str(content.get("sourceCreditSuggestion") or "").strip()
    return title, caption, hashtags, voiceover, source_credit


def hashtag_text(hashtags: list[str], multiline: bool = False) -> str:
    if multiline:
        return "\n".join(hashtags)
    return " ".join(hashtags)


def short_caption(caption: str, limit: int = 220) -> str:
    compact = re.sub(r"\s+", " ", caption).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."


def platform_caption_files(title: str, caption: str, hashtags: list[str]) -> dict[str, str]:
    tags = hashtag_text(hashtags)
    return {
        "caption-instagram.txt": "\n\n".join(part for part in [caption, tags] if part).strip() + "\n",
        "caption-tiktok.txt": "\n\n".join(part for part in [short_caption(caption), tags] if part).strip() + "\n",
        "caption-youtube-shorts.txt": "\n\n".join(part for part in [title, caption, tags] if part).strip() + "\n",
    }


def linked_source_and_candidate(record: dict[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    source = None
    candidate = None
    source_link = record.get("sourceLink")
    if isinstance(source_link, dict) and source_link.get("sourceId"):
        try:
            source = SOURCE_STORE.get(str(source_link["sourceId"]))
        except AppError:
            source = None
    candidate_link = record.get("candidateLink")
    if isinstance(candidate_link, dict) and candidate_link.get("candidateId"):
        try:
            _source, candidate = find_candidate(str(candidate_link["candidateId"]))
        except AppError:
            candidate = None
    return source, candidate


def content_is_approved(record: dict[str, Any]) -> bool:
    workflow = ensure_workflow(record)
    if workflow.get("reviewStatus") == "approved":
        return True
    return str(workflow.get("status") or "") in SCHEDULABLE_STATUSES


def completed_png_for_package(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    render = record.get("latestRender")
    return render if isinstance(render, dict) and render.get("status") == "completed" and render_files_exist(render) else None


def completed_video_for_package(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    render = record.get("latestVideoRender")
    return render if isinstance(render, dict) and render.get("status") == "completed" and video_file_exists(render) else None


def completed_audio_for_package(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    render = record.get("latestAudioRender")
    return render if isinstance(render, dict) and render.get("status") == "completed" and audio_file_exists(render) else None


def source_credit_for_package(record: dict[str, Any], source: Optional[dict[str, Any]]) -> str:
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    candidates = [
        content.get("sourceCreditSuggestion"),
        record.get("sourceLink", {}).get("sourceCreditUsed") if isinstance(record.get("sourceLink"), dict) else "",
        source.get("creditText") if isinstance(source, dict) else "",
    ]
    for item in candidates:
        text = str(item or "").strip()
        if text:
            return text
    return ""


def package_required_issues(record: dict[str, Any]) -> list[str]:
    title, caption, hashtags, _voiceover, _source_credit = content_text_fields(record)
    workflow = ensure_workflow(record)
    issues = []
    if workflow.get("status") == "rejected":
        issues.append("Content is rejected.")
    if not title:
        issues.append("Content title is missing.")
    if not caption:
        issues.append("Caption is missing.")
    if not hashtags:
        issues.append("Hashtags are missing.")
    if CONTENT_PACKAGE_REQUIRE_APPROVAL and not content_is_approved(record):
        issues.append("Content must be approved before packaging. Run /review <content_id> and /approve <content_id> first.")
    return issues


def package_warnings(record: dict[str, Any], source: Optional[dict[str, Any]], candidate: Optional[dict[str, Any]]) -> list[str]:
    _title, _caption, _hashtags, voiceover, _source_credit = content_text_fields(record)
    workflow = ensure_workflow(record)
    warnings = []
    stale = workflow.get("renderStale") if isinstance(workflow.get("renderStale"), dict) else {}
    if isinstance(stale, dict):
        if stale.get("png"):
            warnings.append("PNG render is stale. Rerun /render before posting.")
        if stale.get("video"):
            warnings.append("MP4 video render is stale. Rerun /video before posting.")
        if stale.get("audio"):
            warnings.append("Voiceover video is stale. Rerun /mixvoice before posting.")
    if not completed_png_for_package(record):
        warnings.append("PNG carousel render not found.")
    if not completed_video_for_package(record):
        warnings.append("MP4 video render not found.")
    if voiceover and not completed_audio_for_package(record):
        warnings.append("Voiceover script exists, but voiceover MP4 was not found.")
    if source and not source_credit_for_package(record, source):
        warnings.append("Linked source exists, but source credit is missing.")
    if source and source.get("permissionStatus") in {"unknown", "needs_permission", "allowed_for_dakwah"}:
        warnings.append("Source permission requires manual review before monetized posting.")
    if candidate and candidate.get("needsContext"):
        warnings.append(str(candidate.get("contextWarning") or "Candidate context must be reviewed manually."))
    if not CONTENT_PACKAGE_REQUIRE_APPROVAL and not content_is_approved(record):
        warnings.append("Content is not approved yet.")
    warnings.append("Review kembali sebelum upload agar tidak salah konteks.")
    return list(dict.fromkeys([item for item in warnings if item]))


def ready_to_post_check(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    source, candidate = linked_source_and_candidate(record)
    required = package_required_issues(record)
    warnings = package_warnings(record, source, candidate)
    stale = ensure_workflow(record).get("renderStale", {})
    stale_blocked = bool(isinstance(stale, dict) and any(stale.values()) and not CONTENT_PACKAGE_ALLOW_STALE_MEDIA)
    if stale_blocked:
        required.append("Media render is stale. Please rerun /render, /video, or /mixvoice before packaging.")
    missing = [item for item in warnings if "not found" in item or "missing" in item.lower()]
    ready = not required and not missing
    return {
        "contentId": item_id,
        "ready": ready,
        "missing": missing,
        "blockingIssues": required,
        "warnings": warnings,
        "summary": workflow_summary(record),
        "telegramMessages": format_ready_to_post_for_telegram(item_id, ready, missing, required, warnings),
    }


def posting_checklist_text(record: dict[str, Any]) -> str:
    title, _caption, _hashtags, _voiceover, _source_credit = content_text_fields(record)
    return "\n".join(
        [
            "# Posting Checklist - Annotasi Hikmah",
            "",
            "Content ID:",
            str(record.get("id")),
            "",
            "Title:",
            title or "-",
            "",
            "Before upload:",
            "",
            "* [ ] Content has been reviewed.",
            "* [ ] Content status is approved.",
            "* [ ] PNG carousel is readable.",
            "* [ ] MP4 video is playable.",
            "* [ ] Voiceover audio is clear if used.",
            "* [ ] Caption is ready.",
            "* [ ] Hashtags are relevant.",
            "* [ ] Source credit is included if content is based on kajian/transcript.",
            "* [ ] Source permission status has been checked.",
            "* [ ] Candidate/segment context has been reviewed.",
            "* [ ] No invented Quran verse.",
            "* [ ] No invented hadith.",
            "* [ ] No unsupported attribution to UAS, UAH, or any ustadz.",
            "* [ ] Title is not misleading or excessive clickbait.",
            "* [ ] Meaning is not cut out of context.",
            "* [ ] Final content is suitable for dakwah/reflection.",
            "* [ ] Platform selected for posting.",
            "* [ ] Uploaded URL will be saved using `/uploaded`.",
            "",
            "Reminder:",
            "",
            "Review kembali sebelum upload agar tidak salah konteks.",
            "",
            "Additional warning:",
            "",
            "Boleh disebarkan untuk dakwah belum tentu otomatis aman untuk monetisasi. Tetap beri sumber dan nilai tambah.",
            "",
        ]
    )


def dakwah_safety_checklist_text() -> str:
    return "\n".join(
        [
            "# Dakwah Safety Checklist",
            "",
            "* [ ] Source clarity checked.",
            "* [ ] Permission clarity checked.",
            "* [ ] Credit clarity checked.",
            "* [ ] Context reviewed.",
            "* [ ] Quran/hadith safety checked.",
            "* [ ] Attribution safety checked.",
            "* [ ] Monetization caution reviewed.",
            "* [ ] No voice cloning used.",
            "* [ ] No misleading edits.",
            "* [ ] Manual review completed.",
            "",
        ]
    )


def source_context_text(record: dict[str, Any], source: Optional[dict[str, Any]], candidate: Optional[dict[str, Any]]) -> str:
    if not source:
        return "No linked source found. If this content was inspired by a kajian, video, transcript, book, or article, add the source before posting.\n"
    link = record.get("sourceLink") if isinstance(record.get("sourceLink"), dict) else {}
    candidate_link = record.get("candidateLink") if isinstance(record.get("candidateLink"), dict) else {}
    candidate_id_value = (candidate or {}).get("candidateId") or candidate_link.get("candidateId") or "-"
    lines = [
        "# Source Context",
        "",
        f"Source ID: {source.get('sourceId')}",
        f"Source title: {source.get('title') or '-'}",
        f"Speaker name: {source.get('speakerName') or '-'}",
        f"Source URL: {source.get('sourceUrl') or '-'}",
        f"Source platform: {source.get('platform') or '-'}",
        f"Permission status: {source.get('permissionStatus') or '-'}",
        f"Permission notes: {source.get('permissionNotes') or '-'}",
        f"Credit text: {source.get('creditText') or '-'}",
        f"Segment ID: {link.get('segmentId') or '-'}",
        f"Candidate ID: {candidate_id_value}",
        f"Risk level: {(candidate or {}).get('riskLevel') or link.get('riskLevel') or '-'}",
        f"Context warning: {(candidate or {}).get('contextWarning') or '-'}",
        "",
    ]
    return "\n".join(lines)


def package_readme_text(record: dict[str, Any], package: dict[str, Any]) -> str:
    title, _caption, _hashtags, _voiceover, _source_credit = content_text_fields(record)
    return "\n".join(
        [
            "# Annotasi Content Package",
            "",
            "Content ID:",
            str(record.get("id")),
            "",
            "Package ID:",
            str(package.get("packageId")),
            "",
            "Title:",
            title or "-",
            "",
            "How to post manually:",
            "",
            "1. Open `01-carousel` for Instagram carousel slides.",
            "2. Open `02-video` for Shorts/Reels/TikTok video.",
            "3. Copy caption from `03-copy`.",
            "4. Include source credit if applicable.",
            "5. Review `04-review/posting-checklist.md`.",
            "6. Upload manually to selected platform.",
            "7. After upload, run:",
            f"   `/uploaded {record.get('id')} instagram <url>`",
            "",
            "Reminder:",
            "",
            "Review kembali sebelum upload agar tidak salah konteks.",
            "",
        ]
    )


def format_ready_to_post_for_telegram(item_id: str, ready: bool, missing: list[str], blocking: list[str], warnings: list[str]) -> list[str]:
    lines = ["Ready To Post Check", "", "Content ID:", item_id, "", "Ready:", "yes" if ready else "no", ""]
    if missing:
        lines.extend(["Missing:", *[f"- {item}" for item in missing], ""])
    if blocking:
        lines.extend(["Blocking:", *[f"- {item}" for item in blocking], ""])
    if warnings:
        lines.extend(["Warnings:", *[f"- {item}" for item in warnings], ""])
    return split_telegram_message("\n".join(lines).strip())


def format_posting_checklist_for_telegram(record: dict[str, Any]) -> list[str]:
    text = posting_checklist_text(record).replace("# Posting Checklist - Annotasi Hikmah", "Posting Checklist")
    return split_telegram_message(text)


def format_package_for_telegram(package: dict[str, Any]) -> list[str]:
    included = package.get("included") if isinstance(package.get("included"), dict) else {}
    warnings = package.get("warnings") if isinstance(package.get("warnings"), list) else []
    lines = [
        "Content Package Created",
        "",
        "Content ID:",
        str(package.get("contentId")),
        "",
        "Package ID:",
        str(package.get("packageId")),
        "",
        "Title:",
        str(package.get("title") or "-"),
        "",
        "Included:",
        f"- Carousel PNG: {included.get('pngCount', 0)} files",
        f"- Video MP4: {'yes' if included.get('videoCount', 0) else 'no'}",
        f"- Voiceover MP4: {'yes' if package.get('hasVoiceoverVideo') else 'no'}",
        f"- Caption files: {'yes' if included.get('copyFiles', 0) else 'no'}",
        f"- Source credit: {'yes' if package.get('hasSourceCredit') else 'no'}",
        f"- Posting checklist: {'yes' if package.get('hasPostingChecklist') else 'no'}",
        f"- ZIP: {'yes' if package.get('zipPath') else 'no'}",
        "",
        "Package:",
        str(package.get("packageDir") or "-"),
        "",
        "ZIP:",
        str(package.get("zipPath") or "-"),
        "",
    ]
    if warnings:
        lines.extend(["Warnings:", *[f"- {warning}" for warning in warnings], ""])
    lines.extend(["Next:", "Upload manual, then run:", f"/uploaded {package.get('contentId')} instagram <url>"])
    return split_telegram_message("\n".join(lines).strip())


def format_package_status_for_telegram(item_id: str, package: Optional[dict[str, Any]]) -> list[str]:
    if not package:
        return [f"Package Status\n\nContent ID:\n{item_id}\n\nLatest Package:\nnone\n\nStatus:\nnot_started"]
    warnings = package.get("warnings") if isinstance(package.get("warnings"), list) else []
    lines = [
        "Package Status",
        "",
        "Content ID:",
        item_id,
        "",
        "Latest Package:",
        str(package.get("packageId")),
        "",
        "Status:",
        str(package.get("status")),
        "",
        "ZIP:",
        "available" if package.get("zipPath") else "not available",
        "",
        "Stale:",
        "yes" if package.get("status") == "stale" else "no",
    ]
    if warnings:
        lines.extend(["", "Warnings:", *[f"- {warning}" for warning in warnings]])
    return split_telegram_message("\n".join(lines).strip())


def format_package_list_for_telegram(item_id: str, packages: list[dict[str, Any]]) -> list[str]:
    lines = ["Package List", "", "Content ID:", item_id, ""]
    if not packages:
        lines.append("No packages found.")
    for index, package in enumerate(packages, start=1):
        lines.append(f"{index}. {package.get('packageId')} - {package.get('status')} - {package.get('createdAt')}")
    return split_telegram_message("\n".join(lines).strip())


def manifest_for_package(record: dict[str, Any], package: dict[str, Any], source: Optional[dict[str, Any]], candidate: Optional[dict[str, Any]], assets: dict[str, list[str]]) -> dict[str, Any]:
    workflow = ensure_workflow(record)
    title, _caption, _hashtags, _voiceover, _source_credit = content_text_fields(record)
    return {
        "packageId": package["packageId"],
        "contentId": record["id"],
        "title": title,
        "status": package["status"],
        "createdAt": package["createdAt"],
        "timezone": CONTENT_PACKAGE_TIMEZONE,
        "contentStatus": workflow.get("status"),
        "schedule": {
            "scheduledDate": workflow.get("scheduledDate") or None,
            "scheduledTime": workflow.get("scheduledTime") or None,
            "platform": workflow.get("scheduledPlatform") or None,
        },
        "source": {
            "sourceId": source.get("sourceId") if source else None,
            "title": source.get("title") if source else None,
            "speakerName": source.get("speakerName") if source else None,
            "sourceUrl": source.get("sourceUrl") if source else None,
            "permissionStatus": source.get("permissionStatus") if source else None,
            "creditText": source.get("creditText") if source else None,
        },
        "candidate": {
            "candidateId": candidate.get("candidateId") if candidate else None,
            "candidateType": candidate.get("candidateType") if candidate else None,
            "riskLevel": candidate.get("riskLevel") if candidate else None,
            "needsContext": bool(candidate.get("needsContext")) if candidate else False,
        },
        "assets": assets,
        "warnings": package.get("warnings", []),
        "postingReminder": "Review kembali sebelum upload agar tidak salah konteks.",
    }


def create_package_zip(package_dir: Path, zip_path: Path) -> None:
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(package_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(package_dir))
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "zip_creation_failed", "Could not create package ZIP.") from exc


def generate_content_package(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    LOGGER.info("package_request_received content_id=%s", item_id)
    record = STORE.get(item_id)
    ensure_workflow(record)
    force_regenerate = parse_bool(body.get("forceRegenerate"), False)
    existing = latest_package(record)
    if existing and existing.get("status") == "completed" and not force_regenerate:
        LOGGER.info("duplicate_package_returned content_id=%s package_id=%s", item_id, existing.get("packageId"))
        return {**existing, "telegramMessages": format_package_for_telegram(existing)}

    source, candidate = linked_source_and_candidate(record)
    required = package_required_issues(record)
    stale = ensure_workflow(record).get("renderStale", {})
    if isinstance(stale, dict) and any(stale.values()) and not CONTENT_PACKAGE_ALLOW_STALE_MEDIA:
        required.append("Media render is stale. Please rerun /render, /video, or /mixvoice before packaging.")
    if required:
        raise AppError(HTTPStatus.CONFLICT, "package_not_ready", required[0])

    item_package_id = package_id()
    title, caption, hashtags, voiceover, _source_credit = content_text_fields(record)
    package_root = ensure_path_inside((PACKAGE_DIR / item_id).resolve(), [PACKAGE_DIR])
    package_dir = ensure_path_inside(package_root / item_package_id, [PACKAGE_DIR])
    zip_path = package_root / f"{item_id}-{slugify(title, item_id)}-{item_package_id}.zip"
    warnings = package_warnings(record, source, candidate)
    package = {
        "packageId": item_package_id,
        "package_id": item_package_id,
        "contentId": item_id,
        "content_id": item_id,
        "title": title,
        "status": "packaging",
        "packageDir": str(package_dir),
        "package_dir": str(package_dir),
        "zipPath": "",
        "zip_path": "",
        "includedPngCount": 0,
        "included_png_count": 0,
        "includedVideoCount": 0,
        "included_video_count": 0,
        "includedTextCount": 0,
        "included_text_count": 0,
        "hasVoiceoverVideo": False,
        "has_voiceover_video": False,
        "hasSourceCredit": False,
        "has_source_credit": False,
        "hasCandidateMetadata": bool(candidate),
        "has_candidate_metadata": bool(candidate),
        "hasPostingChecklist": False,
        "has_posting_checklist": False,
        "warnings": warnings,
        "warningsJson": json.dumps(warnings, ensure_ascii=False),
        "warnings_json": json.dumps(warnings, ensure_ascii=False),
        "included": {"pngCount": 0, "videoCount": 0, "copyFiles": 0, "reviewFiles": 0, "metadataFiles": 0},
        "errorMessage": "",
        "error_message": "",
        "createdAt": now_iso(),
        "created_at": now_iso(),
        "updatedAt": now_iso(),
        "updated_at": now_iso(),
    }
    if not isinstance(record.get("packages"), list):
        record["packages"] = []
    record["packages"].append(package)
    record["latestPackage"] = package
    STORE.save(record)

    try:
        for dirname in ["01-carousel", "02-video", "03-copy", "04-review", "05-metadata"]:
            (package_dir / dirname).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        package["status"] = "failed"
        package["errorMessage"] = "Package directory is not writable."
        package["error_message"] = package["errorMessage"]
        package["updatedAt"] = now_iso()
        package["updated_at"] = package["updatedAt"]
        STORE.save(record)
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "package_directory_not_writable", "Package directory is not writable.") from exc

    assets = {"carouselPng": [], "videos": [], "copyFiles": [], "reviewFiles": [], "metadataFiles": []}
    try:
        png_render = completed_png_for_package(record)
        if png_render:
            png_files = validate_png_files(png_render, len(record.get("content", {}).get("slides", [])))
            for file_info in png_files:
                slide_number = int(file_info.get("slideNumber") or len(assets["carouselPng"]) + 1)
                relative = f"01-carousel/slide-{slide_number:02d}.png"
                safe_copy_file(Path(str(file_info["path"])), package_dir / relative)
                assets["carouselPng"].append(relative)

        video_render = completed_video_for_package(record)
        if video_render:
            video_path = Path(str(video_render.get("file", {}).get("path") if isinstance(video_render.get("file"), dict) else ""))
            safe_copy_file(video_path, package_dir / "02-video/final.mp4")
            assets["videos"].append("02-video/final.mp4")

        audio_render = completed_audio_for_package(record)
        if audio_render:
            audio_path = Path(str(audio_render.get("outputVideo", {}).get("path") if isinstance(audio_render.get("outputVideo"), dict) else ""))
            safe_copy_file(audio_path, package_dir / "02-video/final-voiceover.mp4")
            assets["videos"].append("02-video/final-voiceover.mp4")

        copy_files = {
            "title.txt": title + "\n",
            "hashtags.txt": hashtag_text(hashtags, multiline=True) + "\n",
            "voiceover-script.txt": (voiceover or "-") + "\n",
            "source-credit.txt": (source_credit_for_package(record, source) or "Source credit missing. Add source credit before posting if this content is source-based.") + "\n",
        }
        if parse_bool(body.get("includePlatformCaptions"), CONTENT_PACKAGE_INCLUDE_PLATFORM_CAPTIONS):
            copy_files.update(platform_caption_files(title, caption, hashtags))
        else:
            copy_files["caption-instagram.txt"] = caption + "\n"
        for filename, text in copy_files.items():
            write_text_file(package_dir / "03-copy" / filename, text)
            assets["copyFiles"].append(f"03-copy/{filename}")

        review_files = {
            "posting-checklist.md": posting_checklist_text(record),
            "dakwah-safety-checklist.md": dakwah_safety_checklist_text(),
            "source-context.md": source_context_text(record, source, candidate),
        }
        for filename, text in review_files.items():
            write_text_file(package_dir / "04-review" / filename, text)
            assets["reviewFiles"].append(f"04-review/{filename}")

        if parse_bool(body.get("includeMetadata"), CONTENT_PACKAGE_INCLUDE_METADATA):
            metadata = {
                "content.json": record,
                "render-metadata.json": {
                    "latestRender": record.get("latestRender", {}),
                    "latestVideoRender": record.get("latestVideoRender", {}),
                    "latestAudioRender": record.get("latestAudioRender", {}),
                },
            }
            if source:
                metadata["source.json"] = source
            if candidate:
                metadata["candidate.json"] = candidate
            for filename, payload in metadata.items():
                write_json_file(package_dir / "05-metadata" / filename, payload)
                assets["metadataFiles"].append(f"05-metadata/{filename}")

        package["includedPngCount"] = len(assets["carouselPng"])
        package["included_png_count"] = package["includedPngCount"]
        package["includedVideoCount"] = len(assets["videos"])
        package["included_video_count"] = package["includedVideoCount"]
        package["includedTextCount"] = len(assets["copyFiles"]) + len(assets["reviewFiles"])
        package["included_text_count"] = package["includedTextCount"]
        package["hasVoiceoverVideo"] = "02-video/final-voiceover.mp4" in assets["videos"]
        package["has_voiceover_video"] = package["hasVoiceoverVideo"]
        package["hasSourceCredit"] = bool(source_credit_for_package(record, source))
        package["has_source_credit"] = package["hasSourceCredit"]
        package["hasPostingChecklist"] = "04-review/posting-checklist.md" in assets["reviewFiles"]
        package["has_posting_checklist"] = package["hasPostingChecklist"]
        package["included"] = {
            "pngCount": len(assets["carouselPng"]),
            "videoCount": len(assets["videos"]),
            "copyFiles": len(assets["copyFiles"]),
            "reviewFiles": len(assets["reviewFiles"]),
            "metadataFiles": len(assets["metadataFiles"]),
        }
        package["status"] = "completed"
        manifest = manifest_for_package(record, package, source, candidate, assets)
        write_json_file(package_dir / "05-metadata/manifest.json", manifest)
        assets["metadataFiles"].append("05-metadata/manifest.json")
        write_text_file(package_dir / "README.md", package_readme_text(record, package))
    except AppError as exc:
        package["status"] = "failed"
        package["errorMessage"] = exc.message
        package["error_message"] = exc.message
        package["updatedAt"] = now_iso()
        package["updated_at"] = package["updatedAt"]
        STORE.save(record)
        raise

    create_zip = parse_bool(body.get("createZip"), CONTENT_PACKAGE_CREATE_ZIP)
    if create_zip:
        try:
            create_package_zip(package_dir, zip_path)
            size_mb = zip_path.stat().st_size / (1024 * 1024)
            package["zipPath"] = str(zip_path)
            package["zip_path"] = str(zip_path)
            if size_mb > CONTENT_PACKAGE_MAX_ZIP_SIZE_MB:
                package["warnings"].append("ZIP is larger than configured Telegram-safe size; return path instead of sending file.")
        except AppError as exc:
            package["warnings"].append(f"ZIP creation failed: {exc.message}")
            package["warningsJson"] = json.dumps(package["warnings"], ensure_ascii=False)
            package["warnings_json"] = package["warningsJson"]

    package["updatedAt"] = now_iso()
    package["updated_at"] = package["updatedAt"]
    package["warningsJson"] = json.dumps(package["warnings"], ensure_ascii=False)
    package["warnings_json"] = package["warningsJson"]
    record["latestPackage"] = package
    record["updatedAt"] = now_iso()
    STORE.save(record)
    LOGGER.info("package_completed content_id=%s package_id=%s", item_id, item_package_id)
    return {**package, "telegramMessages": format_package_for_telegram(package)}


def latest_package_status(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    package = latest_package(record)
    return {"contentId": item_id, "package": package, "telegramMessages": format_package_status_for_telegram(item_id, package)}


def list_packages_for_content(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    packages = record.get("packages") if isinstance(record.get("packages"), list) else []
    packages = [item for item in packages if isinstance(item, dict)]
    return {"contentId": item_id, "packages": packages, "telegramMessages": format_package_list_for_telegram(item_id, packages)}


def package_by_id(item_package_id: str) -> dict[str, Any]:
    record, package = STORE.find_package(item_package_id)
    lines = [
        "Package Path",
        "",
        "Package ID:",
        item_package_id,
        "",
        "Content ID:",
        str(record.get("id")),
        "",
        "Directory:",
        str(package.get("packageDir") or "-"),
        "",
        "ZIP:",
        str(package.get("zipPath") or "-"),
    ]
    return {"contentId": record.get("id"), "package": package, "telegramMessages": split_telegram_message("\n".join(lines).strip())}


def posting_checklist_for_content(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    return {"contentId": item_id, "checklist": posting_checklist_text(record), "telegramMessages": format_posting_checklist_for_telegram(record)}


def ensure_source_generation_allowed(source: dict[str, Any], override: bool = False) -> list[str]:
    warnings = []
    if source.get("sourceStatus") == "restricted" or source.get("permissionStatus") in {"restricted", "rejected"}:
        if SOURCE_BLOCK_RESTRICTED_GENERATION and not override:
            raise AppError(HTTPStatus.CONFLICT, "source_restricted", "Source is restricted and cannot be used for generation.")
        warnings.append("Source is restricted. Manual review is required.")
    if source.get("sourceStatus") != "approved":
        message = "Source is not approved. Manual source review is required."
        if SOURCE_REQUIRE_APPROVAL_FOR_GENERATION and not override:
            raise AppError(HTTPStatus.CONFLICT, "source_not_approved", message)
        warnings.append(message)
    if source.get("permissionStatus") in {"unknown", "needs_permission"}:
        warnings.append("Permission status is not clear. Add credit and review reuse permission before posting.")
    return warnings


def transcript_context(source: dict[str, Any], segment: Optional[dict[str, Any]] = None) -> str:
    if segment:
        return str(segment.get("text") or "")
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
    return str(transcript.get("transcriptText") or "")


def ideas_from_source(source_id_value: str) -> dict[str, Any]:
    source = SOURCE_STORE.get(source_id_value)
    warnings = ensure_source_generation_allowed(source, override=True)
    text = transcript_context(source)
    if not text:
        raise AppError(HTTPStatus.NOT_FOUND, "transcript_not_found", "Transcript is required for source ideas.")
    LOGGER.info("ideas_from_source_requested source_id=%s", source_id_value)
    ideas = call_ai_json(
        [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": ideas_from_source_prompt(source, text)},
        ]
    )
    if not isinstance(ideas.get("ideas"), list):
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_validation_failed", "AI ideas response is invalid.")
    lines = [f"Ideas from source {source_id_value}", ""]
    for index, idea in enumerate(ideas["ideas"], start=1):
        lines.extend([f"{index}. {idea.get('title')}", f"Angle: {idea.get('angle')}", f"Risk: {idea.get('riskLevel')}", ""])
    if warnings:
        lines.extend(["Warnings:", *[f"- {warning}" for warning in warnings]])
    return {**ideas, "warnings": warnings, "telegramMessages": split_telegram_message("\n".join(lines).strip())}


def link_source_to_content(record: dict[str, Any], source: dict[str, Any], transcript: Optional[dict[str, Any]], segment: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    link = {
        "contentId": record["id"],
        "sourceId": source["sourceId"],
        "transcriptId": transcript.get("transcriptId") if isinstance(transcript, dict) else "",
        "segmentId": segment.get("segmentId") if isinstance(segment, dict) else "",
        "sourceCreditUsed": source.get("creditText", ""),
        "riskLevel": segment.get("riskLevel") if isinstance(segment, dict) else "medium",
        "createdAt": now_iso(),
    }
    record["sourceLink"] = link
    links = source.get("generatedContent")
    if not isinstance(links, list):
        links = []
        source["generatedContent"] = links
    links.append(link)
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("source_linked_to_content source_id=%s content_id=%s", source["sourceId"], record["id"])
    return link


def generate_content_from_source(source_id_value: str, body: dict[str, Any]) -> dict[str, Any]:
    source = SOURCE_STORE.get(source_id_value)
    warnings = ensure_source_generation_allowed(source, bool(body.get("override", False)))
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else None
    text = transcript_context(source)
    if not text:
        raise AppError(HTTPStatus.NOT_FOUND, "transcript_not_found", "Transcript is required to generate from source.")
    topic = str(body.get("topic") or "").strip()
    content = call_ai_json(
        [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": source_content_prompt(source, text, topic)},
        ]
    )
    content = validate_content(content)
    if warnings:
        content["safetyNotes"].extend(warnings)
    item_id = content_id()
    record = {
        "id": item_id,
        "status": "needs_review",
        "topic": topic or source.get("topic") or source.get("title"),
        "niche": "annotasi_hikmah",
        "tone": "calm_reflective",
        "platform": "instagram",
        "content": content,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    ensure_workflow(record)
    set_workflow_status(record, "needs_review")
    link = link_source_to_content(record, source, transcript)
    STORE.save(record)
    LOGGER.info("content_generated_from_source source_id=%s content_id=%s", source_id_value, item_id)
    return {"id": item_id, "status": "needs_review", "content": content, "sourceLink": link, "warnings": warnings, "telegramMessages": format_full_for_telegram(record, include_voiceover=False)}


def generate_content_from_segment(item_segment_id: str, body: dict[str, Any]) -> dict[str, Any]:
    source, transcript, segment = SOURCE_STORE.find_segment(item_segment_id)
    warnings = ensure_source_generation_allowed(source, bool(body.get("override", False)))
    if segment.get("riskLevel") in {"medium", "high"}:
        warnings.append(f"Segment risk is {segment.get('riskLevel')}. Review context manually before posting.")
    content = call_ai_json(
        [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": source_content_prompt(source, str(segment.get("text") or ""), str(body.get("topic") or ""), segment)},
        ]
    )
    content = validate_content(content)
    content["safetyNotes"].extend(warnings)
    item_id = content_id()
    record = {
        "id": item_id,
        "status": "needs_review",
        "topic": segment.get("topic") or source.get("topic") or source.get("title"),
        "niche": "annotasi_hikmah",
        "tone": "calm_reflective",
        "platform": "instagram",
        "content": content,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    ensure_workflow(record)
    set_workflow_status(record, "needs_review")
    link = link_source_to_content(record, source, transcript, segment)
    STORE.save(record)
    LOGGER.info("content_generated_from_segment segment_id=%s content_id=%s", item_segment_id, item_id)
    return {"id": item_id, "status": "needs_review", "content": content, "sourceLink": link, "warnings": warnings, "telegramMessages": format_full_for_telegram(record, include_voiceover=False)}


def source_for_content(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    link = record.get("sourceLink")
    if not isinstance(link, dict) or not link.get("sourceId"):
        raise AppError(HTTPStatus.NOT_FOUND, "source_link_not_found", "Content has no linked source.")
    source = SOURCE_STORE.get(str(link["sourceId"]))
    segment = None
    if link.get("segmentId"):
        try:
            _source, _transcript, segment = SOURCE_STORE.find_segment(str(link["segmentId"]))
        except AppError:
            segment = None
    lines = [
        "Content Source",
        "",
        "Content ID:",
        item_id,
        "",
        "Source ID:",
        str(source.get("sourceId")),
        "",
        "Title:",
        str(source.get("title")),
        "",
        "Credit:",
        str(source.get("creditText") or "-"),
        "",
        "Segment:",
        str(link.get("segmentId") or "none"),
        "",
        "Risk:",
        str((segment or {}).get("riskLevel") or link.get("riskLevel") or "medium"),
        "",
        "Reminder:",
        "Review kembali sebelum upload agar tidak salah konteks.",
    ]
    return {"contentId": item_id, "source": source_summary(source), "link": link, "telegramMessages": split_telegram_message("\n".join(lines).strip())}


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
    ensure_workflow(record)
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

    def do_PATCH(self) -> None:
        try:
            self.handle_patch()
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

    def do_DELETE(self) -> None:
        try:
            self.handle_delete()
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
        parsed_url = urlparse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")
        params = urlparse.parse_qs(parsed_url.query)
        if path == "/health":
            json_response(self, HTTPStatus.OK, {"status": "ok", "service": "annotasi-carousel-studio"})
            return

        if path == "/api/v1/calendar":
            json_response(self, HTTPStatus.OK, query_calendar(params))
            return

        calendar_shortcut_match = re.fullmatch(r"/api/v1/calendar/(today|week|month|next)", path)
        if calendar_shortcut_match:
            mode = calendar_shortcut_match.group(1)
            today = local_today()
            if mode == "today":
                query = {"from": [today.isoformat()], "to": [today.isoformat()]}
                body = query_calendar(query)
                body["telegramMessages"] = format_calendar_for_telegram(
                    [STORE.get(str(item["id"])) for item in body["items"]],
                    f"Today's Content Plan\n\n{today.isoformat()}",
                    "No content scheduled for today.",
                )
                json_response(self, HTTPStatus.OK, body)
                return
            if mode == "week":
                json_response(self, HTTPStatus.OK, query_calendar({"from": [today.isoformat()], "to": [(today + timedelta(days=6)).isoformat()]}))
                return
            if mode == "month":
                month_start = today.replace(day=1)
                next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
                month_end = next_month - timedelta(days=1)
                json_response(self, HTTPStatus.OK, query_calendar({"from": [month_start.isoformat()], "to": [month_end.isoformat()]}))
                return
            items = calendar_items(today, today + timedelta(days=365))
            next_item = items[:1]
            json_response(
                self,
                HTTPStatus.OK,
                {
                    "items": [workflow_summary(item) for item in next_item],
                    "telegramMessages": format_calendar_for_telegram(next_item, "Next Scheduled Content", "No scheduled content found."),
                },
            )
            return

        if path == "/api/v1/content-list":
            status = params.get("status", [""])[0].strip()
            limit = parse_int(params.get("limit", ["20"])[0], 20, "limit")
            limit = max(1, min(limit, 100))
            json_response(self, HTTPStatus.OK, list_content_by_status(status, limit))
            return

        if path == "/api/v1/sources":
            json_response(self, HTTPStatus.OK, list_sources(params))
            return

        if path == "/api/v1/candidate-list":
            status = params.get("status", [""])[0].strip()
            limit = parse_int(params.get("limit", ["20"])[0], 20, "limit")
            json_response(self, HTTPStatus.OK, list_candidates_by_status(status, limit))
            return

        package_detail_match = re.fullmatch(r"/api/v1/packages/(pkg_\d{8}_[a-f0-9]{8})", path)
        if package_detail_match:
            json_response(self, HTTPStatus.OK, package_by_id(package_detail_match.group(1)))
            return

        candidate_detail_match = re.fullmatch(r"/api/v1/candidates/(cand_\d{8}_[a-f0-9]{8})", path)
        if candidate_detail_match:
            source, candidate = find_candidate(candidate_detail_match.group(1))
            json_response(self, HTTPStatus.OK, {**candidate, "source": source_summary(source), "telegramMessages": format_candidate_detail_for_telegram(source, candidate)})
            return

        source_review_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/review", path)
        if source_review_match:
            source = SOURCE_STORE.get(source_review_match.group(1))
            json_response(self, HTTPStatus.OK, {**source, "telegramMessages": format_source_review_for_telegram(source)})
            return

        source_candidates_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/candidates", path)
        if source_candidates_match:
            status = params.get("status", [""])[0].strip()
            json_response(self, HTTPStatus.OK, list_candidates_for_source(source_candidates_match.group(1), status))
            return

        source_transcript_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/transcript", path)
        if source_transcript_match:
            source = SOURCE_STORE.get(source_transcript_match.group(1))
            if not isinstance(source.get("transcript"), dict):
                raise AppError(HTTPStatus.NOT_FOUND, "transcript_not_found", "Transcript was not found.")
            json_response(self, HTTPStatus.OK, {**source["transcript"], "telegramMessages": format_transcript_summary_for_telegram(source)})
            return

        source_segments_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/segments", path)
        if source_segments_match:
            source = SOURCE_STORE.get(source_segments_match.group(1))
            transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
            segments = transcript.get("segments") if isinstance(transcript.get("segments"), list) else []
            json_response(self, HTTPStatus.OK, {"sourceId": source.get("sourceId"), "segments": segments, "telegramMessages": format_segments_for_telegram(source)})
            return

        source_detail_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})", path)
        if source_detail_match:
            source = SOURCE_STORE.get(source_detail_match.group(1))
            json_response(self, HTTPStatus.OK, {**source, "summary": source_summary(source), "telegramMessages": format_source_detail_for_telegram(source)})
            return

        segment_detail_match = re.fullmatch(r"/api/v1/segments/(seg_\d{8}_[a-f0-9]{8})", path)
        if segment_detail_match:
            source, transcript, segment = SOURCE_STORE.find_segment(segment_detail_match.group(1))
            json_response(self, HTTPStatus.OK, {**segment, "sourceId": source.get("sourceId"), "transcriptId": transcript.get("transcriptId"), "telegramMessages": format_segment_detail_for_telegram(source, segment)})
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

        review_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/review", path)
        if review_match:
            json_response(self, HTTPStatus.OK, get_review(review_match.group(1)))
            return

        status_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/status", path)
        if status_match:
            json_response(self, HTTPStatus.OK, get_content_status(status_match.group(1)))
            return

        content_source_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/source", path)
        if content_source_match:
            json_response(self, HTTPStatus.OK, source_for_content(content_source_match.group(1)))
            return

        content_candidate_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/candidate", path)
        if content_candidate_match:
            json_response(self, HTTPStatus.OK, candidate_for_content(content_candidate_match.group(1)))
            return

        package_latest_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/package/latest", path)
        if package_latest_match:
            json_response(self, HTTPStatus.OK, latest_package_status(package_latest_match.group(1)))
            return

        packages_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/packages", path)
        if packages_match:
            json_response(self, HTTPStatus.OK, list_packages_for_content(packages_match.group(1)))
            return

        ready_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/ready-to-post", path)
        if ready_match:
            json_response(self, HTTPStatus.OK, ready_to_post_check(ready_match.group(1)))
            return

        checklist_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/posting-checklist", path)
        if checklist_match:
            json_response(self, HTTPStatus.OK, posting_checklist_for_content(checklist_match.group(1)))
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
        path = urlparse.urlparse(self.path).path.rstrip("/")
        body = read_json_body(self)
        if path == "/api/v1/sources":
            json_response(self, HTTPStatus.OK, create_source(body))
            return
        source_highlights_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/highlights", path)
        if source_highlights_match:
            json_response(self, HTTPStatus.OK, generate_highlights_from_source(source_highlights_match.group(1), body))
            return
        segment_highlights_match = re.fullmatch(r"/api/v1/segments/(seg_\d{8}_[a-f0-9]{8})/highlights", path)
        if segment_highlights_match:
            json_response(self, HTTPStatus.OK, generate_highlights_from_segment(segment_highlights_match.group(1), body))
            return
        candidate_approve_match = re.fullmatch(r"/api/v1/candidates/(cand_\d{8}_[a-f0-9]{8})/approve", path)
        if candidate_approve_match:
            json_response(self, HTTPStatus.OK, approve_candidate(candidate_approve_match.group(1)))
            return
        candidate_reject_match = re.fullmatch(r"/api/v1/candidates/(cand_\d{8}_[a-f0-9]{8})/reject", path)
        if candidate_reject_match:
            json_response(self, HTTPStatus.OK, reject_candidate(candidate_reject_match.group(1), body))
            return
        candidate_generate_match = re.fullmatch(r"/api/v1/candidates/(cand_\d{8}_[a-f0-9]{8})/generate-content", path)
        if candidate_generate_match:
            json_response(self, HTTPStatus.OK, generate_content_from_candidate(candidate_generate_match.group(1), body))
            return
        source_approve_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/approve", path)
        if source_approve_match:
            json_response(self, HTTPStatus.OK, approve_source(source_approve_match.group(1)))
            return
        source_restrict_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/restrict", path)
        if source_restrict_match:
            json_response(self, HTTPStatus.OK, restrict_source(source_restrict_match.group(1), body))
            return
        source_credit_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/credit", path)
        if source_credit_match:
            json_response(self, HTTPStatus.OK, set_source_credit(source_credit_match.group(1), body))
            return
        source_transcript_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/transcript", path)
        if source_transcript_match:
            json_response(self, HTTPStatus.OK, add_transcript(source_transcript_match.group(1), body))
            return
        source_segments_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/segments/generate", path)
        if source_segments_match:
            json_response(self, HTTPStatus.OK, generate_segments(source_segments_match.group(1)))
            return
        source_ideas_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/ideas", path)
        if source_ideas_match:
            json_response(self, HTTPStatus.OK, ideas_from_source(source_ideas_match.group(1)))
            return
        source_generate_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/generate-content", path)
        if source_generate_match:
            json_response(self, HTTPStatus.OK, generate_content_from_source(source_generate_match.group(1), body))
            return
        segment_generate_match = re.fullmatch(r"/api/v1/segments/(seg_\d{8}_[a-f0-9]{8})/generate-content", path)
        if segment_generate_match:
            json_response(self, HTTPStatus.OK, generate_content_from_segment(segment_generate_match.group(1), body))
            return
        approve_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/approve", path)
        if approve_match:
            json_response(self, HTTPStatus.OK, approve_content(approve_match.group(1), body))
            return
        reject_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/reject", path)
        if reject_match:
            json_response(self, HTTPStatus.OK, reject_content(reject_match.group(1), body))
            return
        schedule_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/schedule", path)
        if schedule_match:
            json_response(self, HTTPStatus.OK, schedule_content(schedule_match.group(1), body))
            return
        uploaded_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/uploaded", path)
        if uploaded_match:
            json_response(self, HTTPStatus.OK, mark_uploaded(uploaded_match.group(1), body))
            return
        package_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/package", path)
        if package_match:
            json_response(self, HTTPStatus.OK, generate_content_package(package_match.group(1), body))
            return
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

    def handle_patch(self) -> None:
        path = urlparse.urlparse(self.path).path.rstrip("/")
        body = read_json_body(self)
        source_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})", path)
        if source_match:
            json_response(self, HTTPStatus.OK, update_source(source_match.group(1), body))
            return
        segment_match = re.fullmatch(r"/api/v1/segments/(seg_\d{8}_[a-f0-9]{8})", path)
        if segment_match:
            json_response(self, HTTPStatus.OK, update_segment(segment_match.group(1), body))
            return
        slide_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/slides/(\d+)", path)
        if slide_match:
            json_response(self, HTTPStatus.OK, edit_slide(slide_match.group(1), int(slide_match.group(2)), body))
            return
        caption_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/caption", path)
        if caption_match:
            json_response(self, HTTPStatus.OK, edit_caption(caption_match.group(1), body))
            return
        voiceover_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/voiceover", path)
        if voiceover_match:
            json_response(self, HTTPStatus.OK, edit_voiceover(voiceover_match.group(1), body))
            return
        status_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/status", path)
        if status_match:
            json_response(self, HTTPStatus.OK, update_content_status(status_match.group(1), body))
            return
        raise AppError(HTTPStatus.NOT_FOUND, "not_found", "Route not found.")

    def handle_delete(self) -> None:
        path = urlparse.urlparse(self.path).path.rstrip("/")
        schedule_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/schedule", path)
        if schedule_match:
            json_response(self, HTTPStatus.OK, unschedule_content(schedule_match.group(1)))
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
