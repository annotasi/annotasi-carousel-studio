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
from ..content.formatter import *
from ..content.workflow import *
from ..source.formatter import *
from ..source.transcript import *

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
