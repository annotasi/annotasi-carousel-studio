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
from ..render.video_renderer import *

def format_audio_prepare_for_telegram(session: dict[str, Any]) -> list[str]:
    lines = [
        "Voiceover Mixing Mode",
        "",
        "Content ID:",
        str(session.get("contentId", "")),
        "",
        "Audio Session ID:",
        str(session.get("audioSessionId", "")),
        "",
        "Silakan kirim voice note atau file audio untuk content ID ini melalui Hermes, atau gunakan:",
        f"/mixvoice_file {session.get('contentId', '')} <audio_file_path>",
        "",
        "Supported formats:",
        ", ".join(session.get("supportedFormats", [])),
        "",
        "Reminder:",
        "Gunakan suara kamu sendiri. Jangan gunakan voice cloning atau imitasi suara orang lain.",
    ]
    return split_telegram_message("\n".join(lines).strip())


def format_audio_for_telegram(audio_render: dict[str, Any]) -> list[str]:
    output_video = audio_render.get("outputVideo") if isinstance(audio_render.get("outputVideo"), dict) else {}
    lines = [
        "Final Video dengan Voiceover",
        "",
        "Content ID:",
        str(audio_render.get("contentId", "")),
        "",
        "Audio Render ID:",
        str(audio_render.get("audioRenderId", "")),
        "",
        "Source Video Render ID:",
        str(audio_render.get("sourceVideoRenderId", "")),
        "",
        "Duration:",
        f"{audio_render.get('finalDurationSeconds')} seconds",
        "",
        "Output:",
        str(output_video.get("path") or output_video.get("filename") or "final-voiceover.mp4"),
        "",
        "Reminder:",
        "Review kembali sebelum upload agar tidak salah konteks.",
    ]
    return split_telegram_message("\n".join(lines).strip())


def normalize_audio_result(audio_render: dict[str, Any]) -> dict[str, Any]:
    return {**audio_render, "telegramMessages": format_audio_for_telegram(audio_render)}


def audio_file_exists(audio_render: dict[str, Any]) -> bool:
    output_video = audio_render.get("outputVideo")
    if not isinstance(output_video, dict):
        return False
    path = Path(str(output_video.get("path") or ""))
    return path.exists() and path.is_file() and path.stat().st_size > 0


def latest_completed_audio_render(
    record: dict[str, Any],
    *,
    source_video_render_id: str,
    source_audio_path: str,
    audio_mode: str,
    normalize_audio: bool,
    fit_mode: str,
) -> Optional[dict[str, Any]]:
    stale = ensure_workflow(record).get("renderStale", {})
    if isinstance(stale, dict) and stale.get("audio"):
        return None
    audio_renders = record.get("audioRenders")
    if not isinstance(audio_renders, list):
        return None
    normalized_source = str(Path(source_audio_path).resolve())
    for item in reversed(audio_renders):
        if not isinstance(item, dict):
            continue
        if (
            item.get("status") == "completed"
            and item.get("sourceVideoRenderId") == source_video_render_id
            and item.get("sourceAudioPath") == normalized_source
            and item.get("audioMode") == audio_mode
            and item.get("normalizeAudio") == normalize_audio
            and item.get("fitMode") == fit_mode
            and audio_file_exists(item)
        ):
            return item
    return None


def validate_audio_file(raw_path: str) -> tuple[Path, float]:
    LOGGER.info("audio_validation_started")
    path = resolve_allowed_audio_path(raw_path)
    if not path.exists() or not path.is_file():
        raise AppError(HTTPStatus.NOT_FOUND, "audio_file_missing", "Audio file was not found.")
    extension = path.suffix.lower().lstrip(".")
    if extension not in AUDIO_ALLOWED_EXTENSIONS:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "unsupported_audio_format", "Audio format is not supported.")
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > AUDIO_MAX_FILE_SIZE_MB:
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "audio_too_large", "Audio file exceeds configured size limit.")
    probe = probe_media(path)
    if not probe_has_stream(probe, "audio"):
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_audio_stream", "Audio file has no valid audio stream.")
    duration = media_duration_seconds(probe, "audio")
    LOGGER.info("audio_validation_completed duration_seconds=%s size_mb=%.2f", duration, size_mb)
    return path, duration


