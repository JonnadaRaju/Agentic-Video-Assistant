from __future__ import annotations

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import AudioRecording, User, VideoRecording
from app.schemas.agent import AgentStep
from app.services.ai_service import (
    AIServiceError,
    answer_question,
    answer_question_with_groq,
    build_context_chunks,
    build_unified_context_chunks,
    build_video_context_chunks,
    semantic_search_recordings,
    semantic_search_videos,
    summarize_and_store_video,
    summarize_text,
    transcribe_and_store_recording,
    transcribe_and_store_video,
)
from app.services.recording_service import get_recording, get_recordings
from app.services.video_service import get_video, get_videos


def _summary_intent(query: str) -> bool:
    normalized = query.lower()
    return "summarize" in normalized or "summary" in normalized


def _latest_intent(query: str) -> bool:
    normalized = query.lower()
    return any(token in normalized for token in ("latest", "last", "recent"))


def _search_intent(query: str) -> bool:
    normalized = query.lower()
    return any(token in normalized for token in ("find", "search", "mention", "show"))


def _video_intent(query: str) -> bool:
    normalized = query.lower()
    return "video" in normalized or "videos" in normalized


def _audio_intent(query: str) -> bool:
    normalized = query.lower()
    return any(token in normalized for token in ("audio", "recording", "recordings"))


def _append_step(
    steps: list[AgentStep],
    *,
    tool: str,
    input_payload: dict,
    output_preview: str,
) -> None:
    steps.append(
        AgentStep(
            step=str(len(steps) + 1),
            tool=tool,
            input=input_payload,
            output_preview=output_preview,
        )
    )


def _format_media_line(kind: str, obj_id: int, filename: str, created_at: datetime) -> str:
    return f"- [{kind}] #{obj_id} {filename} ({created_at.isoformat()})"


async def _latest_audio_with_steps(
    db: AsyncSession,
    user_id: int,
    steps: list[AgentStep],
) -> AudioRecording | None:
    recordings = await get_recordings(db, user_id)
    _append_step(
        steps,
        tool="list_recordings",
        input_payload={"user_id": user_id},
        output_preview=f"Found {len(recordings)} recordings",
    )
    return recordings[0] if recordings else None


async def _latest_video_with_steps(
    db: AsyncSession,
    user_id: int,
    steps: list[AgentStep],
) -> VideoRecording | None:
    videos = await get_videos(db, user_id)
    _append_step(
        steps,
        tool="list_videos",
        input_payload={"user_id": user_id},
        output_preview=f"Found {len(videos)} videos",
    )
    return videos[0] if videos else None


