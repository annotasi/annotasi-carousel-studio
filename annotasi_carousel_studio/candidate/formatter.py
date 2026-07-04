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
def format_candidates_for_telegram(source: dict[str, Any], candidates: list[dict[str, Any]]) -> list[str]:
    if not candidates:
        return [f"Candidate List\n\nSource:\n{source.get('sourceId')}\n\nNo candidates found."]
    lines = ["Candidate List", "", "Source:", str(source.get("sourceId")), ""]
    for index, candidate in enumerate(candidates, start=1):
        lines.extend(
            [
                f"{index}. {candidate.get('candidateId')} - {candidate.get('title')}",
                f"Type: {candidate.get('candidateType')}",
                f"Risk: {candidate.get('riskLevel')}",
                f"Status: {candidate.get('candidateStatus')}",
                "",
            ]
        )
    return split_telegram_message("\n".join(lines).strip())


def format_candidate_detail_for_telegram(source: dict[str, Any], candidate: dict[str, Any]) -> list[str]:
    lines = [
        "Candidate Detail",
        "",
        "Candidate ID:",
        str(candidate.get("candidateId")),
        "",
        "Source:",
        f"{source.get('sourceId')} - {source.get('title')}",
        "",
        "Segment:",
        str(candidate.get("segmentId") or "none"),
        "",
        "Type:",
        str(candidate.get("candidateType")),
        "",
        "Title:",
        str(candidate.get("title")),
        "",
        "Hook:",
        str(candidate.get("hook")),
        "",
        "Angle:",
        str(candidate.get("angle")),
        "",
        "Risk:",
        str(candidate.get("riskLevel")),
        "",
        "Needs context:",
        "yes" if candidate.get("needsContext") else "no",
        "",
        "Context warning:",
        str(candidate.get("contextWarning") or "-"),
        "",
        "Source credit:",
        str(candidate.get("sourceCreditSuggestion") or source.get("creditText") or "-"),
        "",
        "Status:",
        str(candidate.get("candidateStatus")),
        "",
        "Next actions:",
        f"/candidate_approve {candidate.get('candidateId')}",
        f"/candidate_reject {candidate.get('candidateId')} <reason>",
        f"/generate_from_candidate {candidate.get('candidateId')}",
    ]
    return split_telegram_message("\n".join(lines).strip())
