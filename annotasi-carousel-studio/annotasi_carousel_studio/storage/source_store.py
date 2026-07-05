from __future__ import annotations

from ..common import *
from ..config import *
from ..errors import *

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


SOURCE_STORE = JsonSourceStore(SOURCE_STORAGE_DIR)