async def execute_agent_query(
    db: AsyncSession,
    user: User,
    query: str,
) -> tuple[str, list[AgentStep]]:
    steps: list[AgentStep] = []
    normalized = query.strip()
    if not normalized:
        raise AIServiceError("Query cannot be empty.")

    lowered = normalized.lower()
    wants_summary = _summary_intent(normalized)
    wants_video = _video_intent(normalized)
    wants_audio = _audio_intent(normalized)

    # Latest summary intent with explicit video target.
    if _latest_intent(normalized) and wants_summary and wants_video:
        latest_video = await _latest_video_with_steps(db, user.id, steps)
        if not latest_video:
            return "No videos found for your account.", steps

        if not latest_video.transcript:
            latest_video = await transcribe_and_store_video(db, latest_video)
            _append_step(
                steps,
                tool="transcribe_video",
                input_payload={"video_id": latest_video.id},
                output_preview=(latest_video.transcript or "")[:120],
            )

        latest_video = await summarize_and_store_video(db, latest_video)
        _append_step(
            steps,
            tool="summarize_video",
            input_payload={"video_id": latest_video.id},
            output_preview=(latest_video.summary or "")[:120],
        )
        return latest_video.summary or "", steps

    # Latest summary intent with explicit audio target.
    if _latest_intent(normalized) and wants_summary and wants_audio and not wants_video:
        latest_audio = await _latest_audio_with_steps(db, user.id, steps)
        if not latest_audio:
            return "No recordings found for your account.", steps

        if not latest_audio.transcript:
            latest_audio = await transcribe_and_store_recording(db, latest_audio)
            _append_step(
                steps,
                tool="transcribe_audio",
                input_payload={"recording_id": latest_audio.id},
                output_preview=(latest_audio.transcript or "")[:120],
            )

        summary = summarize_text(latest_audio.transcript or "")
        _append_step(
            steps,
            tool="summarize_audio",
            input_payload={"recording_id": latest_audio.id},
            output_preview=summary[:120],
        )
        return summary, steps

    # Latest summary intent without explicit media target: pick newest across audio+video.
    if _latest_intent(normalized) and wants_summary and not wants_video and not wants_audio:
        latest_audio = await _latest_audio_with_steps(db, user.id, steps)
        latest_video = await _latest_video_with_steps(db, user.id, steps)

        candidates: list[tuple[str, datetime, int]] = []
        if latest_audio:
            candidates.append(("audio", latest_audio.created_at, latest_audio.id))
        if latest_video:
            candidates.append(("video", latest_video.created_at, latest_video.id))

        if not candidates:
            return "No recordings or videos found for your account.", steps

        media_type, _, media_id = max(candidates, key=lambda item: item[1])
        if media_type == "video":
            video = await get_video(db, media_id, user.id)
            if not video:
                return "Latest video could not be loaded.", steps
            if not video.transcript:
                video = await transcribe_and_store_video(db, video)
                _append_step(
                    steps,
                    tool="transcribe_video",
                    input_payload={"video_id": video.id},
                    output_preview=(video.transcript or "")[:120],
                )
            video = await summarize_and_store_video(db, video)
            _append_step(
                steps,
                tool="summarize_video",
                input_payload={"video_id": video.id},
                output_preview=(video.summary or "")[:120],
            )
            return video.summary or "", steps

        audio = await get_recording(db, media_id, user.id)
        if not audio:
            return "Latest recording could not be loaded.", steps
        if not audio.transcript:
            audio = await transcribe_and_store_recording(db, audio)
            _append_step(
                steps,
                tool="transcribe_audio",
                input_payload={"recording_id": audio.id},
                output_preview=(audio.transcript or "")[:120],
            )
        summary = summarize_text(audio.transcript or "")
        _append_step(
            steps,
            tool="summarize_audio",
            input_payload={"recording_id": audio.id},
            output_preview=summary[:120],
        )
        return summary, steps

    # Show/list recent items.
    if "recent" in lowered or "list" in lowered or "show" in lowered:
        if wants_video and not wants_audio:
            videos = await get_videos(db, user.id)
            _append_step(
                steps,
                tool="list_videos",
                input_payload={"user_id": user.id},
                output_preview=f"Found {len(videos)} videos",
            )
            if not videos:
                return "No videos found for your account.", steps
            lines = [
                _format_media_line("video", v.id, v.filename, v.created_at)
                for v in videos[:8]
            ]
            return "Recent videos:\n" + "\n".join(lines), steps

        if wants_audio and not wants_video:
            recordings = await get_recordings(db, user.id)
            _append_step(
                steps,
                tool="list_recordings",
                input_payload={"user_id": user.id},
                output_preview=f"Found {len(recordings)} recordings",
            )
            if not recordings:
                return "No recordings found for your account.", steps
            lines = [
                _format_media_line("audio", r.id, r.filename, r.created_at)
                for r in recordings[:8]
            ]
            return "Recent recordings:\n" + "\n".join(lines), steps

        recordings = await get_recordings(db, user.id)
        videos = await get_videos(db, user.id)
        _append_step(
            steps,
            tool="list_recordings",
            input_payload={"user_id": user.id},
            output_preview=f"Found {len(recordings)} recordings",
        )
        _append_step(
            steps,
            tool="list_videos",
            input_payload={"user_id": user.id},
            output_preview=f"Found {len(videos)} videos",
        )

        combined = [
            ("audio", r.id, r.filename, r.created_at) for r in recordings
        ] + [
            ("video", v.id, v.filename, v.created_at) for v in videos
        ]
        combined.sort(key=lambda item: item[3], reverse=True)
        if not combined:
            return "No recordings or videos found for your account.", steps

        lines = [
            _format_media_line(kind, obj_id, filename, created_at)
            for kind, obj_id, filename, created_at in combined[:10]
        ]
        return "Recent media:\n" + "\n".join(lines), steps

    # Search intents.
    if _search_intent(normalized):
        if wants_video and not wants_audio:
            videos = await semantic_search_videos(db, user.id, normalized, limit=5)
            _append_step(
                steps,
                tool="search_videos",
                input_payload={"query": normalized, "limit": 5},
                output_preview=f"Matched {len(videos)} videos",
            )
            if not videos:
                return "I could not find any videos matching that query.", steps
            lines = [f"- [video] #{v.id} {v.filename}" for v in videos[:5]]
            return "Relevant videos:\n" + "\n".join(lines), steps

        if wants_audio and not wants_video:
            recordings = await semantic_search_recordings(db, user.id, normalized, limit=5)
            _append_step(
                steps,
                tool="search_recordings",
                input_payload={"query": normalized, "limit": 5},
                output_preview=f"Matched {len(recordings)} recordings",
            )
            if not recordings:
                return "I could not find any recordings matching that query.", steps
            lines = [f"- [audio] #{r.id} {r.filename}" for r in recordings[:5]]
            return "Relevant recordings:\n" + "\n".join(lines), steps

        recordings = await semantic_search_recordings(db, user.id, normalized, limit=3)
        videos = await semantic_search_videos(db, user.id, normalized, limit=3)
        _append_step(
            steps,
            tool="search_recordings",
            input_payload={"query": normalized, "limit": 3},
            output_preview=f"Matched {len(recordings)} recordings",
        )
        _append_step(
            steps,
            tool="search_videos",
            input_payload={"query": normalized, "limit": 3},
            output_preview=f"Matched {len(videos)} videos",
        )

        if not recordings and not videos:
            return "I could not find any audio or video items matching that query.", steps

        lines = [f"- [audio] #{r.id} {r.filename}" for r in recordings]
        lines.extend([f"- [video] #{v.id} {v.filename}" for v in videos])
        return "Relevant media:\n" + "\n".join(lines[:10]), steps

    # Grounded answer path.
    audio_matches = []
    video_matches = []

    if wants_video and not wants_audio:
        video_matches = await semantic_search_videos(db, user.id, normalized, limit=5)
        _append_step(
            steps,
            tool="search_videos",
            input_payload={"query": normalized, "limit": 5},
            output_preview=f"Matched {len(video_matches)} videos",
        )
    elif wants_audio and not wants_video:
        audio_matches = await semantic_search_recordings(db, user.id, normalized, limit=5)
        _append_step(
            steps,
            tool="search_recordings",
            input_payload={"query": normalized, "limit": 5},
            output_preview=f"Matched {len(audio_matches)} recordings",
        )
    else:
        audio_matches = await semantic_search_recordings(db, user.id, normalized, limit=3)
        video_matches = await semantic_search_videos(db, user.id, normalized, limit=3)
        _append_step(
            steps,
            tool="search_recordings",
            input_payload={"query": normalized, "limit": 3},
            output_preview=f"Matched {len(audio_matches)} recordings",
        )
        _append_step(
            steps,
            tool="search_videos",
            input_payload={"query": normalized, "limit": 3},
            output_preview=f"Matched {len(video_matches)} videos",
        )

    if wants_summary and video_matches and (wants_video or not audio_matches):
        top_video = video_matches[0]
        top_video = await summarize_and_store_video(db, top_video)
        _append_step(
            steps,
            tool="summarize_video",
            input_payload={"video_id": top_video.id},
            output_preview=(top_video.summary or "")[:120],
        )
        return top_video.summary or "", steps

    if wants_summary and audio_matches and not wants_video:
        top_audio = audio_matches[0]
        if not top_audio.transcript:
            top_audio = await transcribe_and_store_recording(db, top_audio)
            _append_step(
                steps,
                tool="transcribe_audio",
                input_payload={"recording_id": top_audio.id},
                output_preview=(top_audio.transcript or "")[:120],
            )
        summary = summarize_text(top_audio.transcript or "")
        _append_step(
            steps,
            tool="summarize_audio",
            input_payload={"recording_id": top_audio.id},
            output_preview=summary[:120],
        )
        return summary, steps

    context: list[str]
    if wants_video and not wants_audio:
        context = build_video_context_chunks(video_matches)
        if not context:
            return "I could not find enough transcript context in your videos.", steps
        answer = answer_question_with_groq(normalized, context)
        _append_step(
            steps,
            tool="answer_question_about_videos",
            input_payload={"question": normalized},
            output_preview=answer[:120],
        )
        return answer, steps

    if wants_audio and not wants_video:
        context = build_context_chunks(audio_matches)
        if not context:
            return "I could not find enough transcript context in your recordings.", steps
        answer = answer_question(normalized, context)
        _append_step(
            steps,
            tool="answer_question_about_recordings",
            input_payload={"question": normalized},
            output_preview=answer[:120],
        )
        return answer, steps

    context = build_unified_context_chunks(audio_matches, video_matches)
    if not context:
        return "I could not find enough transcript context in your recordings or videos.", steps

    answer = answer_question_with_groq(normalized, context)
    _append_step(
        steps,
        tool="answer_question_about_media",
        input_payload={"question": normalized},
        output_preview=answer[:120],
    )
    return answer, steps
