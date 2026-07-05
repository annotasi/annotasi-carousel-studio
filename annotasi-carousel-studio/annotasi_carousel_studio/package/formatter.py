from __future__ import annotations

from typing import Any

from ..common import *
from ..config import *
from ..errors import *
from ..storage.content_store import STORE, JsonContentStore
from ..storage.source_store import SOURCE_STORE, JsonSourceStore
from ..utils.ids import *
from ..utils.time import *
from ..utils.text import *
from ..utils.media import *

def content_text_fields(record: dict[str, Any]) -> tuple[str, str, list[str], str, str]:
    content = record.get("content")
    if not isinstance(content, dict):
        content = {}

    title = str(content.get("title") or record.get("title") or "").strip()
    caption = str(content.get("caption") or "").strip()

    raw_hashtags = content.get("hashtags")
    if isinstance(raw_hashtags, list):
        hashtags = [str(item).strip() for item in raw_hashtags if str(item).strip()]
    else:
        hashtags = []

    voiceover = str(content.get("voiceoverScript") or "").strip()
    source_credit = str(content.get("sourceCreditSuggestion") or "").strip()

    return title, caption, hashtags, voiceover, source_credit

def posting_checklist_text(record: dict[str, Any]) -> str:
    title, _caption, _hashtags, _voiceover, _source_credit = content_text_fields(record)
    return "\n".join(
        [
            "# Posting Checklist - Annotasi Hikmah",
            "",
            "Content ID:",
            str(record.get("id")),
            "",
            "Title:",
            title or "-",
            "",
            "Before upload:",
            "",
            "* [ ] Content has been reviewed.",
            "* [ ] Content status is approved.",
            "* [ ] PNG carousel is readable.",
            "* [ ] MP4 video is playable.",
            "* [ ] Voiceover audio is clear if used.",
            "* [ ] Caption is ready.",
            "* [ ] Hashtags are relevant.",
            "* [ ] Source credit is included if content is based on kajian/transcript.",
            "* [ ] Source permission status has been checked.",
            "* [ ] Candidate/segment context has been reviewed.",
            "* [ ] No invented Quran verse.",
            "* [ ] No invented hadith.",
            "* [ ] No unsupported attribution to UAS, UAH, or any ustadz.",
            "* [ ] Title is not misleading or excessive clickbait.",
            "* [ ] Meaning is not cut out of context.",
            "* [ ] Final content is suitable for dakwah/reflection.",
            "* [ ] Platform selected for posting.",
            "* [ ] Uploaded URL will be saved using `/uploaded`.",
            "",
            "Reminder:",
            "",
            "Review kembali sebelum upload agar tidak salah konteks.",
            "",
            "Additional warning:",
            "",
            "Boleh disebarkan untuk dakwah belum tentu otomatis aman untuk monetisasi. Tetap beri sumber dan nilai tambah.",
            "",
        ]
    )


def dakwah_safety_checklist_text() -> str:
    return "\n".join(
        [
            "# Dakwah Safety Checklist",
            "",
            "* [ ] Source clarity checked.",
            "* [ ] Permission clarity checked.",
            "* [ ] Credit clarity checked.",
            "* [ ] Context reviewed.",
            "* [ ] Quran/hadith safety checked.",
            "* [ ] Attribution safety checked.",
            "* [ ] Monetization caution reviewed.",
            "* [ ] No voice cloning used.",
            "* [ ] No misleading edits.",
            "* [ ] Manual review completed.",
            "",
        ]
    )


def source_context_text(record: dict[str, Any], source: Optional[dict[str, Any]], candidate: Optional[dict[str, Any]]) -> str:
    if not source:
        return "No linked source found. If this content was inspired by a kajian, video, transcript, book, or article, add the source before posting.\n"
    link = record.get("sourceLink") if isinstance(record.get("sourceLink"), dict) else {}
    candidate_link = record.get("candidateLink") if isinstance(record.get("candidateLink"), dict) else {}
    candidate_id_value = (candidate or {}).get("candidateId") or candidate_link.get("candidateId") or "-"
    lines = [
        "# Source Context",
        "",
        f"Source ID: {source.get('sourceId')}",
        f"Source title: {source.get('title') or '-'}",
        f"Speaker name: {source.get('speakerName') or '-'}",
        f"Source URL: {source.get('sourceUrl') or '-'}",
        f"Source platform: {source.get('platform') or '-'}",
        f"Permission status: {source.get('permissionStatus') or '-'}",
        f"Permission notes: {source.get('permissionNotes') or '-'}",
        f"Credit text: {source.get('creditText') or '-'}",
        f"Segment ID: {link.get('segmentId') or '-'}",
        f"Candidate ID: {candidate_id_value}",
        f"Risk level: {(candidate or {}).get('riskLevel') or link.get('riskLevel') or '-'}",
        f"Context warning: {(candidate or {}).get('contextWarning') or '-'}",
        "",
    ]
    return "\n".join(lines)


