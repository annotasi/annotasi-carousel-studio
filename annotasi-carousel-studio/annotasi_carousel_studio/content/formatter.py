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
from ..content.workflow import *

def format_full_for_telegram(record: dict[str, Any], include_voiceover: bool = False) -> list[str]:
    content = record["content"]
    lines = [
        "Annotasi Hikmah Carousel",
        "",
        "Title:",
        content["title"],
        "",
    ]
    for slide in content["slides"]:
        lines.extend(
            [
                f"Slide {slide['slideNumber']}:",
                slide["text"],
                "",
            ]
        )
    lines.extend(
        [
            "Caption:",
            content["caption"],
            "",
            "Hashtags:",
            " ".join(content["hashtags"]),
            "",
        ]
    )
    if include_voiceover:
        lines.extend(["Voiceover:", content["voiceoverScript"], ""])
    else:
        lines.extend(["Voiceover:", f"Use /voiceover {record['id']}", ""])
    lines.extend(
        [
            "Content ID:",
            record["id"],
            "",
            "Reminder:",
            "Review kembali sebelum upload agar tidak salah konteks.",
        ]
    )
    return split_telegram_message("\n".join(lines).strip())


def format_caption_for_telegram(record: dict[str, Any]) -> list[str]:
    content = record["content"]
    text = "\n".join(
        [
            f"Caption for {record['id']}",
            "",
            content["caption"],
            "",
            " ".join(content["hashtags"]),
        ]
    )
    return split_telegram_message(text)


def format_voiceover_for_telegram(record: dict[str, Any]) -> list[str]:
    content = record["content"]
    text = "\n".join([f"Voiceover for {record['id']}", "", content["voiceoverScript"]])
    return split_telegram_message(text)


def format_review_for_telegram(record: dict[str, Any]) -> list[str]:
    summary = workflow_summary(record)
    checklist = review_checklist(record)
    slides = record.get("content", {}).get("slides") if isinstance(record.get("content"), dict) else []
    lines = [
        "Review Content",
        "",
        "Content ID:",
        str(summary["id"]),
        "",
        "Title:",
        str(summary["title"]),
        "",
        "Status:",
        str(summary["status"]),
        "",
        "Slides:",
        f"{len(slides) if isinstance(slides, list) else 0} slides",
        "",
    ]
    link = record.get("sourceLink")
    if isinstance(link, dict) and link.get("sourceId"):
        try:
            linked_source = SOURCE_STORE.get(str(link["sourceId"]))
            candidate_link = record.get("candidateLink")
            linked_candidate = None
            if isinstance(candidate_link, dict) and candidate_link.get("candidateId"):
                try:
                    _source, linked_candidate = find_candidate(str(candidate_link["candidateId"]))
                except AppError:
                    linked_candidate = None
            lines.extend(
                [
                    "Source:",
                    f"{linked_source.get('sourceId')} - {linked_source.get('title')}",
                    "",
                    "Speaker:",
                    str(linked_source.get("speakerName") or "-"),
                    "",
                    "Permission:",
                    str(linked_source.get("permissionStatus") or "-"),
                    "",
                    "Credit:",
                    str(linked_source.get("creditText") or "-"),
                    "",
                    "Segment:",
                    str(link.get("segmentId") or "none"),
                    "",
                    "Risk:",
                    str(link.get("riskLevel") or "medium"),
                    "",
                ]
            )
            if linked_candidate:
                lines.extend(
                    [
                        "Candidate:",
                        str(linked_candidate.get("candidateId")),
                        "",
                        "Candidate type:",
                        str(linked_candidate.get("candidateType")),
                        "",
                        "Candidate risk:",
                        str(linked_candidate.get("riskLevel")),
                        "",
                        "Needs context:",
                        "yes" if linked_candidate.get("needsContext") else "no",
                        "",
                        "Context warning:",
                        str(linked_candidate.get("contextWarning") or "-"),
                        "",
                        "Candidate checklist:",
                        "[ ] Candidate context reviewed",
                        "[ ] Candidate risk level checked",
                        "[ ] Source credit included",
                        "[ ] Segment meaning not changed",
                        "[ ] Hook is not clickbait",
                        "[ ] Generated content matches candidate angle",
                        "",
                    ]
                )
            lines.extend(
                [
                    "Source checklist:",
                    "[ ] Source is linked",
                    "[ ] Credit text is included",
                    "[ ] Permission status reviewed",
                    "[ ] Segment context reviewed",
                    "[ ] No meaning is cut out of context",
                    "",
                ]
            )
        except AppError:
            lines.extend(["Source:", f"{link.get('sourceId')} (not found)", ""])
    else:
        lines.extend(
            [
                "Source:",
                "Content has no linked source. If inspired by kajian/video, add source before posting.",
                "",
            ]
        )
    lines.append("Checklist:")
    for item in checklist:
        marker = "[x]" if item["checked"] else "[ ]"
        lines.append(f"{marker} {item['label']}")
    lines.extend(
        [
            "",
            "Available actions:",
            f"/approve {summary['id']}",
            f"/reject {summary['id']} <reason>",
            f"/edit_slide {summary['id']} 3 <new text>",
            f"/edit_caption {summary['id']} <new caption>",
            f"/status {summary['id']}",
            "",
            "Reminder:",
            "Review kembali sebelum upload agar tidak salah konteks.",
        ]
    )
    return split_telegram_message("\n".join(lines).strip())


def format_status_for_telegram(record: dict[str, Any]) -> list[str]:
    summary = workflow_summary(record)
    schedule = summary["schedule"]
    uploaded = summary["uploaded"]
    package = summary["package"]
    schedule_text = "not scheduled"
    if schedule["date"]:
        schedule_text = f"{schedule['date']} {schedule['time'] or ''} {schedule['platform']}".strip()
    uploaded_text = "no"
    if uploaded["at"]:
        uploaded_text = f"yes ({uploaded['platform']}) {uploaded['url']}".strip()
    text = "\n".join(
        [
            "Content Status",
            "",
            "Content ID:",
            str(summary["id"]),
            "",
            "Status:",
            str(summary["status"]),
            "",
            "PNG:",
            str(summary["png"]),
            "",
            "Video:",
            str(summary["video"]),
            "",
            "Voiceover:",
            str(summary["voiceover"]),
            "",
            "Package:",
            str(package.get("status") or "not_started"),
            "",
            "Schedule:",
            schedule_text,
            "",
            "Uploaded:",
            uploaded_text,
        ]
    )
    return split_telegram_message(text)


def format_calendar_for_telegram(items: list[dict[str, Any]], title: str, empty_message: str) -> list[str]:
    if not items:
        return [empty_message]
    lines = [title, ""]
    for index, record in enumerate(items, start=1):
        summary = workflow_summary(record)
        schedule = summary["schedule"]
        lines.extend(
            [
                f"{index}. {summary['id']}",
                f"Title: {summary['title']}",
                f"Date: {schedule['date']}",
                f"Platform: {schedule['platform']}",
                f"Status: {summary['status']}",
                "",
            ]
        )
    return split_telegram_message("\n".join(lines).strip())


def format_content_list_for_telegram(records: list[dict[str, Any]], status: str = "") -> list[str]:
    lines = ["Content List", "", "Status:", status or "all", ""]
    if not records:
        lines.append("No content found.")
        return split_telegram_message("\n".join(lines).strip())
    for index, record in enumerate(records, start=1):
        summary = workflow_summary(record)
        lines.append(f"{index}. {summary['id']} - {summary['title']} ({summary['status']})")
    return split_telegram_message("\n".join(lines).strip())
