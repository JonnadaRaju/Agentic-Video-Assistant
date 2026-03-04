from __future__ import annotations

import re

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import User
from app.schemas.agent import AgentStep
from app.services.ai_service import (
    AIServiceError,
    semantic_search_recordings,
    transcribe_and_store_recording,
    summarize_text,
    answer_question,
    build_context_chunks,
)
from app.services.recording_service import get_recordings, get_recording


def _latest_recording_intent(query: str) -> bool:
    normalized = query.lower()
    return "latest recording" in normalized or "last recording" in normalized


def _summary_intent(query: str) -> bool:
    normalized = query.lower()
    return "summarize" in normalized or "summary" in normalized


def _search_intent(query: str) -> bool:
    normalized = query.lower()
    return "find" in normalized or "search" in normalized or "mention" in normalized


def _comparison_intent(query: str) -> bool:
    normalized = query.lower()
    has_compare = any(token in normalized for token in ("compare", "difference", "changed", "change"))
    has_recording_ref = "recording" in normalized or "recordings" in normalized
    return has_compare and has_recording_ref


def _comparison_count(query: str) -> int:
    normalized = query.lower()
    match = re.search(r"\b(?:last|latest)\s+(\d+)\s+recordings?\b", normalized)
    if match:
        return max(2, min(int(match.group(1)), 5))
    if "last two recording" in normalized or "last 2 recording" in normalized:
        return 2
    if "latest two recording" in normalized or "latest 2 recording" in normalized:
        return 2
    return 2


async def execute_agent_query(
    db: AsyncSession, user: User, query: str
) -> tuple[str, list[AgentStep]]:
    steps: list[AgentStep] = []
    normalized = query.strip()
    if not normalized:
        raise AIServiceError("Query cannot be empty.")

    if _comparison_intent(normalized):
        compare_count = _comparison_count(normalized)
        recordings = await get_recordings(db, user.id)
        steps.append(
            AgentStep(
                step="1",
                tool="list_recordings",
                input={"user_id": user.id, "limit_hint": compare_count},
                output_preview=f"Found {len(recordings)} recordings",
            )
        )
        if len(recordings) < 2:
            return "I need at least 2 recordings to compare.", steps

        selected = recordings[:compare_count]
        step_idx = 2
        for idx, rec in enumerate(selected):
            if rec.transcript:
                continue
            refreshed = await get_recording(db, rec.id, user.id)
            if not refreshed:
                continue
            if not refreshed.transcript:
                refreshed = await transcribe_and_store_recording(db, refreshed)
                steps.append(
                    AgentStep(
                        step=str(step_idx),
                        tool="transcribe_audio",
                        input={"recording_id": refreshed.id},
                        output_preview=(refreshed.transcript or "")[:80],
                    )
                )
                step_idx += 1
            selected[idx] = refreshed

        context = build_context_chunks(selected)
        compare_prompt = (
            f"Compare these latest {len(selected)} recordings and show what changed. "
            "Highlight decisions, action items, and timeline updates."
        )
        comparison = answer_question(compare_prompt, context)
        steps.append(
            AgentStep(
                step=str(step_idx),
                tool="answer_question_about_recordings",
                input={"question": compare_prompt},
                output_preview=comparison[:120],
            )
        )
        return comparison, steps

    if _latest_recording_intent(normalized):
        recordings = await get_recordings(db, user.id)
        steps.append(
            AgentStep(
                step="1",
                tool="list_recordings",
                input={"user_id": user.id},
                output_preview=f"Found {len(recordings)} recordings",
            )
        )
        if not recordings:
            return "No recordings found for your account.", steps
        latest = recordings[0]
        if not latest.transcript:
            latest = await transcribe_and_store_recording(db, latest)
            steps.append(
                AgentStep(
                    step="2",
                    tool="transcribe_audio",
                    input={"recording_id": latest.id},
                    output_preview=(latest.transcript or "")[:120],
                )
            )

        if _summary_intent(normalized):
            summary = summarize_text(latest.transcript or "")
            steps.append(
                AgentStep(
                    step="3",
                    tool="summarize_audio",
                    input={"recording_id": latest.id},
                    output_preview=summary[:120],
                )
            )
            return summary, steps
        return f"Latest recording is '{latest.filename}' (id: {latest.id}).", steps

    matches = await semantic_search_recordings(db, user.id, normalized, limit=5)
    steps.append(
        AgentStep(
            step="1",
            tool="search_recordings",
            input={"query": normalized, "limit": 5},
            output_preview=f"Matched {len(matches)} recordings",
        )
    )
    if not matches:
        return "I could not find any recordings matching that query.", steps

    for idx, recording in enumerate(matches, start=2):
        if recording.transcript:
            continue
        refreshed = await get_recording(db, recording.id, user.id)
        if refreshed and not refreshed.transcript:
            refreshed = await transcribe_and_store_recording(db, refreshed)
            steps.append(
                AgentStep(
                    step=str(idx),
                    tool="transcribe_audio",
                    input={"recording_id": recording.id},
                    output_preview=(refreshed.transcript or "")[:80],
                )
            )

    context = build_context_chunks(matches)

    if _summary_intent(normalized):
        summary = summarize_text(context[0] if context else "")
        steps.append(
            AgentStep(
                step=str(len(steps) + 1),
                tool="summarize_audio",
                input={"recording_id": matches[0].id},
                output_preview=summary[:120],
            )
        )
        return summary, steps

    if _search_intent(normalized):
        lines = [
            f"- #{recording.id} {recording.filename}"
            for recording in matches[:5]
        ]
        return "Relevant recordings:\n" + "\n".join(lines), steps

    qa_answer = answer_question(normalized, context)
    steps.append(
        AgentStep(
            step=str(len(steps) + 1),
            tool="answer_question_about_recordings",
            input={"question": normalized},
            output_preview=qa_answer[:120],
        )
    )
    return qa_answer, steps
