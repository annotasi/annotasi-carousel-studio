from __future__ import annotations

from ..common import *

def content_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"cnt_{stamp}_{secrets.token_hex(4)}"


def render_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"rnd_{stamp}_{secrets.token_hex(4)}"


def video_render_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"vid_{stamp}_{secrets.token_hex(4)}"


def audio_render_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"aud_{stamp}_{secrets.token_hex(4)}"


def package_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"pkg_{stamp}_{secrets.token_hex(4)}"


def source_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"src_{stamp}_{secrets.token_hex(4)}"


def transcript_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"tr_{stamp}_{secrets.token_hex(4)}"


def segment_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"seg_{stamp}_{secrets.token_hex(4)}"


def candidate_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return f"cand_{stamp}_{secrets.token_hex(4)}"
