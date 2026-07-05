from __future__ import annotations

from ..common import *
from ..config import *
from ..errors import *

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
