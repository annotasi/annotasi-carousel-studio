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
from ..render.png_renderer import *
from ..render.video_renderer import *
from ..render.audio_mixer import *
from ..source.service import *
from ..candidate.service import *
from ..package.formatter import *

def write_text_file(path: Path, text: str) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "package_write_failed", f"Could not write {path.name}.") from exc


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    write_text_file(path, json.dumps(payload, ensure_ascii=False, indent=2))


def safe_copy_file(source_path: Path, target_path: Path) -> None:
    source = ensure_path_inside(source_path, [EXPORT_DIR, CONTENT_AUDIO_DIR, PACKAGE_DIR])
    target = ensure_path_inside(target_path, [PACKAGE_DIR])
    if not source.exists() or not source.is_file() or source.stat().st_size <= 0:
        raise AppError(HTTPStatus.NOT_FOUND, "package_asset_missing", f"Asset is missing: {source.name}")
    if source.name.startswith(".env"):
        raise AppError(HTTPStatus.BAD_REQUEST, "package_asset_blocked", "Environment files cannot be packaged.")
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "package_copy_failed", f"Could not copy {source.name}.") from exc


def content_text_fields(record: dict[str, Any]) -> tuple[str, str, list[str], str, str]:
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    title = str(content.get("title") or record.get("topic") or "").strip()
    caption = str(content.get("caption") or "").strip()
    hashtags = content.get("hashtags")
    if not isinstance(hashtags, list):
        hashtags = []
    hashtags = [str(item).strip() for item in hashtags if str(item).strip()]
    voiceover = str(content.get("voiceoverScript") or "").strip()
    source_credit = str(content.get("sourceCreditSuggestion") or "").strip()
    return title, caption, hashtags, voiceover, source_credit


def platform_caption_files(title: str, caption: str, hashtags: list[str]) -> dict[str, str]:
    tags = hashtag_text(hashtags)
    return {
        "caption-instagram.txt": "\n\n".join(part for part in [caption, tags] if part).strip() + "\n",
        "caption-tiktok.txt": "\n\n".join(part for part in [short_caption(caption), tags] if part).strip() + "\n",
        "caption-youtube-shorts.txt": "\n\n".join(part for part in [title, caption, tags] if part).strip() + "\n",
    }


def linked_source_and_candidate(record: dict[str, Any]) -> tuple[Optional[dict[str, Any]], Optional[dict[str, Any]]]:
    source = None
    candidate = None
    source_link = record.get("sourceLink")
    if isinstance(source_link, dict) and source_link.get("sourceId"):
        try:
            source = SOURCE_STORE.get(str(source_link["sourceId"]))
        except AppError:
            source = None
    candidate_link = record.get("candidateLink")
    if isinstance(candidate_link, dict) and candidate_link.get("candidateId"):
        try:
            _source, candidate = find_candidate(str(candidate_link["candidateId"]))
        except AppError:
            candidate = None
    return source, candidate


def content_is_approved(record: dict[str, Any]) -> bool:
    workflow = ensure_workflow(record)
    if workflow.get("reviewStatus") == "approved":
        return True
    return str(workflow.get("status") or "") in SCHEDULABLE_STATUSES


