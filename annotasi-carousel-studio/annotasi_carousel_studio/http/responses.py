from __future__ import annotations

from ..common import *
from ..errors import *

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
