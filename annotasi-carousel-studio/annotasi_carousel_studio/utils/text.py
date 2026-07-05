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
    fence_match = re.fullmatch(r"```(?:\s*json)?\s*\n?(.*?)\n?\s*```", stripped, flags=re.IGNORECASE | re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```\s*(?:json)?\s*\n?", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\n?\s*```$", "", stripped)
    return stripped.strip()


def _extract_balanced_json_candidate(text: str, start: int) -> str:
    opener = text[start]
    closer = "}" if opener == "{" else "]"
    stack = [closer]
    in_string = False
    escaped = False
    for index in range(start + 1, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            stack.append("}")
        elif char == "[":
            stack.append("]")
        elif char in {"}", "]"}:
            if not stack or char != stack[-1]:
                raise ValueError("Unbalanced JSON delimiters.")
            stack.pop()
            if not stack:
                return text[start : index + 1]
    raise ValueError("No balanced JSON value found.")


def extract_first_json_value(text: str) -> Any:
    stripped = text.strip()
    if not stripped:
        raise ValueError("Empty AI response.")
    try:
        return json.loads(stripped)
    except json.JSONDecodeError as direct_error:
        parse_error: Exception = direct_error

    fenced = strip_json_fence(stripped)
    if fenced != stripped:
        try:
            return json.loads(fenced)
        except json.JSONDecodeError as fenced_error:
            parse_error = fenced_error

    starts = [(index, char) for index, char in enumerate(stripped) if char in "{["]
    for index, _char in starts:
        try:
            candidate = _extract_balanced_json_candidate(stripped, index)
            return json.loads(candidate)
        except (ValueError, json.JSONDecodeError) as scan_error:
            parse_error = scan_error
            continue
    raise ValueError(str(parse_error))


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
