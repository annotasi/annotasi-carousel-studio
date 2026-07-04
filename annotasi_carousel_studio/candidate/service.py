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
from ..source.service import *
from ..source.transcript import *
from ..candidate.formatter import *

def validate_candidate_type(value: str) -> str:
    normalized = (value or "mixed").strip().lower()
    if normalized not in SUPPORTED_CANDIDATE_TYPES:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_candidate_type", "Candidate type is invalid.")
    return normalized


def validate_candidate_status(value: str) -> str:
    normalized = (value or "suggested").strip().lower()
    if normalized not in SUPPORTED_CANDIDATE_STATUSES:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_candidate_status", "Candidate status is invalid.")
    return normalized


def source_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = source.get("candidates")
    return candidates if isinstance(candidates, list) else []


def candidate_counts(source: dict[str, Any]) -> dict[str, int]:
    counts = {"total": 0, "approved": 0, "converted_to_content": 0, "rejected": 0}
    for candidate in source_candidates(source):
        counts["total"] += 1
        status = str(candidate.get("candidateStatus") or "")
        if status in counts:
            counts[status] += 1
    return counts


def find_candidate(item_candidate_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if not re.fullmatch(r"cand_\d{8}_[a-f0-9]{8}", item_candidate_id):
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_candidate_id", "Candidate ID format is invalid.")
    for source in SOURCE_STORE.list_records():
        for candidate in source_candidates(source):
            if candidate.get("candidateId") == item_candidate_id:
                return source, candidate
    raise AppError(HTTPStatus.NOT_FOUND, "candidate_not_found", "Candidate was not found.")


def normalized_title(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def candidate_permission_warnings(source: dict[str, Any]) -> list[str]:
    permission = str(source.get("permissionStatus") or "unknown")
    status = str(source.get("sourceStatus") or "draft")
    warnings = []
    if status == "restricted" or permission in {"restricted", "rejected"}:
        if CANDIDATE_BLOCK_RESTRICTED_SOURCE:
            raise AppError(HTTPStatus.CONFLICT, "source_restricted", "Source is restricted or rejected.")
        warnings.append("Source is restricted or rejected. Manual review is required.")
    if permission == "unknown":
        if not CANDIDATE_ALLOW_UNKNOWN_PERMISSION:
            raise AppError(HTTPStatus.CONFLICT, "source_permission_unknown", "Source permission is unknown.")
        warnings.append("Source permission is unknown. Review permission and credit before posting.")
    if permission == "needs_permission":
        warnings.append("Source needs permission. Do not publish without permission review.")
    if permission == "allowed_for_dakwah":
        warnings.append("Boleh disebarkan untuk dakwah belum tentu otomatis aman untuk monetisasi. Tetap beri sumber dan nilai tambah.")
    return warnings


def candidate_context_from_source(source: dict[str, Any], max_segments: int) -> tuple[dict[str, Any], str]:
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else None
    if not transcript or not transcript.get("transcriptText"):
        raise AppError(HTTPStatus.NOT_FOUND, "transcript_not_found", "Transcript is required for highlight generation.")
    segments = transcript.get("segments") if isinstance(transcript.get("segments"), list) else []
    if segments:
        selected = segments[:max_segments]
        context = "\n\n".join(
            f"segmentId={segment.get('segmentId')} risk={segment.get('riskLevel')}\n{segment.get('text')}"
            for segment in selected
        )
    else:
        context = str(transcript.get("transcriptText") or "")
    if len(context) > CANDIDATE_MAX_TRANSCRIPT_CHARS:
        context = context[:CANDIDATE_MAX_TRANSCRIPT_CHARS] + "\n\n[Transcript truncated for analysis. Manual review required.]"
    return transcript, context


def save_candidates(source: dict[str, Any], new_candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = source.get("candidates")
    if not isinstance(candidates, list):
        candidates = []
        source["candidates"] = candidates
    existing_titles = {normalized_title(str(item.get("title") or "")) for item in candidates if isinstance(item, dict)}
    saved = []
    for candidate in new_candidates:
        key = normalized_title(candidate["title"])
        if not key or key in existing_titles:
            continue
        candidates.append(candidate)
        existing_titles.add(key)
        saved.append(candidate)
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("candidates_saved source_id=%s count=%d", source.get("sourceId"), len(saved))
    return saved


def generate_highlights_from_source(source_id_value: str, body: dict[str, Any]) -> dict[str, Any]:
    source = SOURCE_STORE.get(source_id_value)
    warnings = candidate_permission_warnings(source)
    candidate_count = max(1, min(parse_int(body.get("candidateCount"), CANDIDATE_DEFAULT_COUNT, "candidateCount"), 10))
    preferred = body.get("preferredTypes")
    preferred_types = [validate_candidate_type(str(item)) for item in preferred] if isinstance(preferred, list) else sorted(CANDIDATE_ALLOWED_TYPES)
    transcript, context = candidate_context_from_source(source, min(parse_int(body.get("maxSegments"), CANDIDATE_MAX_SEGMENTS_PER_RUN, "maxSegments"), CANDIDATE_MAX_SEGMENTS_PER_RUN))
    LOGGER.info("highlight_generation_requested source_id=%s", source_id_value)
    result = call_ai_json(
        [
            {"role": "system", "content": system_prompt()},
            {
                "role": "user",
                "content": highlight_candidates_prompt(
                    source,
                    transcript,
                    context,
                    candidate_count=candidate_count,
                    preferred_types=preferred_types,
                ),
            },
        ]
    )
    raw_candidates = result.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_no_candidates", "AI returned no candidates.")
    candidates = [validate_candidate_payload(item, source, transcript) for item in raw_candidates if isinstance(item, dict)]
    allow_high_risk = parse_bool(body.get("allowHighRisk"), CANDIDATE_ALLOW_HIGH_RISK)
    candidates = [item for item in candidates if allow_high_risk or item["riskLevel"] != "high"]
    if not candidates:
        raise AppError(HTTPStatus.CONFLICT, "high_risk_candidate_blocked", "Only high-risk candidates were returned and high-risk candidates are blocked.")
    saved = save_candidates(source, candidates[:candidate_count])
    if not saved:
        raise AppError(HTTPStatus.CONFLICT, "duplicate_candidate", "No new candidates were saved.")
    lines = ["Highlight Candidates Generated", "", "Source:", source_id_value, "", "Title:", str(source.get("title")), "", "Candidates:", ""]
    for index, candidate in enumerate(saved, start=1):
        lines.extend([f"{index}. {candidate['candidateId']}", f"Type: {candidate['candidateType']}", f"Title: {candidate['title']}", f"Risk: {candidate['riskLevel']}", f"Needs context: {'yes' if candidate['needsContext'] else 'no'}", ""])
    if warnings:
        lines.extend(["Warnings:", *[f"- {warning}" for warning in warnings], ""])
    lines.extend(["Next actions:", f"/candidate {saved[0]['candidateId']}", f"/candidate_approve {saved[0]['candidateId']}", f"/generate_from_candidate {saved[0]['candidateId']}", "", "Reminder:", "Review kembali konteks sebelum upload agar tidak salah makna."])
    return {"sourceId": source_id_value, "analysisSummary": result.get("analysisSummary", ""), "warnings": warnings, "candidates": saved, "telegramMessages": split_telegram_message("\n".join(lines).strip())}


def generate_highlights_from_segment(item_segment_id: str, body: dict[str, Any]) -> dict[str, Any]:
    source, transcript, segment = SOURCE_STORE.find_segment(item_segment_id)
    warnings = candidate_permission_warnings(source)
    if segment.get("riskLevel") == "high":
        warnings.append("Segment risk is high. Manual context review is required.")
    candidate_count = max(1, min(parse_int(body.get("candidateCount"), 5, "candidateCount"), 5))
    result = call_ai_json(
        [
            {"role": "system", "content": system_prompt()},
            {
                "role": "user",
                "content": highlight_candidates_prompt(
                    source,
                    transcript,
                    str(segment.get("text") or ""),
                    candidate_count=candidate_count,
                    preferred_types=sorted(CANDIDATE_ALLOWED_TYPES),
                    segment=segment,
                ),
            },
        ]
    )
    raw_candidates = result.get("candidates")
    if not isinstance(raw_candidates, list) or not raw_candidates:
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_no_candidates", "AI returned no candidates.")
    candidates = [validate_candidate_payload(item, source, transcript, item_segment_id) for item in raw_candidates if isinstance(item, dict)]
    allow_high_risk = parse_bool(body.get("allowHighRisk"), CANDIDATE_ALLOW_HIGH_RISK)
    candidates = [item for item in candidates if allow_high_risk or item["riskLevel"] != "high"]
    if not candidates:
        raise AppError(HTTPStatus.CONFLICT, "high_risk_candidate_blocked", "Only high-risk candidates were returned and high-risk candidates are blocked.")
    saved = save_candidates(source, candidates[:candidate_count])
    if not saved:
        raise AppError(HTTPStatus.CONFLICT, "duplicate_candidate", "No new candidates were saved.")
    return {"sourceId": source["sourceId"], "segmentId": item_segment_id, "warnings": warnings, "candidates": saved, "telegramMessages": format_candidates_for_telegram(source, saved)}


def list_candidates_for_source(source_id_value: str, status: str = "") -> dict[str, Any]:
    source = SOURCE_STORE.get(source_id_value)
    if status:
        status = validate_candidate_status(status)
    candidates = [candidate for candidate in source_candidates(source) if not status or candidate.get("candidateStatus") == status]
    return {"sourceId": source_id_value, "candidates": candidates, "telegramMessages": format_candidates_for_telegram(source, candidates)}


def list_candidates_by_status(status: str = "", limit: int = 20) -> dict[str, Any]:
    if status:
        status = validate_candidate_status(status)
    items = []
    for source in SOURCE_STORE.list_records():
        for candidate in source_candidates(source):
            if status and candidate.get("candidateStatus") != status:
                continue
            items.append((source, candidate))
    items.sort(key=lambda pair: str(pair[1].get("createdAt") or ""), reverse=True)
    selected = items[: max(1, min(limit, 100))]
    lines = ["Candidate List", "", "Status:", status or "all", ""]
    for index, (_source, candidate) in enumerate(selected, start=1):
        lines.append(f"{index}. {candidate.get('candidateId')} - {candidate.get('title')} ({candidate.get('candidateStatus')})")
    if not selected:
        lines.append("No candidates found.")
    return {"status": status or "all", "candidates": [candidate for _source, candidate in selected], "telegramMessages": split_telegram_message("\n".join(lines).strip())}


def approve_candidate(item_candidate_id: str) -> dict[str, Any]:
    source, candidate = find_candidate(item_candidate_id)
    if candidate.get("candidateStatus") == "rejected":
        raise AppError(HTTPStatus.CONFLICT, "candidate_already_rejected", "Rejected candidate cannot be approved without manual status change.")
    candidate["candidateStatus"] = "approved"
    candidate["updatedAt"] = now_iso()
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("candidate_approved candidate_id=%s", item_candidate_id)
    return {**candidate, "telegramMessages": split_telegram_message(f"Candidate approved.\n\nNext action:\n/generate_from_candidate {item_candidate_id}")}


def reject_candidate(item_candidate_id: str, body: dict[str, Any]) -> dict[str, Any]:
    reason = str(body.get("reason") or "").strip()
    source, candidate = find_candidate(item_candidate_id)
    candidate["candidateStatus"] = "rejected"
    candidate["rejectionReason"] = reason
    candidate["updatedAt"] = now_iso()
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("candidate_rejected candidate_id=%s", item_candidate_id)
    return {**candidate, "telegramMessages": split_telegram_message(f"Candidate rejected.\n\nReason:\n{reason or '-'}")}


def generate_content_from_candidate(item_candidate_id: str, body: dict[str, Any]) -> dict[str, Any]:
    source, candidate = find_candidate(item_candidate_id)
    if candidate.get("candidateStatus") == "rejected":
        raise AppError(HTTPStatus.CONFLICT, "candidate_already_rejected", "Candidate is rejected.")
    if candidate.get("candidateStatus") == "converted_to_content":
        raise AppError(HTTPStatus.CONFLICT, "candidate_already_converted", "Candidate has already been converted to content.")
    if candidate.get("candidateStatus") != "approved":
        raise AppError(HTTPStatus.CONFLICT, "candidate_not_approved", "Candidate must be approved before content generation.")
    allow_high_risk = parse_bool(body.get("allowHighRisk"), CANDIDATE_ALLOW_HIGH_RISK)
    if candidate.get("riskLevel") == "high" and not allow_high_risk:
        raise AppError(HTTPStatus.CONFLICT, "high_risk_candidate_blocked", "High-risk candidate is blocked by configuration.")
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
    segment = None
    if candidate.get("segmentId"):
        try:
            _source, _transcript, segment = SOURCE_STORE.find_segment(str(candidate["segmentId"]))
        except AppError:
            segment = None
    content = call_ai_json(
        [
            {"role": "system", "content": system_prompt()},
            {"role": "user", "content": candidate_content_prompt(source, transcript, candidate, segment)},
        ]
    )
    content = validate_content(content)
    warnings = []
    if candidate.get("needsContext"):
        warnings.append(str(candidate.get("contextWarning") or "Review candidate context manually."))
    if candidate.get("riskLevel") in {"medium", "high"}:
        warnings.append(f"Candidate risk is {candidate.get('riskLevel')}. Manual review required.")
    content["safetyNotes"].extend([warning for warning in warnings if warning])
    item_id = content_id()
    record = {
        "id": item_id,
        "status": "needs_review",
        "topic": candidate.get("title") or source.get("topic") or source.get("title"),
        "niche": "annotasi_hikmah",
        "tone": "calm_reflective",
        "platform": "instagram",
        "content": content,
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    ensure_workflow(record)
    set_workflow_status(record, "needs_review")
    transcript_dict = transcript if isinstance(transcript, dict) else None
    source_link = link_source_to_content(record, source, transcript_dict, segment)
    candidate_link = {"candidateId": item_candidate_id, "contentId": item_id, "createdAt": now_iso()}
    record["candidateLink"] = {**candidate_link, "sourceId": source.get("sourceId"), "segmentId": candidate.get("segmentId"), "riskLevel": candidate.get("riskLevel")}
    links = candidate.get("contentLinks")
    if not isinstance(links, list):
        links = []
        candidate["contentLinks"] = links
    links.append(candidate_link)
    candidate["candidateStatus"] = "converted_to_content"
    candidate["updatedAt"] = now_iso()
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    STORE.save(record)
    LOGGER.info("content_generated_from_candidate candidate_id=%s content_id=%s", item_candidate_id, item_id)
    lines = [
        "Content Generated from Candidate",
        "",
        "Content ID:",
        item_id,
        "",
        "Candidate:",
        item_candidate_id,
        "",
        "Title:",
        str(content.get("title")),
        "",
        "Status:",
        "needs_review",
        "",
        "Next actions:",
        f"/review {item_id}",
        f"/approve {item_id}",
        f"/render {item_id}",
        "",
        "Reminder:",
        "Review kembali sebelum upload agar tidak salah konteks.",
    ]
    return {"id": item_id, "status": "needs_review", "content": content, "sourceLink": source_link, "candidateLink": record["candidateLink"], "warnings": warnings, "telegramMessages": split_telegram_message("\n".join(lines).strip())}


def candidate_for_content(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    link = record.get("candidateLink")
    if not isinstance(link, dict) or not link.get("candidateId"):
        raise AppError(HTTPStatus.NOT_FOUND, "candidate_link_not_found", "Content has no linked candidate.")
    source, candidate = find_candidate(str(link["candidateId"]))
    lines = [
        "Content Candidate",
        "",
        "Content ID:",
        item_id,
        "",
        "Candidate ID:",
        str(candidate.get("candidateId")),
        "",
        "Source:",
        str(source.get("sourceId")),
        "",
        "Segment:",
        str(candidate.get("segmentId") or "none"),
        "",
        "Risk:",
        str(candidate.get("riskLevel")),
    ]
    return {"contentId": item_id, "candidate": candidate, "source": source_summary(source), "telegramMessages": split_telegram_message("\n".join(lines).strip())}
