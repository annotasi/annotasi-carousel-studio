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
def system_prompt() -> str:
    return """You create internal content packages for Annotasi Carousel Studio.

Language and style:
- Use Bahasa Indonesia.
- Calm, reflective, practical, and not clickbait.
- Suitable for Muslim workers and professionals.
- Keep carousel slide text short and readable.

Dakwah safety:
- Do not invent Quran verses.
- Do not invent hadith.
- Do not attribute statements to UAS, UAH, or any ustadz unless a source is provided.
- Do not imitate or clone any ustadz voice.
- Do not produce controversial fatwa-style answers.
- Use phrases like pengingat, hikmah, renungan, or catatan.
- If no source is provided, avoid Quran/hadith references and use general reminders.
- Include this exact reminder in safetyNotes: Review kembali sebelum upload agar tidak salah konteks.

Return JSON only. Do not wrap it in markdown."""


def carousel_user_prompt(
    *,
    topic: str,
    niche: str,
    tone: str,
    slide_count: int,
    platform: str,
    source_context: str,
) -> str:
    source_rule = (
        "A source/transcript was provided. Include a source credit suggestion and warn that context must be reviewed."
        if source_context
        else "No source was provided. Do not invent Quran, hadith, speaker, book, or kajian references."
    )
    return f"""Create one content package.

Topic: {topic}
Niche: {niche}
Tone: {tone}
Platform: {platform}
Slide count: {slide_count}
Source rule: {source_rule}
Source/context, if any:
{source_context or "-"}

JSON schema:
{{
  "title": "string",
  "niche": "string",
  "tone": "string",
  "slides": [
    {{
      "slideNumber": 1,
      "type": "hook|body|closing",
      "text": "string",
      "visualDirection": "string"
    }}
  ],
  "caption": "string",
  "hashtags": ["string"],
  "voiceoverScript": "string",
  "videoStoryboard": [
    {{
      "sceneNumber": 1,
      "durationSeconds": 5,
      "visual": "string",
      "motion": "string",
      "voiceoverPart": "string"
    }}
  ],
  "safetyNotes": ["string"],
  "sourceCreditSuggestion": "string",
  "callToAction": "string"
}}

Rules:
- slides must contain 5 to 8 slides; prefer exactly {slide_count}.
- each slide text must be 25 words or fewer.
- use hook for slide 1, closing for the final slide, and body for the middle slides.
- hashtags should be relevant and not excessive.
- voiceover should fit roughly 30 to 60 seconds.
- videoStoryboard should map naturally to the slides.
- sourceCreditSuggestion should be a placeholder if no source was provided."""


def ideas_user_prompt(niche: str) -> str:
    return f"""Generate 10 content ideas for this niche: {niche}

Return JSON only:
{{
  "niche": "string",
  "ideas": [
    {{
      "title": "string",
      "angle": "string",
      "sampleHook": "string"
    }}
  ],
  "safetyNotes": ["string"]
}}

Use Bahasa Indonesia, calm wording, and the same dakwah safety rules."""


def ideas_from_source_prompt(source: dict[str, Any], transcript_text: str) -> str:
    return f"""Generate 10 safe content ideas from this source.

Source:
- sourceId: {source.get("sourceId")}
- title: {source.get("title")}
- speakerName: {source.get("speakerName")}
- platform: {source.get("platform")}
- sourceUrl: {source.get("sourceUrl")}
- permissionStatus: {source.get("permissionStatus")}
- creditText: {source.get("creditText")}
- contextNotes: {source.get("contextNotes")}

Transcript/context excerpt:
{transcript_text[:6000] or "-"}

Rules:
- Bahasa Indonesia.
- Do not invent Quran verses.
- Do not invent hadith.
- Do not produce fatwa-style conclusions.
- Do not add speaker attribution beyond the source metadata.
- Prefer pengingat, hikmah, renungan, or catatan framing.
- For each idea, mark riskLevel low, medium, or high.
- Mark needsContext true if the idea needs previous/next context.
- sourceCreditRequired should be true unless this is own_content/internal note.

Return JSON only:
{{
  "sourceId": "string",
  "ideas": [
    {{
      "title": "string",
      "angle": "string",
      "suggestedTopic": "string",
      "riskLevel": "low|medium|high",
      "needsContext": true,
      "sourceCreditRequired": true,
      "notes": "string"
    }}
  ],
  "safetyNotes": ["string"]
}}"""


