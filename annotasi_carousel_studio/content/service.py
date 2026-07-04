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
from ..ai.client import *
from ..ai.prompts import *
from ..ai.validators import *
from ..content.workflow import *
from ..content.formatter import *

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
