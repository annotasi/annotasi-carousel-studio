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
from ..render.png_renderer import latest_completed_png_render, validate_png_files

def format_video_for_telegram(video_render: dict[str, Any]) -> list[str]:
    file_info = video_render.get("file") if isinstance(video_render.get("file"), dict) else {}
    lines = [
        "Annotasi Motion Video Rendered",
        "",
        "Content ID:",
        str(video_render.get("contentId", "")),
        "",
        "Video Render ID:",
        str(video_render.get("videoRenderId", "")),
        "",
        "Format:",
        f"Vertical MP4 {video_render.get('width')}x{video_render.get('height')}",
        "",
        "Slides:",
        str(video_render.get("slideCount", "")),
        "",
        "Duration:",
        f"{video_render.get('totalDurationSeconds')} seconds",
        "",
        "Output:",
        str(file_info.get("path") or file_info.get("filename") or "final.mp4"),
        "",
        "Reminder:",
        "Review kembali sebelum upload agar tidak salah konteks.",
    ]
    return split_telegram_message("\n".join(lines).strip())


def normalize_video_result(video_render: dict[str, Any]) -> dict[str, Any]:
    return {**video_render, "telegramMessages": format_video_for_telegram(video_render)}


def latest_completed_video_for_audio(record: dict[str, Any]) -> Optional[dict[str, Any]]:
    video_renders = record.get("videoRenders")
    if not isinstance(video_renders, list):
        return None
    for item in reversed(video_renders):
        if isinstance(item, dict) and item.get("status") == "completed" and video_file_exists(item):
            return item
    return None


def video_file_exists(video_render: dict[str, Any]) -> bool:
    file_info = video_render.get("file")
    if not isinstance(file_info, dict):
        return False
    path = Path(str(file_info.get("path") or ""))
    return path.exists() and path.is_file() and path.stat().st_size > 0


def latest_completed_video_render(
    record: dict[str, Any],
    *,
    output_format: str,
    template_name: str,
    motion_preset: str,
    width: int,
    height: int,
    fps: int,
    duration_per_slide: float,
    transition_seconds: float,
) -> Optional[dict[str, Any]]:
    stale = ensure_workflow(record).get("renderStale", {})
    if isinstance(stale, dict) and stale.get("video"):
        return None
    video_renders = record.get("videoRenders")
    if not isinstance(video_renders, list):
        return None
    for item in reversed(video_renders):
        if not isinstance(item, dict):
            continue
        if (
            item.get("status") == "completed"
            and item.get("format") == output_format
            and item.get("templateName") == template_name
            and item.get("motionPreset") == motion_preset
            and item.get("width") == width
            and item.get("height") == height
            and item.get("fps") == fps
            and float(item.get("durationPerSlideSeconds", -1)) == duration_per_slide
            and float(item.get("transitionSeconds", -1)) == transition_seconds
            and video_file_exists(item)
        ):
            return item
    return None


def video_filter_for_slide(
    *,
    motion_preset: str,
    width: int,
    height: int,
    fps: int,
    duration: float,
    transition: float,
) -> str:
    frames = max(1, int(round(duration * fps)))
    safe_transition = max(0.0, min(transition, duration / 2))
    fade_in = min(0.25, safe_transition)
    fade_out_start = max(0.0, duration - safe_transition)
    foreground_width = width
    foreground_height = min(height, int(round(width * 1.25)))
    base_scale = (
        f"[0:v]scale={foreground_width}:{foreground_height}:force_original_aspect_ratio=decrease,"
        f"pad={foreground_width}:{foreground_height}:(ow-iw)/2:(oh-ih)/2:color=#12110d"
    )
    if motion_preset == "calm_zoom":
        foreground = (
            f"{base_scale},"
            f"zoompan=z='min(zoom+0.00035,1.035)':d={frames}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={foreground_width}x{foreground_height}:"
            f"fps={fps}[fg]"
        )
    else:
        foreground = f"{base_scale},setsar=1[fg]"
    return (
        f"{foreground};"
        f"[1:v][fg]overlay=(W-w)/2:(H-h)/2:format=auto,"
        f"format=yuv420p,"
        f"fade=t=in:st=0:d={fade_in:.3f},"
        f"fade=t=out:st={fade_out_start:.3f}:d={safe_transition:.3f}[v]"
    )


