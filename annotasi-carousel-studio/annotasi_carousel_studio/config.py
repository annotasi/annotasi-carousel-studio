from __future__ import annotations

from .common import *



AI_BASE_URL = os.getenv("AI_BASE_URL", "http://127.0.0.1:20128/v1")
AI_MODEL = os.getenv("AI_MODEL", "annotasi-coding")
AI_API_KEY = os.getenv("AI_API_KEY", "")
AI_TIMEOUT_SECONDS = float(os.getenv("AI_TIMEOUT_SECONDS", "90"))
HOST = os.getenv("ANNOTASI_HOST", "127.0.0.1")
PORT = int(os.getenv("ANNOTASI_PORT", "8097"))
STORAGE_DIR = Path(os.getenv("CONTENT_STORAGE_DIR", "./data/content"))
SOURCE_STORAGE_DIR = Path(os.getenv("SOURCE_STORAGE_DIR", "./data/sources"))
EXPORT_DIR = Path(os.getenv("CONTENT_EXPORT_DIR", "./data/exports"))
PACKAGE_DIR = Path(os.getenv("CONTENT_PACKAGE_DIR", "./data/packages"))
DEFAULT_TEMPLATE = os.getenv("CAROUSEL_DEFAULT_TEMPLATE", "annotasi_hikmah_dark")
CAROUSEL_WIDTH = int(os.getenv("CAROUSEL_WIDTH", "1080"))
CAROUSEL_HEIGHT = int(os.getenv("CAROUSEL_HEIGHT", "1350"))
RENDER_TIMEOUT_SECONDS = float(os.getenv("CAROUSEL_RENDER_TIMEOUT_SECONDS", "60"))
VIDEO_DEFAULT_FORMAT = os.getenv("VIDEO_DEFAULT_FORMAT", "shorts_vertical")
VIDEO_WIDTH = int(os.getenv("VIDEO_WIDTH", "1080"))
VIDEO_HEIGHT = int(os.getenv("VIDEO_HEIGHT", "1920"))
VIDEO_FPS = int(os.getenv("VIDEO_FPS", "30"))
VIDEO_DURATION_PER_SLIDE_SECONDS = float(os.getenv("VIDEO_DURATION_PER_SLIDE_SECONDS", "5"))
VIDEO_TRANSITION_SECONDS = float(os.getenv("VIDEO_TRANSITION_SECONDS", "0.5"))
VIDEO_DEFAULT_MOTION_PRESET = os.getenv("VIDEO_DEFAULT_MOTION_PRESET", "calm_zoom")
VIDEO_RENDER_TIMEOUT_SECONDS = float(os.getenv("VIDEO_RENDER_TIMEOUT_SECONDS", "180"))
FFMPEG_PATH = os.getenv("FFMPEG_PATH", "ffmpeg")
FFPROBE_PATH = os.getenv("FFPROBE_PATH", "ffprobe")
CONTENT_AUDIO_DIR = Path(os.getenv("CONTENT_AUDIO_DIR", "./data/audio"))
AUDIO_MAX_FILE_SIZE_MB = float(os.getenv("AUDIO_MAX_FILE_SIZE_MB", "50"))
AUDIO_ALLOWED_EXTENSIONS = {
    part.strip().lower().lstrip(".")
    for part in os.getenv("AUDIO_ALLOWED_EXTENSIONS", "mp3,m4a,wav,ogg,oga").split(",")
    if part.strip()
}
AUDIO_NORMALIZE_ENABLED = os.getenv("AUDIO_NORMALIZE_ENABLED", "true").lower() in {"1", "true", "yes", "on"}
AUDIO_DEFAULT_FIT_MODE = os.getenv("AUDIO_DEFAULT_FIT_MODE", "trim_or_pad")
AUDIO_RENDER_TIMEOUT_SECONDS = float(os.getenv("AUDIO_RENDER_TIMEOUT_SECONDS", "180"))
AUDIO_OUTPUT_CODEC = os.getenv("AUDIO_OUTPUT_CODEC", "aac")
CONTENT_TIMEZONE = os.getenv("CONTENT_TIMEZONE", "Asia/Jakarta")
CONTENT_DEFAULT_CALENDAR_DAYS = int(os.getenv("CONTENT_DEFAULT_CALENDAR_DAYS", "7"))
CONTENT_ALLOW_SCHEDULE_REJECTED = os.getenv("CONTENT_ALLOW_SCHEDULE_REJECTED", "false").lower() in {"1", "true", "yes", "on"}
CONTENT_REQUIRE_APPROVAL_BEFORE_SCHEDULE = os.getenv("CONTENT_REQUIRE_APPROVAL_BEFORE_SCHEDULE", "true").lower() in {"1", "true", "yes", "on"}
SOURCE_REQUIRE_APPROVAL_FOR_GENERATION = os.getenv("SOURCE_REQUIRE_APPROVAL_FOR_GENERATION", "false").lower() in {"1", "true", "yes", "on"}
SOURCE_BLOCK_RESTRICTED_GENERATION = os.getenv("SOURCE_BLOCK_RESTRICTED_GENERATION", "true").lower() in {"1", "true", "yes", "on"}
TRANSCRIPT_MAX_CHARS_DIRECT = int(os.getenv("TRANSCRIPT_MAX_CHARS_DIRECT", "12000"))
TRANSCRIPT_SEGMENT_MIN_WORDS = int(os.getenv("TRANSCRIPT_SEGMENT_MIN_WORDS", "300"))
TRANSCRIPT_SEGMENT_MAX_WORDS = int(os.getenv("TRANSCRIPT_SEGMENT_MAX_WORDS", "800"))
SOURCE_DEFAULT_LANGUAGE = os.getenv("SOURCE_DEFAULT_LANGUAGE", "id")
SOURCE_DEFAULT_PERMISSION_STATUS = os.getenv("SOURCE_DEFAULT_PERMISSION_STATUS", "unknown")
CANDIDATE_BLOCK_RESTRICTED_SOURCE = os.getenv("CANDIDATE_BLOCK_RESTRICTED_SOURCE", "true").lower() in {"1", "true", "yes", "on"}
CANDIDATE_ALLOW_UNKNOWN_PERMISSION = os.getenv("CANDIDATE_ALLOW_UNKNOWN_PERMISSION", "true").lower() in {"1", "true", "yes", "on"}
CANDIDATE_ALLOW_HIGH_RISK = os.getenv("CANDIDATE_ALLOW_HIGH_RISK", "false").lower() in {"1", "true", "yes", "on"}
CANDIDATE_DEFAULT_COUNT = int(os.getenv("CANDIDATE_DEFAULT_COUNT", "10"))
CANDIDATE_MAX_TRANSCRIPT_CHARS = int(os.getenv("CANDIDATE_MAX_TRANSCRIPT_CHARS", "30000"))
CANDIDATE_MAX_SEGMENTS_PER_RUN = int(os.getenv("CANDIDATE_MAX_SEGMENTS_PER_RUN", "20"))
CANDIDATE_ALLOWED_TYPES = {
    part.strip().lower()
    for part in os.getenv("CANDIDATE_ALLOWED_TYPES", "carousel,short_video,voiceover_reflection,quote_post,mixed").split(",")
    if part.strip()
}
CONTENT_PACKAGE_CREATE_ZIP = os.getenv("CONTENT_PACKAGE_CREATE_ZIP", "true").lower() in {"1", "true", "yes", "on"}
CONTENT_PACKAGE_REQUIRE_APPROVAL = os.getenv("CONTENT_PACKAGE_REQUIRE_APPROVAL", "true").lower() in {"1", "true", "yes", "on"}
CONTENT_PACKAGE_INCLUDE_METADATA = os.getenv("CONTENT_PACKAGE_INCLUDE_METADATA", "true").lower() in {"1", "true", "yes", "on"}
CONTENT_PACKAGE_INCLUDE_PLATFORM_CAPTIONS = os.getenv("CONTENT_PACKAGE_INCLUDE_PLATFORM_CAPTIONS", "true").lower() in {"1", "true", "yes", "on"}
CONTENT_PACKAGE_TIMEZONE = os.getenv("CONTENT_PACKAGE_TIMEZONE", CONTENT_TIMEZONE)
CONTENT_PACKAGE_MAX_ZIP_SIZE_MB = float(os.getenv("CONTENT_PACKAGE_MAX_ZIP_SIZE_MB", "200"))
CONTENT_PACKAGE_ALLOW_STALE_MEDIA = os.getenv("CONTENT_PACKAGE_ALLOW_STALE_MEDIA", "false").lower() in {"1", "true", "yes", "on"}
TELEGRAM_LIMIT = int(os.getenv("TELEGRAM_MESSAGE_LIMIT", "3900"))
SERVICE_DIR = Path(__file__).resolve().parent.parent
NODE_RENDERER = SERVICE_DIR / "render_png.js"
VALID_WORKFLOW_STATUSES = {
    "idea",
    "generated",
    "needs_review",
    "reviewed",
    "edit_requested",
    "approved",
    "png_rendered",
    "video_rendered",
    "voiceover_ready",
    "scheduled",
    "uploaded",
    "archived",
    "rejected",
}
SCHEDULABLE_STATUSES = {"approved", "png_rendered", "video_rendered", "voiceover_ready", "scheduled", "uploaded"}
SUPPORTED_PLATFORMS = {"instagram", "tiktok", "youtube_shorts", "facebook_reels", "linkedin", "manual"}
SUPPORTED_SOURCE_TYPES = {
    "youtube_video",
    "instagram_video",
    "tiktok_video",
    "podcast",
    "webinar",
    "user_uploaded_video",
    "manual_note",
    "article",
    "book",
    "other",
}
SUPPORTED_SOURCE_PLATFORMS = {"youtube", "instagram", "tiktok", "spotify", "website", "local_file", "manual", "other"}
SUPPORTED_PERMISSION_STATUSES = {
    "unknown",
    "allowed_for_dakwah",
    "allowed_with_credit",
    "own_content",
    "needs_permission",
    "restricted",
    "rejected",
}
SUPPORTED_SOURCE_STATUSES = {"draft", "needs_review", "approved", "restricted", "archived"}
SUPPORTED_TRANSCRIPT_STATUSES = {"available", "draft", "archived"}
SUPPORTED_RISK_LEVELS = {"low", "medium", "high"}
SUPPORTED_CANDIDATE_TYPES = {"carousel", "short_video", "voiceover_reflection", "quote_post", "mixed"}
SUPPORTED_CANDIDATE_STATUSES = {"suggested", "needs_review", "approved", "rejected", "converted_to_content", "archived"}
SUPPORTED_PACKAGE_STATUSES = {"not_started", "packaging", "completed", "failed", "stale"}

LOGGER = logging.getLogger("annotasi_carousel_studio")
