from __future__ import annotations

from ..common import *
from ..config import *
from ..errors import *

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


STORE = JsonContentStore(STORAGE_DIR)
