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


def _source_candidates(source: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = source.get("candidates")
    return candidates if isinstance(candidates, list) else []


def _candidate_counts(source: dict[str, Any]) -> dict[str, int]:
    counts = {"total": 0, "approved": 0, "converted_to_content": 0, "rejected": 0}
    for candidate in _source_candidates(source):
        counts["total"] += 1
        status = str(candidate.get("candidateStatus") or "")
        if status in counts:
            counts[status] += 1
    return counts


def source_summary(source: dict[str, Any]) -> dict[str, Any]:
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
    segments = transcript.get("segments") if isinstance(transcript, dict) else []
    links = source.get("generatedContent") if isinstance(source.get("generatedContent"), list) else []
    counts = _candidate_counts(source)
    return {
        "sourceId": source.get("sourceId"),
        "title": source.get("title", ""),
        "speakerName": source.get("speakerName", ""),
        "sourceUrl": source.get("sourceUrl", ""),
        "platform": source.get("platform", ""),
        "sourceType": source.get("sourceType", ""),
        "permissionStatus": source.get("permissionStatus", ""),
        "sourceStatus": source.get("sourceStatus", ""),
        "creditText": source.get("creditText", ""),
        "topic": source.get("topic", ""),
        "language": source.get("language", ""),
        "transcriptAvailable": bool(transcript.get("transcriptText")),
        "segmentCount": len(segments) if isinstance(segments, list) else 0,
        "generatedContentCount": len(links),
        "candidateCount": counts["total"],
        "approvedCandidateCount": counts["approved"],
        "convertedCandidateCount": counts["converted_to_content"],
        "rejectedCandidateCount": counts["rejected"],
        "contextNotes": source.get("contextNotes", ""),
    }

def format_source_list_for_telegram(sources: list[dict[str, Any]]) -> list[str]:
    if not sources:
        return ["Source List\n\nNo sources found."]
    lines = ["Source List", ""]
    for index, source in enumerate(sources, start=1):
        summary = source_summary(source)
        lines.extend(
            [
                f"{index}. {summary['sourceId']} - {summary['title']}",
                f"Speaker: {summary['speakerName'] or '-'}",
                f"Permission: {summary['permissionStatus']}",
                f"Status: {summary['sourceStatus']}",
                "",
            ]
        )
    return split_telegram_message("\n".join(lines).strip())


def format_source_detail_for_telegram(source: dict[str, Any]) -> list[str]:
    summary = source_summary(source)
    transcript_status = "available" if summary["transcriptAvailable"] else "not_available"
    text = "\n".join(
        [
            "Source Detail",
            "",
            "Source ID:",
            str(summary["sourceId"]),
            "",
            "Title:",
            str(summary["title"]),
            "",
            "Speaker:",
            str(summary["speakerName"] or "-"),
            "",
            "URL:",
            str(summary["sourceUrl"] or "-"),
            "",
            "Permission:",
            str(summary["permissionStatus"]),
            "",
            "Credit:",
            str(summary["creditText"] or "-"),
            "",
            "Status:",
            str(summary["sourceStatus"]),
            "",
            "Transcript:",
            transcript_status,
            "",
            "Generated content:",
            f"{summary['generatedContentCount']} items",
            "",
            "Candidates:",
            f"{summary['candidateCount']} total, {summary['approvedCandidateCount']} approved, {summary['convertedCandidateCount']} converted, {summary['rejectedCandidateCount']} rejected",
            "",
            "Notes:",
            str(summary["contextNotes"] or "-"),
        ]
    )
    return split_telegram_message(text)


def format_source_review_for_telegram(source: dict[str, Any]) -> list[str]:
    checklist = [
        "Source URL is valid",
        "Speaker/source is clear",
        "Permission status is checked",
        "Credit text is ready",
        "Topic is appropriate",
        "No misleading use intended",
        "Not a restricted source",
        "Monetization risk understood",
        "Manual context review required before posting",
    ]
    lines = [
        "Source Review",
        "",
        "Source ID:",
        str(source.get("sourceId")),
        "",
        "Title:",
        str(source.get("title", "")),
        "",
        "Permission:",
        str(source.get("permissionStatus", "")),
        "",
        "Checklist:",
    ]
    lines.extend([f"[ ] {item}" for item in checklist])
    lines.extend(
        [
            "",
            "Reminder:",
            "Boleh disebarkan untuk dakwah belum tentu otomatis aman untuk monetisasi. Tetap beri sumber dan nilai tambah.",
        ]
    )
    return split_telegram_message("\n".join(lines).strip())


def format_transcript_summary_for_telegram(source: dict[str, Any]) -> list[str]:
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
    text = str(transcript.get("transcriptText") or "")
    segments = transcript.get("segments") if isinstance(transcript.get("segments"), list) else []
    preview = text[:500] + ("..." if len(text) > 500 else "")
    lines = [
        "Transcript Summary",
        "",
        "Source ID:",
        str(source.get("sourceId")),
        "",
        "Transcript ID:",
        str(transcript.get("transcriptId") or "-"),
        "",
        "Length:",
        f"{len(text)} characters",
        "",
        "Segments:",
        str(len(segments)),
        "",
        "Status:",
        str(transcript.get("transcriptStatus") or "not_available"),
        "",
        "Preview:",
        preview or "-",
    ]
    return split_telegram_message("\n".join(lines).strip())


def time_label(seconds: Any) -> str:
    if seconds is None:
        return "unknown"
    try:
        total = int(seconds)
    except (TypeError, ValueError):
        return "unknown"
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def format_segments_for_telegram(source: dict[str, Any]) -> list[str]:
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
    segments = transcript.get("segments") if isinstance(transcript.get("segments"), list) else []
    if not segments:
        return ["Transcript Segments\n\nNo segments found."]
    lines = ["Transcript Segments", ""]
    for index, segment in enumerate(segments, start=1):
        preview = str(segment.get("text") or "")[:180]
        lines.extend(
            [
                f"{index}. {segment.get('segmentId')}",
                f"Time: {time_label(segment.get('startTimeSeconds'))} - {time_label(segment.get('endTimeSeconds'))}",
                f"Topic: {segment.get('topic') or '-'}",
                f"Risk: {segment.get('riskLevel')}",
                f"Preview: {preview}",
                "",
            ]
        )
    return split_telegram_message("\n".join(lines).strip())


def format_segment_detail_for_telegram(source: dict[str, Any], segment: dict[str, Any]) -> list[str]:
    linked_count = sum(1 for candidate in _source_candidates(source) if candidate.get("segmentId") == segment.get("segmentId"))
    text = "\n".join(
        [
            "Segment Detail",
            "",
            "Segment ID:",
            str(segment.get("segmentId")),
            "",
            "Source:",
            str(source.get("sourceId")),
            "",
            "Time:",
            f"{time_label(segment.get('startTimeSeconds'))} - {time_label(segment.get('endTimeSeconds'))}",
            "",
            "Risk:",
            str(segment.get("riskLevel")),
            "",
            "Text:",
            str(segment.get("text") or ""),
            "",
            "Context notes:",
            str(segment.get("contextNotes") or "-"),
            "",
            "Linked candidates:",
            str(linked_count),
        ]
    )
    return split_telegram_message(text)