def create_video_segment(
    *,
    png_path: Path,
    segment_path: Path,
    motion_preset: str,
    width: int,
    height: int,
    fps: int,
    duration: float,
    transition: float,
) -> None:
    filter_graph = video_filter_for_slide(
        motion_preset=motion_preset,
        width=width,
        height=height,
        fps=fps,
        duration=duration,
        transition=transition,
    )
    args = [
        FFMPEG_PATH,
        "-y",
        "-loop",
        "1",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(png_path),
        "-f",
        "lavfi",
        "-t",
        f"{duration:.3f}",
        "-i",
        f"color=c=#12110d:s={width}x{height}:r={fps}",
        "-filter_complex",
        filter_graph,
        "-map",
        "[v]",
        "-frames:v",
        str(max(1, int(round(duration * fps)))),
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(segment_path),
    ]
    run_ffmpeg(args, VIDEO_RENDER_TIMEOUT_SECONDS, "ffmpeg_segment_failed", "FFmpeg failed to render a slide segment")


def concat_segments(segment_paths: list[Path], concat_file: Path, output_path: Path) -> None:
    lines = []
    for segment_path in segment_paths:
        escaped = str(segment_path).replace("'", "'\\''")
        lines.append(f"file '{escaped}'")
    concat_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    args = [
        FFMPEG_PATH,
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(concat_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    run_ffmpeg(args, VIDEO_RENDER_TIMEOUT_SECONDS, "ffmpeg_concat_failed", "FFmpeg failed to export final MP4")


def write_video_metadata(output_dir: Path, video_render: dict[str, Any]) -> None:
    metadata_path = output_dir / "render-metadata.json"
    try:
        metadata_path.write_text(json.dumps(video_render, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "metadata_write_failed", "Could not write video metadata.") from exc


def render_content_video(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    output_format = str(body.get("format") or VIDEO_DEFAULT_FORMAT).strip()
    template_name = str(body.get("template") or DEFAULT_TEMPLATE).strip()
    motion_preset = str(body.get("motionPreset") or VIDEO_DEFAULT_MOTION_PRESET).strip()
    force_regenerate = bool(body.get("forceRegenerate", False))
    width = parse_int(body.get("width"), VIDEO_WIDTH, "width")
    height = parse_int(body.get("height"), VIDEO_HEIGHT, "height")
    fps = parse_int(body.get("fps"), VIDEO_FPS, "fps")
    duration_per_slide = parse_float(body.get("durationPerSlideSeconds"), VIDEO_DURATION_PER_SLIDE_SECONDS, "durationPerSlideSeconds")
    transition_seconds = parse_float(body.get("transitionSeconds"), VIDEO_TRANSITION_SECONDS, "transitionSeconds")

    if output_format != "shorts_vertical":
        raise AppError(HTTPStatus.BAD_REQUEST, "unsupported_format", "Only shorts_vertical is supported.")
    if template_name != "annotasi_hikmah_dark":
        raise AppError(HTTPStatus.BAD_REQUEST, "template_not_found", "Template was not found.")
    if motion_preset not in {"calm_zoom", "static"}:
        raise AppError(HTTPStatus.BAD_REQUEST, "unsupported_motion_preset", "Only calm_zoom and static are supported.")
    if width <= 0 or height <= 0 or fps <= 0:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_video_settings", "Video dimensions and fps must be positive.")
    if duration_per_slide <= 0 or transition_seconds < 0:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_video_settings", "Video durations must be valid positive numbers.")
    if body.get("includeVoiceover") or body.get("voiceoverAudioPath"):
        raise AppError(HTTPStatus.BAD_REQUEST, "voiceover_not_supported", "Voiceover audio mixing is reserved for a future milestone.")
    if body.get("backgroundMusicPath"):
        raise AppError(HTTPStatus.BAD_REQUEST, "background_music_not_supported", "Background music mixing is reserved for a future milestone.")

    LOGGER.info("video_render_request_received content_id=%s format=%s preset=%s", item_id, output_format, motion_preset)
    record = STORE.get(item_id)
    slides = validate_renderable_content(record)
    LOGGER.info("content_loaded content_id=%s slides=%d", item_id, len(slides))

    png_render = latest_completed_png_render(record)
    if not png_render:
        raise AppError(HTTPStatus.NOT_FOUND, "png_render_not_found", "PNG render not found. Run /render <content_id> first.")
    png_files = validate_png_files(png_render, len(slides))
    LOGGER.info("png_render_loaded content_id=%s render_id=%s", item_id, png_render.get("renderId"))

    existing = latest_completed_video_render(
        record,
        output_format=output_format,
        template_name=template_name,
        motion_preset=motion_preset,
        width=width,
        height=height,
        fps=fps,
        duration_per_slide=duration_per_slide,
        transition_seconds=transition_seconds,
    )
    if existing and not force_regenerate:
        LOGGER.info("duplicate_video_render_returned content_id=%s video_render_id=%s", item_id, existing.get("videoRenderId"))
        return normalize_video_result(existing)

    check_ffmpeg_available()

    item_video_render_id = video_render_id()
    output_dir = (EXPORT_DIR / item_id / item_video_render_id).resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "output_not_writable", "Output directory is not writable.") from exc

    total_duration = round(len(png_files) * duration_per_slide, 3)
    output_path = output_dir / "final.mp4"
    video_render = {
        "contentId": item_id,
        "videoRenderId": item_video_render_id,
        "status": "rendering",
        "sourcePngRenderId": png_render.get("renderId"),
        "format": output_format,
        "templateName": template_name,
        "motionPreset": motion_preset,
        "width": width,
        "height": height,
        "fps": fps,
        "durationPerSlideSeconds": duration_per_slide,
        "transitionSeconds": transition_seconds,
        "totalDurationSeconds": total_duration,
        "slideCount": len(png_files),
        "file": {"filename": "final.mp4", "path": str(output_path), "mimeType": "video/mp4"},
        "errorMessage": "",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    if not isinstance(record.get("videoRenders"), list):
        record["videoRenders"] = []
    record["videoRenders"].append(video_render)
    record["latestVideoRender"] = video_render
    record["updatedAt"] = now_iso()
    STORE.save(record)

    try:
        LOGGER.info("video_render_plan_created content_id=%s video_render_id=%s slides=%d", item_id, item_video_render_id, len(png_files))
        segment_paths = []
        for file_info in png_files:
            slide_number = int(file_info["slideNumber"])
            LOGGER.info("segment_generation_started content_id=%s video_render_id=%s slide=%d", item_id, item_video_render_id, slide_number)
            segment_path = output_dir / f"segment-{slide_number:02d}.mp4"
            create_video_segment(
                png_path=Path(str(file_info["path"])),
                segment_path=segment_path,
                motion_preset=motion_preset,
                width=width,
                height=height,
                fps=fps,
                duration=duration_per_slide,
                transition=transition_seconds,
            )
            if not segment_path.exists() or segment_path.stat().st_size <= 0:
                raise AppError(HTTPStatus.BAD_GATEWAY, "segment_missing", f"Segment missing for slide {slide_number}.")
            segment_paths.append(segment_path)
            LOGGER.info("segment_generation_completed content_id=%s video_render_id=%s slide=%d", item_id, item_video_render_id, slide_number)

        LOGGER.info("final_video_export_started content_id=%s video_render_id=%s", item_id, item_video_render_id)
        concat_segments(segment_paths, output_dir / "segments.txt", output_path)
        if not output_path.exists() or output_path.stat().st_size <= 0:
            raise AppError(HTTPStatus.BAD_GATEWAY, "video_output_missing", "Generated MP4 is missing or empty.")
        LOGGER.info("final_video_export_completed content_id=%s video_render_id=%s", item_id, item_video_render_id)
    except AppError as exc:
        video_render["status"] = "failed"
        video_render["errorMessage"] = exc.message
        video_render["updatedAt"] = now_iso()
        record["latestVideoRender"] = video_render
        record["updatedAt"] = now_iso()
        STORE.save(record)
        raise

    video_render["status"] = "completed"
    video_render["updatedAt"] = now_iso()
    write_video_metadata(output_dir, video_render)
    record["latestVideoRender"] = video_render
    clear_render_stale(record, "video")
    if ensure_workflow(record).get("status") not in {"scheduled", "uploaded", "archived", "rejected"}:
        set_workflow_status(record, "video_rendered")
    record["updatedAt"] = now_iso()
    STORE.save(record)
    LOGGER.info("video_metadata_stored content_id=%s video_render_id=%s", item_id, item_video_render_id)
    return normalize_video_result(video_render)
