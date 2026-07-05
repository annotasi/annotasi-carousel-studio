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

def format_render_for_telegram(render: dict[str, Any]) -> list[str]:
    files = render.get("files") if isinstance(render.get("files"), list) else []
    lines = [
        "Annotasi Carousel Rendered",
        "",
        "Content ID:",
        str(render.get("contentId", "")),
        "",
        "Render ID:",
        str(render.get("renderId", "")),
        "",
        "Format:",
        f"{render.get('format', 'instagram_carousel')} {render.get('width')}x{render.get('height')}",
        "",
        "Slides:",
        f"{len(files)} PNG files generated",
        "",
        "Output:",
    ]
    for item in files:
        if isinstance(item, dict):
            lines.append(f"- {item.get('filename')}: {item.get('path')}")
    lines.extend(
        [
            "",
            "Reminder:",
            "Review kembali sebelum upload agar tidak salah konteks.",
        ]
    )
    return split_telegram_message("\n".join(lines).strip())


def validate_renderable_content(record: dict[str, Any]) -> list[dict[str, Any]]:
    content = record.get("content")
    if not isinstance(content, dict):
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_content", "Content package is invalid.")
    slides = content.get("slides")
    if not isinstance(slides, list) or not slides:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "no_slides", "Content package has no slides.")
    if not 5 <= len(slides) <= 8:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "unsupported_slide_count", "Slide count must be between 5 and 8.")
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_slide", f"Slide {index} is invalid.")
        text = str(slide.get("text") or "").strip()
        if not text:
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_slide", f"Slide {index} has no text.")
        if len(text) > 700:
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "slide_text_too_long", f"Slide {index} text is too long to render.")
    return slides


def render_files_exist(render: dict[str, Any]) -> bool:
    files = render.get("files")
    if not isinstance(files, list) or not files:
        return False
    return all(isinstance(item, dict) and Path(str(item.get("path", ""))).exists() for item in files)


def latest_completed_render(
    record: dict[str, Any],
    *,
    output_format: str,
    template_name: str,
    width: int,
    height: int,
) -> Optional[dict[str, Any]]:
    stale = ensure_workflow(record).get("renderStale", {})
    if isinstance(stale, dict) and stale.get("png"):
        return None
    renders = record.get("renders")
    if not isinstance(renders, list):
        return None
    for item in reversed(renders):
        if not isinstance(item, dict):
            continue
        if (
            item.get("status") == "completed"
            and item.get("format") == output_format
            and item.get("templateName") == template_name
            and item.get("width") == width
            and item.get("height") == height
            and render_files_exist(item)
        ):
            return item
    return None


def normalize_render_result(render: dict[str, Any]) -> dict[str, Any]:
    return {**render, "telegramMessages": format_render_for_telegram(render)}


def latest_completed_png_render(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    stale = ensure_workflow(record).get("renderStale", {})
    if isinstance(stale, dict) and stale.get("png"):
        return None
    renders = record.get("renders")
    if not isinstance(renders, list):
        return None
    for item in reversed(renders):
        if (
            isinstance(item, dict)
            and item.get("status") == "completed"
            and item.get("format") == "instagram_carousel"
            and render_files_exist(item)
        ):
            return item
    return None


def validate_png_files(render: dict[str, Any], expected_slides: int) -> list[dict[str, Any]]:
    files = render.get("files")
    if not isinstance(files, list) or not files:
        raise AppError(HTTPStatus.NOT_FOUND, "png_render_not_found", "PNG render has no files. Run /render first.")
    ordered = sorted(
        [item for item in files if isinstance(item, dict)],
        key=lambda item: int(item.get("slideNumber") or 0),
    )
    if len(ordered) != expected_slides:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "png_file_count_mismatch", "PNG file count does not match slide count.")
    for index, item in enumerate(ordered, start=1):
        if int(item.get("slideNumber") or 0) != index:
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "png_file_count_mismatch", "PNG slide numbers are not sequential.")
        path = Path(str(item.get("path") or ""))
        if path.suffix.lower() != ".png":
            raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_png_file", f"Slide {index} file is not a PNG.")
        if not path.exists() or not path.is_file():
            raise AppError(HTTPStatus.NOT_FOUND, "png_files_missing", f"PNG file missing for slide {index}. Run /render again.")
        item["path"] = str(path)
    LOGGER.info("png_files_validated count=%d", len(ordered))
    return ordered


