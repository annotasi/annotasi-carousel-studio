from __future__ import annotations

from ..common import *
from ..config import *
from ..errors import *

def check_ffmpeg_available() -> None:
    try:
        completed = subprocess.run(
            [FFMPEG_PATH, "-version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffmpeg_not_found", "FFmpeg is not installed or FFMPEG_PATH is invalid.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffmpeg_unavailable", "FFmpeg availability check timed out.") from exc
    if completed.returncode != 0:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffmpeg_unavailable", "FFmpeg is unavailable.")
    LOGGER.info("ffmpeg_availability_checked")


def check_ffprobe_available() -> None:
    try:
        completed = subprocess.run(
            [FFPROBE_PATH, "-version"],
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffprobe_not_found", "FFprobe is not installed or FFPROBE_PATH is invalid.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffprobe_unavailable", "FFprobe availability check timed out.") from exc
    if completed.returncode != 0:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffprobe_unavailable", "FFprobe is unavailable.")


def run_ffmpeg(args: list[str], timeout: float, failure_code: str, failure_message: str) -> None:
    try:
        completed = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffmpeg_not_found", "FFmpeg is not installed or FFMPEG_PATH is invalid.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(HTTPStatus.GATEWAY_TIMEOUT, "video_render_timeout", "FFmpeg video rendering timed out.") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else failure_message
        raise AppError(HTTPStatus.BAD_GATEWAY, failure_code, f"{failure_message}: {detail[:300]}")


def run_ffprobe_json(args: list[str]) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            args,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )
    except FileNotFoundError as exc:
        raise AppError(HTTPStatus.SERVICE_UNAVAILABLE, "ffprobe_not_found", "FFprobe is not installed or FFPROBE_PATH is invalid.") from exc
    except subprocess.TimeoutExpired as exc:
        raise AppError(HTTPStatus.GATEWAY_TIMEOUT, "ffprobe_timeout", "FFprobe timed out.") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()[-1] if completed.stderr.strip() else "FFprobe failed."
        raise AppError(HTTPStatus.BAD_GATEWAY, "ffprobe_failed", f"FFprobe failed: {detail[:300]}")
    try:
        data = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise AppError(HTTPStatus.BAD_GATEWAY, "ffprobe_invalid_json", "FFprobe returned invalid JSON.") from exc
    if not isinstance(data, dict):
        raise AppError(HTTPStatus.BAD_GATEWAY, "ffprobe_invalid_json", "FFprobe returned invalid JSON.")
    return data


def probe_media(path: Path) -> dict[str, Any]:
    return run_ffprobe_json(
        [
            FFPROBE_PATH,
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type",
            "-of",
            "json",
            str(path),
        ]
    )


def media_duration_seconds(probe: dict[str, Any], field_name: str) -> float:
    format_info = probe.get("format")
    if not isinstance(format_info, dict):
        raise AppError(HTTPStatus.BAD_GATEWAY, "duration_detection_failed", f"Could not detect {field_name} duration.")
    try:
        duration = float(format_info.get("duration"))
    except (TypeError, ValueError) as exc:
        raise AppError(HTTPStatus.BAD_GATEWAY, "duration_detection_failed", f"Could not detect {field_name} duration.") from exc
    if duration <= 0:
        raise AppError(HTTPStatus.BAD_GATEWAY, "duration_detection_failed", f"{field_name} duration is invalid.")
    return round(duration, 3)


def probe_has_stream(probe: dict[str, Any], stream_type: str) -> bool:
    streams = probe.get("streams")
    if not isinstance(streams, list):
        return False
    return any(isinstance(stream, dict) and stream.get("codec_type") == stream_type for stream in streams)


def resolve_allowed_audio_path(raw_path: str) -> Path:
    if not raw_path or "\x00" in raw_path:
        raise AppError(HTTPStatus.BAD_REQUEST, "invalid_audio_path", "Audio file path is invalid.")
    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        path = (SERVICE_DIR / path).resolve()
    else:
        path = path.resolve()
    allowed_root = CONTENT_AUDIO_DIR.resolve()
    try:
        path.relative_to(allowed_root)
    except ValueError as exc:
        raise AppError(
            HTTPStatus.BAD_REQUEST,
            "audio_path_not_allowed",
            f"Audio file must be inside CONTENT_AUDIO_DIR: {allowed_root}",
        ) from exc
    return path


def ensure_path_inside(path: Path, roots: list[Path], code: str = "path_not_allowed") -> Path:
    resolved = path.expanduser().resolve()
    for root in roots:
        try:
            resolved.relative_to(root.resolve())
            return resolved
        except ValueError:
            continue
    raise AppError(HTTPStatus.BAD_REQUEST, code, "File path is outside allowed directories.")