def source_content_prompt(source: dict[str, Any], transcript_text: str, topic: str, segment: Optional[dict[str, Any]] = None) -> str:
    segment_context = ""
    if segment:
        segment_context = f"""
Segment:
- segmentId: {segment.get("segmentId")}
- riskLevel: {segment.get("riskLevel")}
- contextNotes: {segment.get("contextNotes")}
- text: {segment.get("text")}
"""
    return f"""Create one Annotasi Hikmah carousel package from the source context.

Requested topic: {topic or source.get("topic") or source.get("title")}

Source:
- sourceId: {source.get("sourceId")}
- sourceTitle: {source.get("title")}
- speakerName: {source.get("speakerName")}
- sourceUrl: {source.get("sourceUrl")}
- creditText: {source.get("creditText")}
- permissionStatus: {source.get("permissionStatus")}
- sourceStatus: {source.get("sourceStatus")}
- contextNotes: {source.get("contextNotes")}
{segment_context}

Transcript/context:
{transcript_text[:7000] or "-"}

Rules:
- Bahasa Indonesia.
- Do not invent Quran verses.
- Do not invent hadith.
- Do not make fatwa-style conclusions.
- Do not attribute any claim to the speaker unless it is supported by the source context.
- If context is partial, add manual review warning in safetyNotes.
- Always include a source credit suggestion.
- Keep tone calm, reflective, respectful, not clickbait.
- Default to 7 slides, each slide short and readable.

Return JSON only using this schema:
{{
  "title": "string",
  "niche": "string",
  "tone": "string",
  "source": {{
    "sourceId": "string",
    "sourceTitle": "string",
    "speakerName": "string",
    "sourceUrl": "string",
    "creditText": "string",
    "permissionStatus": "string",
    "segmentId": "string|null",
    "riskLevel": "low|medium|high"
  }},
  "slides": [
    {{
      "slideNumber": 1,
      "type": "hook|body|closing",
      "text": "string",
      "visualDirection": "string"
    }}
  ],
  "caption": "string",
  "hashtags": ["string"],
  "voiceoverScript": "string",
  "videoStoryboard": [
    {{
      "sceneNumber": 1,
      "durationSeconds": 5,
      "visual": "string",
      "motion": "string",
      "voiceoverPart": "string"
    }}
  ],
  "safetyNotes": ["string"],
  "sourceCreditSuggestion": "string",
  "callToAction": "string"
}}"""


