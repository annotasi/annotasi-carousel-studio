from __future__ import annotations

from ..common import *
from ..config import *
from ..errors import *

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


def slugify(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return (slug[:80].strip("-") or fallback).lower()


def hashtag_text(hashtags: list[str], multiline: bool = False) -> str:
    if multiline:
        return "\n".join(hashtags)
    return " ".join(hashtags)


def short_caption(caption: str, limit: int = 220) -> str:
    compact = re.sub(r"\s+", " ", caption).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 3].rstrip() + "..."