def package_readme_text(record: dict[str, Any], package: dict[str, Any]) -> str:
    title, _caption, _hashtags, _voiceover, _source_credit = content_text_fields(record)
    return "\n".join(
        [
            "# Annotasi Content Package",
            "",
            "Content ID:",
            str(record.get("id")),
            "",
            "Package ID:",
            str(package.get("packageId")),
            "",
            "Title:",
            title or "-",
            "",
            "How to post manually:",
            "",
            "1. Open `01-carousel` for Instagram carousel slides.",
            "2. Open `02-video` for Shorts/Reels/TikTok video.",
            "3. Copy caption from `03-copy`.",
            "4. Include source credit if applicable.",
            "5. Review `04-review/posting-checklist.md`.",
            "6. Upload manually to selected platform.",
            "7. After upload, run:",
            f"   `/uploaded {record.get('id')} instagram <url>`",
            "",
            "Reminder:",
            "",
            "Review kembali sebelum upload agar tidak salah konteks.",
            "",
        ]
    )


def format_ready_to_post_for_telegram(item_id: str, ready: bool, missing: list[str], blocking: list[str], warnings: list[str]) -> list[str]:
    lines = ["Ready To Post Check", "", "Content ID:", item_id, "", "Ready:", "yes" if ready else "no", ""]
    if missing:
        lines.extend(["Missing:", *[f"- {item}" for item in missing], ""])
    if blocking:
        lines.extend(["Blocking:", *[f"- {item}" for item in blocking], ""])
    if warnings:
        lines.extend(["Warnings:", *[f"- {item}" for item in warnings], ""])
    return split_telegram_message("\n".join(lines).strip())


def format_posting_checklist_for_telegram(record: dict[str, Any]) -> list[str]:
    text = posting_checklist_text(record).replace("# Posting Checklist - Annotasi Hikmah", "Posting Checklist")
    return split_telegram_message(text)


def format_package_for_telegram(package: dict[str, Any]) -> list[str]:
    included = package.get("included") if isinstance(package.get("included"), dict) else {}
    warnings = package.get("warnings") if isinstance(package.get("warnings"), list) else []
    lines = [
        "Content Package Created",
        "",
        "Content ID:",
        str(package.get("contentId")),
        "",
        "Package ID:",
        str(package.get("packageId")),
        "",
        "Title:",
        str(package.get("title") or "-"),
        "",
        "Included:",
        f"- Carousel PNG: {included.get('pngCount', 0)} files",
        f"- Video MP4: {'yes' if included.get('videoCount', 0) else 'no'}",
        f"- Voiceover MP4: {'yes' if package.get('hasVoiceoverVideo') else 'no'}",
        f"- Caption files: {'yes' if included.get('copyFiles', 0) else 'no'}",
        f"- Source credit: {'yes' if package.get('hasSourceCredit') else 'no'}",
        f"- Posting checklist: {'yes' if package.get('hasPostingChecklist') else 'no'}",
        f"- ZIP: {'yes' if package.get('zipPath') else 'no'}",
        "",
        "Package:",
        str(package.get("packageDir") or "-"),
        "",
        "ZIP:",
        str(package.get("zipPath") or "-"),
        "",
    ]
    if warnings:
        lines.extend(["Warnings:", *[f"- {warning}" for warning in warnings], ""])
    lines.extend(["Next:", "Upload manual, then run:", f"/uploaded {package.get('contentId')} instagram <url>"])
    return split_telegram_message("\n".join(lines).strip())


def format_package_status_for_telegram(item_id: str, package: Optional[dict[str, Any]]) -> list[str]:
    if not package:
        return [f"Package Status\n\nContent ID:\n{item_id}\n\nLatest Package:\nnone\n\nStatus:\nnot_started"]
    warnings = package.get("warnings") if isinstance(package.get("warnings"), list) else []
    lines = [
        "Package Status",
        "",
        "Content ID:",
        item_id,
        "",
        "Latest Package:",
        str(package.get("packageId")),
        "",
        "Status:",
        str(package.get("status")),
        "",
        "ZIP:",
        "available" if package.get("zipPath") else "not available",
        "",
        "Stale:",
        "yes" if package.get("status") == "stale" else "no",
    ]
    if warnings:
        lines.extend(["", "Warnings:", *[f"- {warning}" for warning in warnings]])
    return split_telegram_message("\n".join(lines).strip())


def format_package_list_for_telegram(item_id: str, packages: list[dict[str, Any]]) -> list[str]:
    lines = ["Package List", "", "Content ID:", item_id, ""]
    if not packages:
        lines.append("No packages found.")
    for index, package in enumerate(packages, start=1):
        lines.append(f"{index}. {package.get('packageId')} - {package.get('status')} - {package.get('createdAt')}")
    return split_telegram_message("\n".join(lines).strip())
