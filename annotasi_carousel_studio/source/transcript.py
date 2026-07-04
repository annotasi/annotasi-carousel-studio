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
from ..source.formatter import *

def validate_risk_level(value: str) -> str:
    normalized = (value or "low").strip().lower()
    if normalized not in SUPPORTED_RISK_LEVELS:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_risk_level", "Risk level is invalid.")
    return normalized


def add_transcript(source_id_value: str, body: dict[str, Any]) -> dict[str, Any]:
    transcript_text = str(body.get("transcriptText") or body.get("text") or "").strip()
    if not transcript_text:
        raise AppError(HTTPStatus.BAD_REQUEST, "empty_transcript", "Transcript text is required.")
    if len(transcript_text) > TRANSCRIPT_MAX_CHARS_DIRECT:
        raise AppError(HTTPStatus.BAD_REQUEST, "transcript_too_long", "Transcript is too long for direct input.")
    source = SOURCE_STORE.get(source_id_value)
    transcript = {
        "transcriptId": transcript_id(),
        "sourceId": source_id_value,
        "transcriptText": transcript_text,
        "language": str(body.get("language") or source.get("language") or SOURCE_DEFAULT_LANGUAGE),
        "transcriptStatus": "available",
        "segments": [],
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    source["transcript"] = transcript
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("transcript_added source_id=%s transcript_id=%s chars=%d", source_id_value, transcript["transcriptId"], len(transcript_text))
    text = "\n".join(
        [
            "Transcript saved.",
            "",
            "Transcript ID:",
            transcript["transcriptId"],
            "",
            "Source ID:",
            source_id_value,
            "",
            "Length:",
            f"{len(transcript_text)} characters",
            "",
            "Next actions:",
            f"/transcript {source_id_value}",
            f"/segments_generate {source_id_value}",
            f"/ideas_from_source {source_id_value}",
        ]
    )
    return {**transcript, "telegramMessages": split_telegram_message(text)}


def parse_timestamp_parts(hour: Optional[str], minute: str, second: str) -> int:
    h = int(hour[:-1]) if hour else 0
    return h * 3600 + int(minute) * 60 + int(second)


def segment_risk_for_text(text: str) -> str:
    lowered = text.lower()
    high_markers = ["hadits", "hadith", "quran", "alquran", "ayat", "fatwa", "haram", "halal", "riba"]
    medium_markers = ["ustadz", "hukum", "dalil", "dosa", "surga", "neraka"]
    if any(marker in lowered for marker in high_markers):
        return "high"
    if any(marker in lowered for marker in medium_markers):
        return "medium"
    return "low"


def generate_segments(source_id_value: str) -> dict[str, Any]:
    source = SOURCE_STORE.get(source_id_value)
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else None
    if not transcript or not transcript.get("transcriptText"):
        raise AppError(HTTPStatus.NOT_FOUND, "transcript_not_found", "Transcript was not found.")
    LOGGER.info("transcript_segmentation_started source_id=%s", source_id_value)
    text = str(transcript["transcriptText"])
    segments = []
    timestamped = []
    for line in text.splitlines():
        match = TIMESTAMP_LINE_RE.match(line)
        if match and match.group(7).strip():
            start = parse_timestamp_parts(match.group(1), match.group(2), match.group(3))
            end = parse_timestamp_parts(match.group(4), match.group(5), match.group(6)) if match.group(5) else None
            timestamped.append((start, end, match.group(7).strip()))
    if timestamped:
        for index, (start, end, segment_text) in enumerate(timestamped):
            next_start = timestamped[index + 1][0] if index + 1 < len(timestamped) else None
            segments.append(
                {
                    "segmentId": segment_id(),
                    "transcriptId": transcript["transcriptId"],
                    "sourceId": source_id_value,
                    "startTimeSeconds": start,
                    "endTimeSeconds": end if end is not None else next_start,
                    "text": segment_text,
                    "topic": source.get("topic", ""),
                    "contextNotes": "",
                    "riskLevel": segment_risk_for_text(segment_text),
                    "createdAt": now_iso(),
                    "updatedAt": now_iso(),
                }
            )
    else:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
        chunk = []
        count = 0
        for paragraph in paragraphs or [text]:
            words = paragraph.split()
            if chunk and count + len(words) > TRANSCRIPT_SEGMENT_MAX_WORDS:
                segment_text = "\n\n".join(chunk)
                segments.append(
                    {
                        "segmentId": segment_id(),
                        "transcriptId": transcript["transcriptId"],
                        "sourceId": source_id_value,
                        "startTimeSeconds": None,
                        "endTimeSeconds": None,
                        "text": segment_text,
                        "topic": source.get("topic", ""),
                        "contextNotes": "Timestamp tidak tersedia. Segment dibuat berdasarkan struktur teks.",
                        "riskLevel": segment_risk_for_text(segment_text),
                        "createdAt": now_iso(),
                        "updatedAt": now_iso(),
                    }
                )
                chunk = []
                count = 0
            chunk.append(paragraph)
            count += len(words)
        if chunk:
            segment_text = "\n\n".join(chunk)
            segments.append(
                {
                    "segmentId": segment_id(),
                    "transcriptId": transcript["transcriptId"],
                    "sourceId": source_id_value,
                    "startTimeSeconds": None,
                    "endTimeSeconds": None,
                    "text": segment_text,
                    "topic": source.get("topic", ""),
                    "contextNotes": "Timestamp tidak tersedia. Segment dibuat berdasarkan struktur teks.",
                    "riskLevel": segment_risk_for_text(segment_text),
                    "createdAt": now_iso(),
                    "updatedAt": now_iso(),
                }
            )
    transcript["segments"] = segments
    transcript["updatedAt"] = now_iso()
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("transcript_segmentation_completed source_id=%s segments=%d", source_id_value, len(segments))
    message = f"Segments generated\n\nSource ID:\n{source_id_value}\n\nSegments:\n{len(segments)}\n\nReminder:\nJika tidak ada timestamp asli, segment hanya berbasis paragraf/logika, bukan waktu video akurat."
    return {"sourceId": source_id_value, "segments": segments, "telegramMessages": split_telegram_message(message)}


def update_segment(item_segment_id: str, body: dict[str, Any]) -> dict[str, Any]:
    source, transcript, segment = SOURCE_STORE.find_segment(item_segment_id)
    if "riskLevel" in body or "risk" in body:
        segment["riskLevel"] = validate_risk_level(str(body.get("riskLevel") or body.get("risk")))
    if "contextNotes" in body or "notes" in body:
        segment["contextNotes"] = str(body.get("contextNotes") or body.get("notes") or "").strip()
    segment["updatedAt"] = now_iso()
    transcript["updatedAt"] = now_iso()
    source["updatedAt"] = now_iso()
    SOURCE_STORE.save(source)
    LOGGER.info("segment_updated segment_id=%s", item_segment_id)
    return {**segment, "telegramMessages": format_segment_detail_for_telegram(source, segment)}


def transcript_context(source: dict[str, Any], segment: Optional[dict[str, Any]] = None) -> str:
    if segment:
        return str(segment.get("text") or "")
    transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
    return str(transcript.get("transcriptText") or "")
