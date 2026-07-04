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
def validate_content(content: dict[str, Any]) -> dict[str, Any]:
    required_strings = ["title", "niche", "tone", "caption", "voiceoverScript", "sourceCreditSuggestion", "callToAction"]
    for key in required_strings:
        if not isinstance(content.get(key), str) or not content[key].strip():
            raise ValidationError(f"Missing or invalid field: {key}")
        content[key] = content[key].strip()

    slides = content.get("slides")
    if not isinstance(slides, list) or not 5 <= len(slides) <= 8:
        raise ValidationError("slides must contain 5 to 8 items.")
    for index, slide in enumerate(slides, start=1):
        if not isinstance(slide, dict):
            raise ValidationError("Each slide must be an object.")
        slide["slideNumber"] = parse_int(
            slide.get("slideNumber"),
            index,
            "slideNumber",
            HTTPStatus.BAD_GATEWAY,
            "ai_validation_failed",
        )
        if slide["slideNumber"] != index:
            slide["slideNumber"] = index
        if slide.get("type") not in {"hook", "body", "closing"}:
            raise ValidationError(f"Invalid slide type at slide {index}.")
        for key in ["text", "visualDirection"]:
            if not isinstance(slide.get(key), str) or not slide[key].strip():
                raise ValidationError(f"Missing {key} at slide {index}.")
            slide[key] = slide[key].strip()
        if word_count(slide["text"]) > 25:
            raise ValidationError(f"Slide {index} exceeds 25 words.")

    storyboard = content.get("videoStoryboard")
    if not isinstance(storyboard, list) or not storyboard:
        raise ValidationError("videoStoryboard must contain at least one scene.")
    for index, scene in enumerate(storyboard, start=1):
        if not isinstance(scene, dict):
            raise ValidationError("Each storyboard scene must be an object.")
        scene["sceneNumber"] = parse_int(
            scene.get("sceneNumber"),
            index,
            "sceneNumber",
            HTTPStatus.BAD_GATEWAY,
            "ai_validation_failed",
        )
        scene["durationSeconds"] = parse_int(
            scene.get("durationSeconds"),
            5,
            "durationSeconds",
            HTTPStatus.BAD_GATEWAY,
            "ai_validation_failed",
        )
        for key in ["visual", "motion", "voiceoverPart"]:
            if not isinstance(scene.get(key), str) or not scene[key].strip():
                raise ValidationError(f"Missing {key} at scene {index}.")
            scene[key] = scene[key].strip()

    content["hashtags"] = normalize_hashtags(content.get("hashtags"))
    if not content["hashtags"]:
        raise ValidationError("hashtags must contain at least one tag.")

    notes = content.get("safetyNotes")
    if isinstance(notes, list):
        safety_notes = [str(item).strip() for item in notes if str(item).strip()]
    else:
        safety_notes = []
    reminder = "Review kembali sebelum upload agar tidak salah konteks."
    if reminder not in safety_notes:
        safety_notes.append(reminder)
    content["safetyNotes"] = safety_notes

    LOGGER.info("json_validation_success slides=%d storyboard=%d", len(slides), len(storyboard))
    return content


def validate_ideas(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data.get("niche"), str) or not data["niche"].strip():
        raise ValidationError("Missing niche.")
    ideas = data.get("ideas")
    if not isinstance(ideas, list) or len(ideas) != 10:
        raise ValidationError("ideas must contain exactly 10 items.")
    for idea in ideas:
        if not isinstance(idea, dict):
            raise ValidationError("Each idea must be an object.")
        for key in ["title", "angle", "sampleHook"]:
            if not isinstance(idea.get(key), str) or not idea[key].strip():
                raise ValidationError(f"Missing idea field: {key}")
            idea[key] = idea[key].strip()
    notes = data.get("safetyNotes")
    data["safetyNotes"] = [str(item).strip() for item in notes if str(item).strip()] if isinstance(notes, list) else []
    return data


def validate_candidate_payload(item: dict[str, Any], source: dict[str, Any], transcript: dict[str, Any], default_segment_id: str = "") -> dict[str, Any]:
    title = str(item.get("title") or "").strip()
    hook = str(item.get("hook") or "").strip()
    if not title or not hook:
        raise AppError(HTTPStatus.BAD_GATEWAY, "ai_validation_failed", "AI candidate response is missing title or hook.")
    risk = validate_risk_level(str(item.get("riskLevel") or "medium"))
    try:
        candidate_type = validate_candidate_type(str(item.get("candidateType") or "mixed"))
    except AppError:
        candidate_type = "mixed"
    if candidate_type not in CANDIDATE_ALLOWED_TYPES:
        candidate_type = "mixed"
    reasoning = str(item.get("aiReasoningSummary") or "").strip()
    if len(reasoning.split()) > 60:
        reasoning = "Candidate dipilih karena relevan dengan sumber dan perlu ditinjau manual sebelum dipakai."
    candidate = {
        "candidateId": candidate_id(),
        "sourceId": source["sourceId"],
        "transcriptId": transcript.get("transcriptId", ""),
        "segmentId": str(item.get("segmentId") or default_segment_id or "").strip(),
        "candidateType": candidate_type,
        "title": title[:140],
        "hook": hook[:240],
        "angle": str(item.get("angle") or "").strip()[:500],
        "summary": str(item.get("summary") or "").strip()[:800],
        "suggestedFormat": str(item.get("suggestedFormat") or candidate_type).strip(),
        "suggestedDurationSeconds": parse_int(item.get("suggestedDurationSeconds"), 45, "suggestedDurationSeconds"),
        "riskLevel": risk,
        "needsContext": parse_bool(item.get("needsContext"), risk != "low"),
        "contextWarning": str(item.get("contextWarning") or "").strip()[:500],
        "sourceCreditSuggestion": str(item.get("sourceCreditSuggestion") or source.get("creditText") or "").strip(),
        "candidateStatus": "suggested",
        "aiReasoningSummary": reasoning[:500],
        "contentLinks": [],
        "rejectionReason": "",
        "createdAt": now_iso(),
        "updatedAt": now_iso(),
    }
    if candidate["riskLevel"] in {"medium", "high"} and not candidate["contextWarning"]:
        candidate["contextWarning"] = "Review konteks sumber/segment secara manual sebelum dipakai."
    return candidate
