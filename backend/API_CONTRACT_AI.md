# AI API Contract

## Authentication

All endpoints below require:

- `Authorization: Bearer <jwt>`

## Audio Endpoints

### `POST /recordings/{id}/transcribe`

Transcribes one audio recording and stores transcript + embedding.

### `POST /recordings/search`

Semantic search over audio transcripts.

### `POST /recordings/{id}/summarize`

Summarizes one audio recording transcript (auto-transcribes first when needed).

### `POST /recordings/answer`

Answers a question using matching audio transcripts.

## Video Endpoints

### `POST /videos/upload`

Uploads a video file, stores metadata, and persists file under `uploads/videos/<user_id>/...`.

### `GET /videos`

Returns authenticated user's videos (latest first).

### `GET /videos/{id}`

Returns one video metadata record.

### `DELETE /videos/{id}`

Deletes one video and its stored file.

### `GET /videos/{id}/stream`

Streams one owned video file.

### `POST /videos/{id}/transcribe`

Pipeline:

1. Extract audio with FFmpeg
2. Transcribe extracted audio (Sarvam-configured path with fallback)
3. Store transcript and embedding

Response:

```json
{
  "video_id": 42,
  "transcript": "Full transcript text...",
  "transcript_preview": "First 240 chars..."
}
```

### `POST /videos/{id}/summarize`

Generates/stores summary using Groq-configured chat path (fallback supported).

Response:

```json
{
  "video_id": 42,
  "summary": "Concise summary of the video."
}
```

### `POST /videos/search`

Semantic search over video transcripts.

Request:

```json
{
  "query": "deadline discussion",
  "limit": 5
}
```

Response:

```json
{
  "query": "deadline discussion",
  "total_matches": 2,
  "results": [
    {
      "id": 42,
      "filename": "meeting.mp4",
      "duration": 135,
      "created_at": "2026-03-04T12:00:00",
      "transcript_preview": "We discussed project deadlines..."
    }
  ]
}
```

### `POST /videos/answer`

Question answering grounded on matching video transcripts.

Request:

```json
{
  "question": "What did I say about deadlines in my videos?",
  "limit": 5
}
```

Response:

```json
{
  "question": "What did I say about deadlines in my videos?",
  "answer": "You said deadlines were moved to next Friday.",
  "matched_video_ids": [42, 43]
}
```

## Agent Endpoint

### `POST /agent/query`

Supports audio-only, video-only, and combined audio+video retrieval/reasoning.

Request:

```json
{
  "query": "Summarize my latest video"
}
```

Response:

```json
{
  "query": "Summarize my latest video",
  "answer": "Summary text...",
  "steps": [
    {
      "step": "1",
      "tool": "list_videos",
      "input": {"user_id": 1},
      "output_preview": "Found 3 videos"
    }
  ]
}
```
