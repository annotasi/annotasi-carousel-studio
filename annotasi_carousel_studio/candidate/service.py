"""Candidate service compatibility exports."""

from ..main import (
    approve_candidate,
    candidate_context_from_source,
    candidate_counts,
    candidate_for_content,
    candidate_permission_warnings,
    find_candidate,
    generate_content_from_candidate,
    generate_highlights_from_segment,
    generate_highlights_from_source,
    list_candidates_by_status,
    list_candidates_for_source,
    normalized_title,
    reject_candidate,
    save_candidates,
    source_candidates,
    validate_candidate_status,
    validate_candidate_type,
)

__all__ = [
    "approve_candidate",
    "candidate_context_from_source",
    "candidate_counts",
    "candidate_for_content",
    "candidate_permission_warnings",
    "find_candidate",
    "generate_content_from_candidate",
    "generate_highlights_from_segment",
    "generate_highlights_from_source",
    "list_candidates_by_status",
    "list_candidates_for_source",
    "normalized_title",
    "reject_candidate",
    "save_candidates",
    "source_candidates",
    "validate_candidate_status",
    "validate_candidate_type",
]

