import os
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import VideoRecording


def _safe_extension(filename: str | None) -> str:
    if not filename:
        return ".webm"
    ext = Path(filename).suffix.lower()
    if not ext:
        return ".webm"
    if not all(ch.isalnum() or ch == "." for ch in ext):
        return ".webm"
    if len(ext) > 10:
        return ".webm"
    return ext


async def save_video_file(
    file_content: bytes,
    user_id: int,
    original_filename: str | None = None,
) -> tuple[str, str]:
    upload_dir = Path(settings.UPLOAD_VIDEO_DIR) / str(user_id)
    upload_dir.mkdir(parents=True, exist_ok=True)

    extension = _safe_extension(original_filename)
    stored_filename = f"{uuid.uuid4()}{extension}"
    file_path = upload_dir / stored_filename

    with open(file_path, "wb") as f:
        f.write(file_content)

    return stored_filename, str(file_path)


async def create_video_recording(
    db: AsyncSession,
    user_id: int,
    filename: str,
    file_path: str,
    file_size: int,
    duration: int | None = None,
) -> VideoRecording:
    recording = VideoRecording(
        user_id=user_id,
        filename=filename,
        file_path=file_path,
        file_size=file_size,
        duration=duration,
    )
    db.add(recording)
    await db.commit()
    await db.refresh(recording)
    return recording


async def get_videos(db: AsyncSession, user_id: int) -> list[VideoRecording]:
    result = await db.execute(
        select(VideoRecording)
        .where(VideoRecording.user_id == user_id)
        .order_by(VideoRecording.created_at.desc())
    )
    return list(result.scalars().all())


async def get_video(
    db: AsyncSession,
    video_id: int,
    user_id: int,
) -> VideoRecording | None:
    result = await db.execute(
        select(VideoRecording).where(
            VideoRecording.id == video_id,
            VideoRecording.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def delete_video(db: AsyncSession, recording: VideoRecording) -> None:
    if os.path.exists(recording.file_path):
        os.remove(recording.file_path)
    await db.delete(recording)
    await db.commit()