def call_png_renderer(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if not NODE_RENDERER.exists():
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "render_dependency_unavailable", "PNG renderer script is unavailable.")
    try:
        completed = subprocess.run(
            ["node", str(NODE_RENDERER)],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            timeout=RENDER_TIMEOUT_SECONDS,
            cwd=str(SERVICE_DIR),
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "render_dependency_unavailable", "Node.js is required for PNG rendering.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(HTTPStatus.GATEWAY_TIMEOUT, "render_timeout", "PNG rendering timed out.") from exc

    if completed.returncode != 0:
        message = "PNG generation failed."
        code = "png_generation_failed"
        try:
            error_body = json.loads(completed.stdout or "{}")
            if isinstance(error_body, dict):
                code = str(error_body.get("code") or code)
                message = str(error_body.get("message") or message)
        except json.JSONDecodeError:
            if completed.stderr.strip():
                message = completed.stderr.strip()[:300]
        status_by_code = {
            "render_dependency_unavailable": HTTPStatus.SERVICE_UNAVAILABLE,
            "template_not_found": HTTPStatus.BAD_REQUEST,
            "slide_text_too_long": HTTPStatus.UNPROCESSABLE_ENTITY,
            "no_slides": HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_slide": HTTPStatus.UNPROCESSABLE_ENTITY,
        }
        raise AppError(status_by_code.get(code, HTTPStatus.BAD_GATEWAY), code, message)

    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AppError(HTTPStatus.BAD_GATEWAY, "png_generation_failed", "PNG renderer returned invalid JSON.") from exc
    files = result.get("files") if isinstance(result, dict) else None
    if not isinstance(files, list) or not files:
        raise AppError(HTTPStatus.BAD_GATEWAY, "png_generation_failed", "PNG renderer did not return files.")
    return files


def render_content_png(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    output_format = str(body.get("format") or "instagram_carousel").strip()
    template_name = str(body.get("template") or DEFAULT_TEMPLATE).strip()
    force_regenerate = bool(body.get("forceRegenerate", False))
    width = parse_int(body.get("width"), CAROUSEL_WIDTH, "width")
    height = parse_int(body.get("height"), CAROUSEL_HEIGHT, "height")

    if output_format != "instagram_carousel":
        raise AppError(HTTPStatus.BAD_REQUEST, "unsupported_format", "Only instagram_carousel is supported.")
    if template_name != "annotasi_hikmah_dark":
        raise AppError(HTTPStatus.BAD_REQUEST, "template_not_found", "Template was not found.")
    if width <= 0 or height <= 0:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_dimensions", "Render dimensions must be positive.")

    LOGGER.info("render_request_received content_id=%s format=%s template=%s", item_id, output_format, template_name)
    record = STORE.get(item_id)
    slides = validate_renderable_content(record)
    LOGGER.info("content_loaded content_id=%s slides=%d", item_id, len(slides))

    existing = latest_completed_render(
        record,
        output_format=output_format,
        template_name=template_name,
        width=width,
        height=height,
    )
    if existing and not force_regenerate:
        LOGGER.info("duplicate_render_returned content_id=%s render_id=%s", item_id, existing.get("renderId"))
        return normalize_render_result(existing)

    item_render_id = render_id()
    output_dir = (EXPORT_DIR / item_id / item_render_id).resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "output_not_writable", "Output directory is not writable.") from exc
    LOGGER.info("output_directory_prepared content_id=%s render_id=%s", item_id, item_render_id)
    LOGGER.info("template_selected template=%s", template_name)

    content = record["content"]
    render = {
        "contentId": item_id,
        "renderId": item_render_id,
        "status": "rendering",
        "format": output_format,
        "templateName": template_name,
        "width": width,
        "height": height,
        "files": [],
        "errorMessage": "",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    if not isinstance(record.get("renders"), list):
        record["renders"] = []
    record["renders"].append(render)
    record["latestRender"] = render
    record["updatedAt"] = now_iso()
    STORE.save(record)

    renderer_payload = {
        "contentId": item_id,
        "renderId": item_render_id,
        "format": output_format,
        "templateName": template_name,
        "width": width,
        "height": height,
        "outputDir": str(output_dir),
        "brand": {
            "primary": "Annotasi Hikmah",
            "subtitle": "Pengingat singkat untuk Muslim yang sedang bekerja, berjuang, dan memperbaiki hidup.",
            "footer": "Review kembali sebelum upload agar tidak salah konteks.",
        },
        "content": {
            "title": content.get("title", ""),
            "callToAction": content.get("callToAction", ""),
            "sourceCreditSuggestion": content.get("sourceCreditSuggestion", ""),
            "slides": slides,
        },
    }

    try:
        files = call_png_renderer(renderer_payload)
    except AppError as exc:
        render["status"] = "failed"
        render["errorMessage"] = exc.message
        render["updatedAt"] = now_iso()
        record["latestRender"] = render
        record["updatedAt"] = now_iso()
        STORE.save(record)
        raise

    render["status"] = "completed"
    render["files"] = files
    render["updatedAt"] = now_iso()
    record["latestRender"] = render
    clear_render_stale(record, "png")
    if ensure_workflow(record).get("status") not in {"scheduled", "uploaded", "archived", "rejected"}:
        set_workflow_status(record, "png_rendered")
    record["updatedAt"] = now_iso()
    STORE.save(record)
    LOGGER.info("render_completed content_id=%s render_id=%s files=%d", item_id, item_render_id, len(files))
    return normalize_render_result(render)
