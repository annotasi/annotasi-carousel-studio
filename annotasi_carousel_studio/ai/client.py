from __future__ import annotations

from ..common import *
from ..config import *
from ..errors import *
from ..storage.content_store import STORE, JsonContentStore
from ..storage.source_store import SOURCE_STORE, JsonSourceStore
from ..utils.ids import *
from ..utils.time import *
from ..utils.text import *
from ..utils.media import *
from ..ai.prompts import *


def _preview(value: Any, limit: int = 500) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text[:limit]


def _content_from_message_parts(parts: list[Any]) -> str:
    texts = []
    for part in parts:
        if isinstance(part, str):
            texts.append(part)
        elif isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str):
                texts.append(text)
            elif isinstance(text, dict) and isinstance(text.get("value"), str):
                texts.append(text["value"])
    return "\n".join(texts)


def extract_ai_response_payload(envelope: Any) -> Any:
    if not isinstance(envelope, dict):
        return envelope
    choices = envelope.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict) and "content" in message:
                content = message.get("content")
                if isinstance(content, list):
                    return _content_from_message_parts(content)
                return content
            if "text" in first:
                return first.get("text")
    if "output_text" in envelope:
        return envelope.get("output_text")
    if "content" in envelope:
        return envelope.get("content")
    return envelope


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
    status_code: Any = None
    content_type = ""
    try:
        with urlrequest.urlopen(req, timeout=AI_TIMEOUT_SECONDS) as response:
            status_code = response.getcode()
            content_type = response.headers.get("Content-Type", "")
            raw = response.read().decode("utf-8")
    except urlerror.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        LOGGER.warning(
            "ai_request_failed status=%s content_type=%s preview=%r",
            exc.code,
            exc.headers.get("Content-Type", ""),
            _preview(body),
        )
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_http_error", "AI endpoint returned an error.") from exc
    except urlerror.URLError as exc:
        LOGGER.warning("ai_request_failed reason=%s", exc.reason)
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_unavailable", "AI endpoint is unavailable.") from exc
    except TimeoutError as exc:
        LOGGER.warning("ai_request_failed reason=timeout")
        raise AppError(HTTPStatus.GATEWAY_TIMEOUT, "ai_timeout", "AI endpoint timed out.") from exc

    LOGGER.info("ai_response_received elapsed_ms=%d", int((time.time() - started) * 1000))
    try:
        try:
            envelope = json.loads(raw)
        except json.JSONDecodeError:
            parsed = extract_first_json_value(raw)
        else:
            if isinstance(envelope, dict) and "error" in envelope and not any(key in envelope for key in ("choices", "content", "output_text")):
                LOGGER.warning(
                    "ai_request_failed status=%s content_type=%s preview=%r",
                    status_code,
                    content_type,
                    _preview(envelope),
                )
                raise AppError(HTTPStatus.BAD_GATEWAY, "ai_http_error", "AI endpoint returned an error.")
            generated = extract_ai_response_payload(envelope)
            if isinstance(generated, (dict, list)):
                parsed = generated
            elif isinstance(generated, str):
                parsed = extract_first_json_value(generated)
            else:
                raise ValueError("AI response did not contain generated text.")
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        LOGGER.warning(
            "ai_invalid_json status=%s content_type=%s parse_error=%s preview=%r",
            status_code,
            content_type,
            exc,
            _preview(raw),
        )
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_invalid_json", "AI returned invalid JSON.") from exc
    if not isinstance(parsed, dict):
        LOGGER.warning(
            "ai_invalid_json status=%s content_type=%s parse_error=%s preview=%r",
            status_code,
            content_type,
            "AI JSON response must be an object.",
            _preview(parsed),
        )
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_invalid_json", "AI JSON response must be an object.")
    return parsed