def highlight_candidates_prompt(
    source: dict[str, Any],
    transcript: dict[str, Any],
    context_text: str,
    *,
    candidate_count: int,
    preferred_types: list[str],
    segment: Optional[dict[str, Any]] = None,
) -> str:
    segment_context = ""
    if segment:
        segment_context = f"""
Focus segment:
- segmentId: {segment.get("segmentId")}
- riskLevel: {segment.get("riskLevel")}
- contextNotes: {segment.get("contextNotes")}
- text: {segment.get("text")}
"""
    return f"""Analyze this source transcript and suggest safe content candidates.

Source:
- sourceId: {source.get("sourceId")}
- title: {source.get("title")}
- speakerName: {source.get("speakerName")}
- sourceUrl: {source.get("sourceUrl")}
- platform: {source.get("platform")}
- permissionStatus: {source.get("permissionStatus")}
- creditText: {source.get("creditText")}

Transcript:
- transcriptId: {transcript.get("transcriptId")}
{segment_context}

Context text:
{context_text[:CANDIDATE_MAX_TRANSCRIPT_CHARS]}

Candidate count: {candidate_count}
Preferred types: {", ".join(preferred_types)}

Safety rules:
- Bahasa Indonesia.
- Do not invent Quran verses.
- Do not invent hadith.
- Do not create fatwa-style conclusions.
- Do not attribute anything to a speaker unless it exists in source metadata/transcript.
- Do not exaggerate or clickbait.
- Do not cut meaning out of context.
- For medium/high risk candidates, include contextWarning.
- aiReasoningSummary must be short and user-safe; do not include hidden chain-of-thought.
- Prefer hikmah, renungan, catatan, or pengingat framing.

Return JSON only:
{{
  "sourceId": "string",
  "transcriptId": "string",
  "analysisSummary": "string",
  "candidates": [
    {{
      "candidateType": "carousel|short_video|voiceover_reflection|quote_post|mixed",
      "segmentId": "string|null",
      "title": "string",
      "hook": "string",
      "angle": "string",
      "summary": "string",
      "suggestedFormat": "string",
      "suggestedDurationSeconds": 45,
      "riskLevel": "low|medium|high",
      "needsContext": true,
      "contextWarning": "string",
      "sourceCreditSuggestion": "string",
      "aiReasoningSummary": "string"
    }}
  ],
  "safetyNotes": ["string"]
}}"""


def candidate_content_prompt(source: dict[str, Any], transcript: dict[str, Any], candidate: dict[str, Any], segment: Optional[dict[str, Any]]) -> str:
    segment_text = str(segment.get("text") or "") if segment else ""
    transcript_excerpt = str(transcript.get("transcriptText") or "")[:5000]
    return f"""Generate one Annotasi Hikmah carousel package from this approved content candidate.

Candidate:
- candidateId: {candidate.get("candidateId")}
- type: {candidate.get("candidateType")}
- title: {candidate.get("title")}
- hook: {candidate.get("hook")}
- angle: {candidate.get("angle")}
- summary: {candidate.get("summary")}
- riskLevel: {candidate.get("riskLevel")}
- needsContext: {candidate.get("needsContext")}
- contextWarning: {candidate.get("contextWarning")}

Source:
- sourceId: {source.get("sourceId")}
- sourceTitle: {source.get("title")}
- speakerName: {source.get("speakerName")}
- sourceUrl: {source.get("sourceUrl")}
- creditText: {source.get("creditText")}
- permissionStatus: {source.get("permissionStatus")}
- segmentId: {candidate.get("segmentId") or ""}

Segment/context:
{segment_text or transcript_excerpt}

Rules:
- Bahasa Indonesia.
- Do not invent Quran verses.
- Do not invent hadith.
- Do not make fatwa-style conclusions.
- Do not add claims beyond the source context.
- Keep calm, reflective, respectful, not clickbait.
- Include source credit suggestion.
- Content status will be needs_review; do not auto-approve.

Return JSON only using this schema:
{{
  "title": "string",
  "niche": "string",
  "tone": "string",
  "source": {{
    "sourceId": "string",
    "sourceTitle": "string",
    "speakerName": "string",
    "sourceUrl": "string",
    "creditText": "string",
    "permissionStatus": "string",
    "segmentId": "string|null",
    "candidateId": "string",
    "riskLevel": "low|medium|high"
  }},
  "slides": [
    {{
      "slideNumber": 1,
      "type": "hook|body|closing",
      "text": "string",
      "visualDirection": "string"
    }}
  ],
  "caption": "string",
  "hashtags": ["string"],
  "voiceoverScript": "string",
  "videoStoryboard": [
    {{
      "sceneNumber": 1,
      "durationSeconds": 5,
      "visual": "string",
      "motion": "string",
      "voiceoverPart": "string"
    }}
  ],
  "safetyNotes": ["string"],
  "sourceCreditSuggestion": "string",
  "callToAction": "string"
}}"""