def completed_png_for_package(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    render = record.get("latestRender")
    return render if isinstance(render, dict) and render.get("status") == "completed" and render_files_exist(render) else None


def completed_video_for_package(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    render = record.get("latestVideoRender")
    return render if isinstance(render, dict) and render.get("status") == "completed" and video_file_exists(render) else None


def completed_audio_for_package(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    render = record.get("latestAudioRender")
    return render if isinstance(render, dict) and render.get("status") == "completed" and audio_file_exists(render) else None


def source_credit_for_package(record: dict[str, Any], source: Optional[dict[str, Any]]) -> str:
    content = record.get("content") if isinstance(record.get("content"), dict) else {}
    candidates = [
        content.get("sourceCreditSuggestion"),
        record.get("sourceLink", {}).get("sourceCreditUsed") if isinstance(record.get("sourceLink"), dict) else "",
        source.get("creditText") if isinstance(source, dict) else "",
    ]
    for item in candidates:
        text = str(item or "").strip()
        if text:
            return text
    return ""


def package_required_issues(record: dict[str, Any]) -> list[str]:
    title, caption, hashtags, _voiceover, _source_credit = content_text_fields(record)
    workflow = ensure_workflow(record)
    issues = []
    if workflow.get("status") == "rejected":
        issues.append("Content is rejected.")
    if not title:
        issues.append("Content title is missing.")
    if not caption:
        issues.append("Caption is missing.")
    if not hashtags:
        issues.append("Hashtags are missing.")
    if CONTENT_PACKAGE_REQUIRE_APPROVAL and not content_is_approved(record):
        issues.append("Content must be approved before packaging. Run /review <content_id> and /approve <content_id> first.")
    return issues


def package_warnings(record: dict[str, Any], source: Optional[dict[str, Any]], candidate: Optional[dict[str, Any]]) -> list[str]:
    _title, _caption, _hashtags, voiceover, _source_credit = content_text_fields(record)
    workflow = ensure_workflow(record)
    warnings = []
    stale = workflow.get("renderStale") if isinstance(workflow.get("renderStale"), dict) else {}
    if isinstance(stale, dict):
        if stale.get("png"):
            warnings.append("PNG render is stale. Rerun /render before posting.")
        if stale.get("video"):
            warnings.append("MP4 video render is stale. Rerun /video before posting.")
        if stale.get("audio"):
            warnings.append("Voiceover video is stale. Rerun /mixvoice before posting.")
    if not completed_png_for_package(record):
        warnings.append("PNG carousel render not found.")
    if not completed_video_for_package(record):
        warnings.append("MP4 video render not found.")
    if voiceover and not completed_audio_for_package(record):
        warnings.append("Voiceover script exists, but voiceover MP4 was not found.")
    if source and not source_credit_for_package(record, source):
        warnings.append("Linked source exists, but source credit is missing.")
    if source and source.get("permissionStatus") in {"unknown", "needs_permission", "allowed_for_dakwah"}:
        warnings.append("Source permission requires manual review before monetized posting.")
    if candidate and candidate.get("needsContext"):
        warnings.append(str(candidate.get("contextWarning") or "Candidate context must be reviewed manually."))
    if not CONTENT_PACKAGE_REQUIRE_APPROVAL and not content_is_approved(record):
        warnings.append("Content is not approved yet.")
    warnings.append("Review kembali sebelum upload agar tidak salah konteks.")
    return list(dict.fromkeys([item for item in warnings if item]))


def ready_to_post_check(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    source, candidate = linked_source_and_candidate(record)
    required = package_required_issues(record)
    warnings = package_warnings(record, source, candidate)
    stale = ensure_workflow(record).get("renderStale", {})
    stale_blocked = bool(isinstance(stale, dict) and any(stale.values()) and not CONTENT_PACKAGE_ALLOW_STALE_MEDIA)
    if stale_blocked:
        required.append("Media render is stale. Please rerun /render, /video, or /mixvoice before packaging.")
    missing = [item for item in warnings if "not found" in item or "missing" in item.lower()]
    ready = not required and not missing
    return {
        "contentId": item_id,
        "ready": ready,
        "missing": missing,
        "blockingIssues": required,
        "warnings": warnings,
        "summary": workflow_summary(record),
        "telegramMessages": format_ready_to_post_for_telegram(item_id, ready, missing, required, warnings),
    }


def manifest_for_package(record: dict[str, Any], package: dict[str, Any], source: Optional[dict[str, Any]], candidate: Optional[dict[str, Any]], assets: dict[str, list[str]]) -> dict[str, Any]:
    workflow = ensure_workflow(record)
    title, _caption, _hashtags, _voiceover, _source_credit = content_text_fields(record)
    return {
        "packageId": package["packageId"],
        "contentId": record["id"],
        "title": title,
        "status": package["status"],
        "createdAt": package["createdAt"],
        "timezone": CONTENT_PACKAGE_TIMEZONE,
        "contentStatus": workflow.get("status"),
        "schedule": {
            "scheduledDate": workflow.get("scheduledDate") or None,
            "scheduledTime": workflow.get("scheduledTime") or None,
            "platform": workflow.get("scheduledPlatform") or None,
        },
        "source": {
            "sourceId": source.get("sourceId") if source else None,
            "title": source.get("title") if source else None,
            "speakerName": source.get("speakerName") if source else None,
            "sourceUrl": source.get("sourceUrl") if source else None,
            "permissionStatus": source.get("permissionStatus") if source else None,
            "creditText": source.get("creditText") if source else None,
        },
        "candidate": {
            "candidateId": candidate.get("candidateId") if candidate else None,
            "candidateType": candidate.get("candidateType") if candidate else None,
            "riskLevel": candidate.get("riskLevel") if candidate else None,
            "needsContext": bool(candidate.get("needsContext")) if candidate else False,
        },
        "assets": assets,
        "warnings": package.get("warnings", []),
        "postingReminder": "Review kembali sebelum upload agar tidak salah konteks.",
    }


def create_package_zip(package_dir: Path, zip_path: Path) -> None:
    try:
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(package_dir.rglob("*")):
                if path.is_file():
                    archive.write(path, path.relative_to(package_dir))
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "zip_creation_failed", "Could not create package ZIP.") from exc


def generate_content_package(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    LOGGER.info("package_request_received content_id=%s", item_id)
    record = STORE.get(item_id)
    ensure_workflow(record)
    force_regenerate = parse_bool(body.get("forceRegenerate"), False)
    existing = latest_package(record)
    if existing and existing.get("status") == "completed" and not force_regenerate:
        LOGGER.info("duplicate_package_returned content_id=%s package_id=%s", item_id, existing.get("packageId"))
        return {**existing, "telegramMessages": format_package_for_telegram(existing)}

    source, candidate = linked_source_and_candidate(record)
    required = package_required_issues(record)
    stale = ensure_workflow(record).get("renderStale", {})
    if isinstance(stale, dict) and any(stale.values()) and not CONTENT_PACKAGE_ALLOW_STALE_MEDIA:
        required.append("Media render is stale. Please rerun /render, /video, or /mixvoice before packaging.")
    if required:
        raise AppError(HTTPStatus.CONFLICT, "package_not_ready", required[0])

    item_package_id = package_id()
    title, caption, hashtags, voiceover, _source_credit = content_text_fields(record)
    package_root = ensure_path_inside((PACKAGE_DIR / item_id).resolve(), [PACKAGE_DIR])
    package_dir = ensure_path_inside(package_root / item_package_id, [PACKAGE_DIR])
    zip_path = package_root / f"{item_id}-{slugify(title, item_id)}-{item_package_id}.zip"
    warnings = package_warnings(record, source, candidate)
    package = {
        "packageId": item_package_id,
        "package_id": item_package_id,
        "contentId": item_id,
        "content_id": item_id,
        "title": title,
        "status": "packaging",
        "packageDir": str(package_dir),
        "package_dir": str(package_dir),
        "zipPath": "",
        "zip_path": "",
        "includedPngCount": 0,
        "included_png_count": 0,
        "includedVideoCount": 0,
        "included_video_count": 0,
        "includedTextCount": 0,
        "included_text_count": 0,
        "hasVoiceoverVideo": False,
        "has_voiceover_video": False,
        "hasSourceCredit": False,
        "has_source_credit": False,
        "hasCandidateMetadata": bool(candidate),
        "has_candidate_metadata": bool(candidate),
        "hasPostingChecklist": False,
        "has_posting_checklist": False,
        "warnings": warnings,
        "warningsJson": json.dumps(warnings, ensure_ascii=False),
        "warnings_json": json.dumps(warnings, ensure_ascii=False),
        "included": {"pngCount": 0, "videoCount": 0, "copyFiles": 0, "reviewFiles": 0, "metadataFiles": 0},
        "errorMessage": "",
        "error_message": "",
        "createdAt": now_iso(),
        "created_at": now_iso(),
        "updatedAt": now_iso(),
        "updated_at": now_iso(),
    }
    if not isinstance(record.get("packages"), list):
        record["packages"] = []
    record["packages"].append(package)
    record["latestPackage"] = package
    STORE.save(record)

    try:
        for dirname in ["01-carousel", "02-video", "03-copy", "04-review", "05-metadata"]:
            (package_dir / dirname).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        package["status"] = "failed"
        package["errorMessage"] = "Package directory is not writable."
        package["error_message"] = package["errorMessage"]
        package["updatedAt"] = now_iso()
        package["updated_at"] = package["updatedAt"]
        STORE.save(record)
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "package_directory_not_writable", "Package directory is not writable.") from exc

    assets = {"carouselPng": [], "videos": [], "copyFiles": [], "reviewFiles": [], "metadataFiles": []}
    try:
        png_render = completed_png_for_package(record)
        if png_render:
            png_files = validate_png_files(png_render, len(record.get("content", {}).get("slides", [])))
            for file_info in png_files:
                slide_number = int(file_info.get("slideNumber") or len(assets["carouselPng"]) + 1)
                relative = f"01-carousel/slide-{slide_number:02d}.png"
                safe_copy_file(Path(str(file_info["path"])), package_dir / relative)
                assets["carouselPng"].append(relative)

        video_render = completed_video_for_package(record)
        if video_render:
            video_path = Path(str(video_render.get("file", {}).get("path") if isinstance(video_render.get("file"), dict) else ""))
            safe_copy_file(video_path, package_dir / "02-video/final.mp4")
            assets["videos"].append("02-video/final.mp4")

        audio_render = completed_audio_for_package(record)
        if audio_render:
            audio_path = Path(str(audio_render.get("outputVideo", {}).get("path") if isinstance(audio_render.get("outputVideo"), dict) else ""))
            safe_copy_file(audio_path, package_dir / "02-video/final-voiceover.mp4")
            assets["videos"].append("02-video/final-voiceover.mp4")

        copy_files = {
            "title.txt": title + "\n",
            "hashtags.txt": hashtag_text(hashtags, multiline=True) + "\n",
            "voiceover-script.txt": (voiceover or "-") + "\n",
            "source-credit.txt": (source_credit_for_package(record, source) or "Source credit missing. Add source credit before posting if this content is source-based.") + "\n",
        }
        if parse_bool(body.get("includePlatformCaptions"), CONTENT_PACKAGE_INCLUDE_PLATFORM_CAPTIONS):
            copy_files.update(platform_caption_files(title, caption, hashtags))
        else:
            copy_files["caption-instagram.txt"] = caption + "\n"
        for filename, text in copy_files.items():
            write_text_file(package_dir / "03-copy" / filename, text)
            assets["copyFiles"].append(f"03-copy/{filename}")

        review_files = {
            "posting-checklist.md": posting_checklist_text(record),
            "dakwah-safety-checklist.md": dakwah_safety_checklist_text(),
            "source-context.md": source_context_text(record, source, candidate),
        }
        for filename, text in review_files.items():
            write_text_file(package_dir / "04-review" / filename, text)
            assets["reviewFiles"].append(f"04-review/{filename}")

        if parse_bool(body.get("includeMetadata"), CONTENT_PACKAGE_INCLUDE_METADATA):
            metadata = {
                "content.json": record,
                "render-metadata.json": {
                    "latestRender": record.get("latestRender", {}),
                    "latestVideoRender": record.get("latestVideoRender", {}),
                    "latestAudioRender": record.get("latestAudioRender", {}),
                },
            }
            if source:
                metadata["source.json"] = source
            if candidate:
                metadata["candidate.json"] = candidate
            for filename, payload in metadata.items():
                write_json_file(package_dir / "05-metadata" / filename, payload)
                assets["metadataFiles"].append(f"05-metadata/{filename}")

        package["includedPngCount"] = len(assets["carouselPng"])
        package["included_png_count"] = package["includedPngCount"]
        package["includedVideoCount"] = len(assets["videos"])
        package["included_video_count"] = package["includedVideoCount"]
        package["includedTextCount"] = len(assets["copyFiles"]) + len(assets["reviewFiles"])
        package["included_text_count"] = package["includedTextCount"]
        package["hasVoiceoverVideo"] = "02-video/final-voiceover.mp4" in assets["videos"]
        package["has_voiceover_video"] = package["hasVoiceoverVideo"]
        package["hasSourceCredit"] = bool(source_credit_for_package(record, source))
        package["has_source_credit"] = package["hasSourceCredit"]
        package["hasPostingChecklist"] = "04-review/posting-checklist.md" in assets["reviewFiles"]
        package["has_posting_checklist"] = package["hasPostingChecklist"]
        package["included"] = {
            "pngCount": len(assets["carouselPng"]),
            "videoCount": len(assets["videos"]),
            "copyFiles": len(assets["copyFiles"]),
            "reviewFiles": len(assets["reviewFiles"]),
            "metadataFiles": len(assets["metadataFiles"]),
        }
        package["status"] = "completed"
        manifest = manifest_for_package(record, package, source, candidate, assets)
        write_json_file(package_dir / "05-metadata/manifest.json", manifest)
        assets["metadataFiles"].append("05-metadata/manifest.json")
        write_text_file(package_dir / "README.md", package_readme_text(record, package))
    except AppError as exc:
        package["status"] = "failed"
        package["errorMessage"] = exc.message
        package["error_message"] = exc.message
        package["updatedAt"] = now_iso()
        package["updated_at"] = package["updatedAt"]
        STORE.save(record)
        raise

    create_zip = parse_bool(body.get("createZip"), CONTENT_PACKAGE_CREATE_ZIP)
    if create_zip:
        try:
            create_package_zip(package_dir, zip_path)
            size_mb = zip_path.stat().st_size / (1024 * 1024)
            package["zipPath"] = str(zip_path)
            package["zip_path"] = str(zip_path)
            if size_mb > CONTENT_PACKAGE_MAX_ZIP_SIZE_MB:
                package["warnings"].append("ZIP is larger than configured Telegram-safe size; return path instead of sending file.")
        except AppError as exc:
            package["warnings"].append(f"ZIP creation failed: {exc.message}")
            package["warningsJson"] = json.dumps(package["warnings"], ensure_ascii=False)
            package["warnings_json"] = package["warningsJson"]

    package["updatedAt"] = now_iso()
    package["updated_at"] = package["updatedAt"]
    package["warningsJson"] = json.dumps(package["warnings"], ensure_ascii=False)
    package["warnings_json"] = package["warningsJson"]
    record["latestPackage"] = package
    record["updatedAt"] = now_iso()
    STORE.save(record)
    LOGGER.info("package_completed content_id=%s package_id=%s", item_id, item_package_id)
    return {**package, "telegramMessages": format_package_for_telegram(package)}


def latest_package_status(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    package = latest_package(record)
    return {"contentId": item_id, "package": package, "telegramMessages": format_package_status_for_telegram(item_id, package)}


def list_packages_for_content(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    packages = record.get("packages") if isinstance(record.get("packages"), list) else []
    packages = [item for item in packages if isinstance(item, dict)]
    return {"contentId": item_id, "packages": packages, "telegramMessages": format_package_list_for_telegram(item_id, packages)}


def package_by_id(item_package_id: str) -> dict[str, Any]:
    record, package = STORE.find_package(item_package_id)
    lines = [
        "Package Path",
        "",
        "Package ID:",
        item_package_id,
        "",
        "Content ID:",
        str(record.get("id")),
        "",
        "Directory:",
        str(package.get("packageDir") or "-"),
        "",
        "ZIP:",
        str(package.get("zipPath") or "-"),
    ]
    return {"contentId": record.get("id"), "package": package, "telegramMessages": split_telegram_message("\n".join(lines).strip())}


def posting_checklist_for_content(item_id: str) -> dict[str, Any]:
    record = STORE.get(item_id)
    return {"contentId": item_id, "checklist": posting_checklist_text(record), "telegramMessages": format_posting_checklist_for_telegram(record)}