def normalize_voiceover_audio(source_path: Path, output_path: Path, video_duration: float) -> None:
    LOGGER.info("normalization_started")
    args = [
        FFMPEG_PATH,
        "-y",
        "-i",
        str(source_path),
        "-t",
        f"{video_duration:.3f}",
        "-vn",
        "-af",
        "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ar",
        "48000",
        "-ac",
        "2",
        "-c:a",
        "pcm_s16le",
        str(output_path),
    ]
    run_ffmpeg(args, AUDIO_RENDER_TIMEOUT_SECONDS, "audio_normalization_failed", "FFmpeg failed to normalize audio")
    if not output_path.exists() or output_path.stat().st_size <= 0:
        raise AppError(HTTPStatus.BAD_GATEWAY, "audio_normalization_failed", "Normalized audio file is missing or empty.")
    LOGGER.info("normalization_completed")


def mix_voiceover_video(source_video: Path, source_audio: Path, output_video: Path, video_duration: float) -> None:
    LOGGER.info("mixing_started")
    args = [
        FFMPEG_PATH,
        "-y",
        "-i",
        str(source_video),
        "-i",
        str(source_audio),
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-c:v",
        "copy",
        "-c:a",
        AUDIO_OUTPUT_CODEC,
        "-b:a",
        "192k",
        "-t",
        f"{video_duration:.3f}",
        "-movflags",
        "+faststart",
        str(output_video),
    ]
    run_ffmpeg(args, AUDIO_RENDER_TIMEOUT_SECONDS, "audio_mixing_failed", "FFmpeg failed to mix audio into video")
    if not output_video.exists() or output_video.stat().st_size <= 0:
        raise AppError(HTTPStatus.BAD_GATEWAY, "audio_output_missing", "Generated voiceover MP4 is missing or empty.")
    LOGGER.info("mixing_completed")


def write_audio_metadata(output_dir: Path, audio_render: dict[str, Any]) -> None:
    metadata_path = output_dir / "audio-render-metadata.json"
    try:
        metadata_path.write_text(json.dumps(audio_render, ensure_ascii=False, indent=2), encoding="utf-8")
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "metadata_write_failed", "Could not write audio metadata.") from exc


