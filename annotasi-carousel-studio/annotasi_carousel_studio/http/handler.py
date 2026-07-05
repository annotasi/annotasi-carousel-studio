from __future__ import annotations

from ..common import *
from ..config import *
from ..errors import *
from ..http.responses import *
from ..storage.content_store import STORE
from ..storage.source_store import SOURCE_STORE
from ..utils.text import parse_int
from ..utils.time import local_today
from ..content.service import *
from ..render.png_renderer import *
from ..render.video_renderer import *
from ..render.audio_mixer import *
from ..source.service import *
from ..source.transcript import *
from ..source.formatter import *
from ..candidate.service import *
from ..candidate.formatter import *
from ..package.service import *

class AnnotasiHandler(BaseHTTPRequestHandler):
    server_version = "AnnotasiCarouselStudio/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        LOGGER.info("http_client %s", format % args)

    def do_GET(self) -> None:
        try:
            self.handle_get()
        except AppError as exc:
            json_response(self, exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except Exception:
            LOGGER.exception("unhandled_error")
            json_response(
                self,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": {"code": "internal_error", "message": "Unexpected server error."}},
            )

    def do_POST(self) -> None:
        try:
            self.handle_post()
        except AppError as exc:
            LOGGER.warning("request_failed code=%s message=%s", exc.code, exc.message)
            json_response(self, exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except Exception:
            LOGGER.exception("unhandled_error")
            json_response(
                self,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": {"code": "internal_error", "message": "Unexpected server error."}},
            )

    def do_PATCH(self) -> None:
        try:
            self.handle_patch()
        except AppError as exc:
            LOGGER.warning("request_failed code=%s message=%s", exc.code, exc.message)
            json_response(self, exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except Exception:
            LOGGER.exception("unhandled_error")
            json_response(
                self,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": {"code": "internal_error", "message": "Unexpected server error."}},
            )

    def do_DELETE(self) -> None:
        try:
            self.handle_delete()
        except AppError as exc:
            LOGGER.warning("request_failed code=%s message=%s", exc.code, exc.message)
            json_response(self, exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except Exception:
            LOGGER.exception("unhandled_error")
            json_response(
                self,
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": {"code": "internal_error", "message": "Unexpected server error."}},
            )

    def handle_get(self) -> None:
        parsed_url = urlparse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")
        params = urlparse.parse_qs(parsed_url.query)
        if path == "/health":
            json_response(self, HTTPStatus.OK, {"status": "ok", "service": "annotasi-carousel-studio"})
            return

        if path == "/api/v1/calendar":
            json_response(self, HTTPStatus.OK, query_calendar(params))
            return

        calendar_shortcut_match = re.fullmatch(r"/api/v1/calendar/(today|week|month|next)", path)
        if calendar_shortcut_match:
            mode = calendar_shortcut_match.group(1)
            today = local_today()
            if mode == "today":
                query = {"from": [today.isoformat()], "to": [today.isoformat()]}
                body = query_calendar(query)
                body["telegramMessages"] = format_calendar_for_telegram(
                    [STORE.get(str(item["id"])) for item in body["items"]],
                    f"Today's Content Plan\n\n{today.isoformat()}",
                    "No content scheduled for today.",
                )
                json_response(self, HTTPStatus.OK, body)
                return
            if mode == "week":
                json_response(self, HTTPStatus.OK, query_calendar({"from": [today.isoformat()], "to": [(today + timedelta(days=6)).isoformat()]}))
                return
            if mode == "month":
                month_start = today.replace(day=1)
                next_month = (month_start.replace(day=28) + timedelta(days=4)).replace(day=1)
                month_end = next_month - timedelta(days=1)
                json_response(self, HTTPStatus.OK, query_calendar({"from": [month_start.isoformat()], "to": [month_end.isoformat()]}))
                return
            items = calendar_items(today, today + timedelta(days=365))
            next_item = items[:1]
            json_response(
                self,
                HTTPStatus.OK,
                {
                    "items": [workflow_summary(item) for item in next_item],
                    "telegramMessages": format_calendar_for_telegram(next_item, "Next Scheduled Content", "No scheduled content found."),
                },
            )
            return

        if path == "/api/v1/content-list":
            status = params.get("status", [""])[0].strip()
            limit = parse_int(params.get("limit", ["20"])[0], 20, "limit")
            limit = max(1, min(limit, 100))
            json_response(self, HTTPStatus.OK, list_content_by_status(status, limit))
            return

        if path == "/api/v1/sources":
            json_response(self, HTTPStatus.OK, list_sources(params))
            return

        if path == "/api/v1/candidate-list":
            status = params.get("status", [""])[0].strip()
            limit = parse_int(params.get("limit", ["20"])[0], 20, "limit")
            json_response(self, HTTPStatus.OK, list_candidates_by_status(status, limit))
            return

        package_detail_match = re.fullmatch(r"/api/v1/packages/(pkg_\d{8}_[a-f0-9]{8})", path)
        if package_detail_match:
            json_response(self, HTTPStatus.OK, package_by_id(package_detail_match.group(1)))
            return

        candidate_detail_match = re.fullmatch(r"/api/v1/candidates/(cand_\d{8}_[a-f0-9]{8})", path)
        if candidate_detail_match:
            source, candidate = find_candidate(candidate_detail_match.group(1))
            json_response(self, HTTPStatus.OK, {**candidate, "source": source_summary(source), "telegramMessages": format_candidate_detail_for_telegram(source, candidate)})
            return

        source_review_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/review", path)
        if source_review_match:
            source = SOURCE_STORE.get(source_review_match.group(1))
            json_response(self, HTTPStatus.OK, {**source, "telegramMessages": format_source_review_for_telegram(source)})
            return

        source_candidates_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/candidates", path)
        if source_candidates_match:
            status = params.get("status", [""])[0].strip()
            json_response(self, HTTPStatus.OK, list_candidates_for_source(source_candidates_match.group(1), status))
            return

        source_transcript_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/transcript", path)
        if source_transcript_match:
            source = SOURCE_STORE.get(source_transcript_match.group(1))
            if not isinstance(source.get("transcript"), dict):
                raise AppError(HTTPStatus.NOT_FOUND, "transcript_not_found", "Transcript was not found.")
            json_response(self, HTTPStatus.OK, {**source["transcript"], "telegramMessages": format_transcript_summary_for_telegram(source)})
            return

        source_segments_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/segments", path)
        if source_segments_match:
            source = SOURCE_STORE.get(source_segments_match.group(1))
            transcript = source.get("transcript") if isinstance(source.get("transcript"), dict) else {}
            segments = transcript.get("segments") if isinstance(transcript.get("segments"), list) else []
            json_response(self, HTTPStatus.OK, {"sourceId": source.get("sourceId"), "segments": segments, "telegramMessages": format_segments_for_telegram(source)})
            return

        source_detail_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})", path)
        if source_detail_match:
            source = SOURCE_STORE.get(source_detail_match.group(1))
            json_response(self, HTTPStatus.OK, {**source, "summary": source_summary(source), "telegramMessages": format_source_detail_for_telegram(source)})
            return

        segment_detail_match = re.fullmatch(r"/api/v1/segments/(seg_\d{8}_[a-f0-9]{8})", path)
        if segment_detail_match:
            source, transcript, segment = SOURCE_STORE.find_segment(segment_detail_match.group(1))
            json_response(self, HTTPStatus.OK, {**segment, "sourceId": source.get("sourceId"), "transcriptId": transcript.get("transcriptId"), "telegramMessages": format_segment_detail_for_telegram(source, segment)})
            return

        render_match = re.fullmatch(r"/api/v1/render/(rnd_\d{8}_[a-f0-9]{8})", path)
        if render_match:
            render = STORE.find_render(render_match.group(1))
            json_response(self, HTTPStatus.OK, normalize_render_result(render))
            return

        video_render_match = re.fullmatch(r"/api/v1/video-render/(vid_\d{8}_[a-f0-9]{8})", path)
        if video_render_match:
            video_render = STORE.find_video_render(video_render_match.group(1))
            json_response(self, HTTPStatus.OK, normalize_video_result(video_render))
            return

        audio_render_match = re.fullmatch(r"/api/v1/audio-render/(aud_\d{8}_[a-f0-9]{8})", path)
        if audio_render_match:
            audio_render = STORE.find_audio_render(audio_render_match.group(1))
            json_response(self, HTTPStatus.OK, normalize_audio_result(audio_render))
            return

        latest_audio_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/audio/latest", path)
        if latest_audio_match:
            record = STORE.get(latest_audio_match.group(1))
            audio_render = record.get("latestAudioRender")
            if not isinstance(audio_render, dict):
                raise AppError(HTTPStatus.NOT_FOUND, "audio_render_not_found", "No audio render exists for this content.")
            json_response(self, HTTPStatus.OK, normalize_audio_result(audio_render))
            return

        latest_video_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/render/video", path)
        if latest_video_match:
            record = STORE.get(latest_video_match.group(1))
            video_render = record.get("latestVideoRender")
            if not isinstance(video_render, dict):
                raise AppError(HTTPStatus.NOT_FOUND, "video_render_not_found", "No video render exists for this content.")
            json_response(self, HTTPStatus.OK, normalize_video_result(video_render))
            return

        png_render_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/render/png", path)
        if png_render_match:
            record = STORE.get(png_render_match.group(1))
            render = record.get("latestRender")
            if not isinstance(render, dict):
                raise AppError(HTTPStatus.NOT_FOUND, "render_not_found", "No PNG render exists for this content.")
            json_response(self, HTTPStatus.OK, normalize_render_result(render))
            return

        review_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/review", path)
        if review_match:
            json_response(self, HTTPStatus.OK, get_review(review_match.group(1)))
            return

        status_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/status", path)
        if status_match:
            json_response(self, HTTPStatus.OK, get_content_status(status_match.group(1)))
            return

        content_source_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/source", path)
        if content_source_match:
            json_response(self, HTTPStatus.OK, source_for_content(content_source_match.group(1)))
            return

        content_candidate_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/candidate", path)
        if content_candidate_match:
            json_response(self, HTTPStatus.OK, candidate_for_content(content_candidate_match.group(1)))
            return

        package_latest_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/package/latest", path)
        if package_latest_match:
            json_response(self, HTTPStatus.OK, latest_package_status(package_latest_match.group(1)))
            return

        packages_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/packages", path)
        if packages_match:
            json_response(self, HTTPStatus.OK, list_packages_for_content(packages_match.group(1)))
            return

        ready_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/ready-to-post", path)
        if ready_match:
            json_response(self, HTTPStatus.OK, ready_to_post_check(ready_match.group(1)))
            return

        checklist_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/posting-checklist", path)
        if checklist_match:
            json_response(self, HTTPStatus.OK, posting_checklist_for_content(checklist_match.group(1)))
            return

        match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})(?:/(caption|voiceover|voiceover-script))?", path)
        if not match:
            raise AppError(HTTPStatus.NOT_FOUND, "not_found", "Route not found.")

        item_id, view = match.groups()
        record = STORE.get(item_id)
        if view == "caption":
            body = {
                "id": item_id,
                "caption": record["content"]["caption"],
                "hashtags": record["content"]["hashtags"],
                "telegramMessages": format_caption_for_telegram(record),
            }
        elif view in {"voiceover", "voiceover-script"}:
            body = {
                "id": item_id,
                "voiceoverScript": record["content"]["voiceoverScript"],
                "telegramMessages": format_voiceover_for_telegram(record),
            }
        else:
            body = {**record, "telegramMessages": format_full_for_telegram(record, include_voiceover=True)}
        json_response(self, HTTPStatus.OK, body)

    def handle_post(self) -> None:
        path = urlparse.urlparse(self.path).path.rstrip("/")
        body = read_json_body(self)
        if path == "/api/v1/sources":
            json_response(self, HTTPStatus.OK, create_source(body))
            return
        source_highlights_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/highlights", path)
        if source_highlights_match:
            json_response(self, HTTPStatus.OK, generate_highlights_from_source(source_highlights_match.group(1), body))
            return
        segment_highlights_match = re.fullmatch(r"/api/v1/segments/(seg_\d{8}_[a-f0-9]{8})/highlights", path)
        if segment_highlights_match:
            json_response(self, HTTPStatus.OK, generate_highlights_from_segment(segment_highlights_match.group(1), body))
            return
        candidate_approve_match = re.fullmatch(r"/api/v1/candidates/(cand_\d{8}_[a-f0-9]{8})/approve", path)
        if candidate_approve_match:
            json_response(self, HTTPStatus.OK, approve_candidate(candidate_approve_match.group(1)))
            return
        candidate_reject_match = re.fullmatch(r"/api/v1/candidates/(cand_\d{8}_[a-f0-9]{8})/reject", path)
        if candidate_reject_match:
            json_response(self, HTTPStatus.OK, reject_candidate(candidate_reject_match.group(1), body))
            return
        candidate_generate_match = re.fullmatch(r"/api/v1/candidates/(cand_\d{8}_[a-f0-9]{8})/generate-content", path)
        if candidate_generate_match:
            json_response(self, HTTPStatus.OK, generate_content_from_candidate(candidate_generate_match.group(1), body))
            return
        source_approve_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/approve", path)
        if source_approve_match:
            json_response(self, HTTPStatus.OK, approve_source(source_approve_match.group(1)))
            return
        source_restrict_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/restrict", path)
        if source_restrict_match:
            json_response(self, HTTPStatus.OK, restrict_source(source_restrict_match.group(1), body))
            return
        source_credit_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/credit", path)
        if source_credit_match:
            json_response(self, HTTPStatus.OK, set_source_credit(source_credit_match.group(1), body))
            return
        source_transcript_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/transcript", path)
        if source_transcript_match:
            json_response(self, HTTPStatus.OK, add_transcript(source_transcript_match.group(1), body))
            return
        source_segments_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/segments/generate", path)
        if source_segments_match:
            json_response(self, HTTPStatus.OK, generate_segments(source_segments_match.group(1)))
            return
        source_ideas_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/ideas", path)
        if source_ideas_match:
            json_response(self, HTTPStatus.OK, ideas_from_source(source_ideas_match.group(1)))
            return
        source_generate_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})/generate-content", path)
        if source_generate_match:
            json_response(self, HTTPStatus.OK, generate_content_from_source(source_generate_match.group(1), body))
            return
        segment_generate_match = re.fullmatch(r"/api/v1/segments/(seg_\d{8}_[a-f0-9]{8})/generate-content", path)
        if segment_generate_match:
            json_response(self, HTTPStatus.OK, generate_content_from_segment(segment_generate_match.group(1), body))
            return
        approve_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/approve", path)
        if approve_match:
            json_response(self, HTTPStatus.OK, approve_content(approve_match.group(1), body))
            return
        reject_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/reject", path)
        if reject_match:
            json_response(self, HTTPStatus.OK, reject_content(reject_match.group(1), body))
            return
        schedule_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/schedule", path)
        if schedule_match:
            json_response(self, HTTPStatus.OK, schedule_content(schedule_match.group(1), body))
            return
        uploaded_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/uploaded", path)
        if uploaded_match:
            json_response(self, HTTPStatus.OK, mark_uploaded(uploaded_match.group(1), body))
            return
        package_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/package", path)
        if package_match:
            json_response(self, HTTPStatus.OK, generate_content_package(package_match.group(1), body))
            return
        audio_prepare_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/audio/prepare", path)
        if audio_prepare_match:
            json_response(self, HTTPStatus.OK, prepare_audio_session(audio_prepare_match.group(1)))
            return
        audio_mix_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/audio/mix", path)
        if audio_mix_match:
            json_response(self, HTTPStatus.OK, render_content_audio_mix(audio_mix_match.group(1), body))
            return
        video_render_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/render/video", path)
        if video_render_match:
            json_response(self, HTTPStatus.OK, render_content_video(video_render_match.group(1), body))
            return
        png_render_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/render/png", path)
        if png_render_match:
            json_response(self, HTTPStatus.OK, render_content_png(png_render_match.group(1), body))
            return
        if path == "/api/v1/content/carousel":
            json_response(self, HTTPStatus.OK, generate_content(body, "annotasi_hikmah"))
            return
        if path == "/api/v1/content/hikmah":
            body.setdefault("niche", "annotasi_hikmah")
            body.setdefault("tone", "calm_reflective")
            json_response(self, HTTPStatus.OK, generate_content(body, "annotasi_hikmah"))
            return
        if path == "/api/v1/content/ideas":
            json_response(self, HTTPStatus.OK, generate_ideas(body))
            return
        raise AppError(HTTPStatus.NOT_FOUND, "not_found", "Route not found.")

    def handle_patch(self) -> None:
        path = urlparse.urlparse(self.path).path.rstrip("/")
        body = read_json_body(self)
        source_match = re.fullmatch(r"/api/v1/sources/(src_\d{8}_[a-f0-9]{8})", path)
        if source_match:
            json_response(self, HTTPStatus.OK, update_source(source_match.group(1), body))
            return
        segment_match = re.fullmatch(r"/api/v1/segments/(seg_\d{8}_[a-f0-9]{8})", path)
        if segment_match:
            json_response(self, HTTPStatus.OK, update_segment(segment_match.group(1), body))
            return
        slide_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/slides/(\d+)", path)
        if slide_match:
            json_response(self, HTTPStatus.OK, edit_slide(slide_match.group(1), int(slide_match.group(2)), body))
            return
        caption_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/caption", path)
        if caption_match:
            json_response(self, HTTPStatus.OK, edit_caption(caption_match.group(1), body))
            return
        voiceover_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/voiceover", path)
        if voiceover_match:
            json_response(self, HTTPStatus.OK, edit_voiceover(voiceover_match.group(1), body))
            return
        status_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/status", path)
        if status_match:
            json_response(self, HTTPStatus.OK, update_content_status(status_match.group(1), body))
            return
        raise AppError(HTTPStatus.NOT_FOUND, "not_found", "Route not found.")

    def handle_delete(self) -> None:
        path = urlparse.urlparse(self.path).path.rstrip("/")
        schedule_match = re.fullmatch(r"/api/v1/content/(cnt_\d{8}_[a-f0-9]{8})/schedule", path)
        if schedule_match:
            json_response(self, HTTPStatus.OK, unschedule_content(schedule_match.group(1)))
            return
        raise AppError(HTTPStatus.NOT_FOUND, "not_found", "Route not found.")
