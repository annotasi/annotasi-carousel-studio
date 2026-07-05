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