def prepare_audio_session(item_id: str) -> dict[str, Any]:
    LOGGER.info("audio_prepare_request_received content_id=%s", item_id)
    record = STORE.get(item_id)
    validate_renderable_content(record)
    audio_dir = (CONTENT_AUDIO_DIR / item_id).resolve()
    try:
        audio_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "audio_directory_not_writable", "Audio directory is not writable.") from exc
    session = {
        "contentId": item_id,
        "audioSessionId": audio_render_id(),
        "status": "waiting_for_audio",
        "supportedFormats": sorted(AUDIO_ALLOWED_EXTENSIONS),
        "audioDirectory": str(audio_dir),
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    if not isinstance(record.get("audioSessions"), list):
        record["audioSessions"] = []
    record["audioSessions"].append(session)
    record["latestAudioSession"] = session
    record["updatedAt"] = now_iso()
    STORE.save(record)
    return {**session, "telegramMessages": format_audio_prepare_for_telegram(session)}


def render_content_audio_mix(item_id: str, body: dict[str, Any]) -> dict[str, Any]:
    audio_file_path = str(body.get("audioFilePath") or "").strip()
    if not audio_file_path:
        raise AppError(HTTPStatus.BAD_REQUEST, "missing_audio_file_path", "audioFilePath is required.")
    audio_mode = str(body.get("audioMode") or "voiceover").strip()
    normalize_audio = bool(body.get("normalizeAudio", AUDIO_NORMALIZE_ENABLED))
    fit_mode = str(body.get("fitMode") or AUDIO_DEFAULT_FIT_MODE).strip()
    force_regenerate = bool(body.get("forceRegenerate", False))

    if audio_mode != "voiceover":
        raise AppError(HTTPStatus.BAD_REQUEST, "unsupported_audio_mode", "Only voiceover audio mode is supported.")
    if fit_mode != "trim_or_pad":
        raise AppError(HTTPStatus.BAD_REQUEST, "unsupported_fit_mode", "Only trim_or_pad fit mode is supported.")

    LOGGER.info("audio_mix_request_received content_id=%s mode=%s", item_id, audio_mode)
    record = STORE.get(item_id)
    validate_renderable_content(record)
    LOGGER.info("content_loaded content_id=%s", item_id)

    video_render = latest_completed_video_for_audio(record)
    if not video_render:
        raise AppError(HTTPStatus.NOT_FOUND, "video_render_not_found", "Video render not found. Run /video <content_id> first.")
    source_video = Path(str(video_render.get("file", {}).get("path") if isinstance(video_render.get("file"), dict) else ""))
    if not source_video.exists() or not source_video.is_file() or source_video.stat().st_size <= 0:
        raise AppError(HTTPStatus.NOT_FOUND, "source_mp4_missing", "Source MP4 is missing. Run /video again.")
    LOGGER.info("video_render_loaded content_id=%s video_render_id=%s", item_id, video_render.get("videoRenderId"))

    check_ffmpeg_available()
    check_ffprobe_available()

    video_probe = probe_media(source_video)
    if not probe_has_stream(video_probe, "video"):
        raise AppError(HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_source_video", "Source MP4 has no valid video stream.")
    video_duration = media_duration_seconds(video_probe, "video")

    audio_path, audio_duration = validate_audio_file(audio_file_path)
    LOGGER.info("audio_video_durations_detected video_seconds=%s audio_seconds=%s", video_duration, audio_duration)

    existing = latest_completed_audio_render(
        record,
        source_video_render_id=str(video_render.get("videoRenderId") or ""),
        source_audio_path=str(audio_path),
        audio_mode=audio_mode,
        normalize_audio=normalize_audio,
        fit_mode=fit_mode,
    )
    if existing and not force_regenerate:
        LOGGER.info("duplicate_audio_render_returned content_id=%s audio_render_id=%s", item_id, existing.get("audioRenderId"))
        return normalize_audio_result(existing)

    item_audio_render_id = audio_render_id()
    output_dir = (EXPORT_DIR / item_id / item_audio_render_id).resolve()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise AppError(HTTPStatus.INTERNAL_SERVER_ERROR, "output_not_writable", "Output directory is not writable.") from exc

    normalized_audio_path = output_dir / "voiceover-normalized.wav" if normalize_audio else None
    output_video_path = output_dir / "final-voiceover.mp4"
    audio_render = {
        "contentId": item_id,
        "audioRenderId": item_audio_render_id,
        "status": "processing",
        "sourceVideoRenderId": video_render.get("videoRenderId"),
        "sourceAudioPath": str(audio_path),
        "normalizedAudioPath": str(normalized_audio_path) if normalized_audio_path else "",
        "audioFile": {"filename": audio_path.name, "path": str(audio_path)},
        "outputVideo": {"filename": "final-voiceover.mp4", "path": str(output_video_path), "mimeType": "video/mp4"},
        "audioMode": audio_mode,
        "normalizeAudio": normalize_audio,
        "fitMode": fit_mode,
        "videoDurationSeconds": video_duration,
        "audioDurationSeconds": audio_duration,
        "finalDurationSeconds": video_duration,
        "statusMessage": "",
        "errorMessage": "",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    if not isinstance(record.get("audioRenders"), list):
        record["audioRenders"] = []
    record["audioRenders"].append(audio_render)
    record["latestAudioRender"] = audio_render
    record["updatedAt"] = now_iso()
    STORE.save(record)

    try:
        audio_to_mix = audio_path
        if normalize_audio and normalized_audio_path:
            normalize_voiceover_audio(audio_path, normalized_audio_path, video_duration)
            audio_to_mix = normalized_audio_path
        mix_voiceover_video(source_video, audio_to_mix, output_video_path, video_duration)
        final_probe = probe_media(output_video_path)
        if not probe_has_stream(final_probe, "video") or not probe_has_stream(final_probe, "audio"):
            raise AppError(HTTPStatus.BAD_GATEWAY, "invalid_audio_output", "Generated MP4 is missing video or audio stream.")
        audio_render["finalDurationSeconds"] = media_duration_seconds(final_probe, "final video")
    except AppError as exc:
        audio_render["status"] = "failed"
        audio_render["errorMessage"] = exc.message
        audio_render["updatedAt"] = now_iso()
        record["latestAudioRender"] = audio_render
        record["updatedAt"] = now_iso()
        STORE.save(record)
        raise

    audio_render["status"] = "completed"
    audio_render["updatedAt"] = now_iso()
    write_audio_metadata(output_dir, audio_render)
    record["latestAudioRender"] = audio_render
    clear_render_stale(record, "audio")
    if ensure_workflow(record).get("status") not in {"scheduled", "uploaded", "archived", "rejected"}:
        set_workflow_status(record, "voiceover_ready")
    record["updatedAt"] = now_iso()
    STORE.save(record)
    LOGGER.info("audio_metadata_stored content_id=%s audio_render_id=%s", item_id, item_audio_render_id)
    return normalize_audio_result(audio_render)
