# Media Intelligence MCP Server

## Tools

Audio tools (existing):

- `list_recordings(user_id, token?)`
- `get_recording_metadata(recording_id, token?)`
- `transcribe_audio(recording_id, token?)`
- `summarize_audio(recording_id, token?)`
- `search_recordings(query, limit?, token?)`
- `answer_question_about_recordings(question, limit?, token?)`

Video tools (new):

- `list_videos(user_id, token?)`
- `get_video_metadata(video_id, token?)`
- `transcribe_video(video_id, token?)`
- `summarize_video(video_id, token?)`
- `search_videos(query, limit?, token?)`
- `answer_question_about_videos(question, limit?, token?)`

## Setup

```powershell
cd mcp_server
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Environment

- `MCP_API_BASE_URL` default `http://localhost:8000`
- `MCP_API_TOKEN` JWT for user-scoped access
- `MCP_REQUEST_TIMEOUT_SECONDS` default `20`

## Run

```powershell
.\.venv\Scripts\python.exe server.py
```

## Security Notes

- Tool inputs are strongly typed.
- Query/question fields are sanitized and checked for prompt-injection markers.
- User ownership and access control are enforced by FastAPI JWT-scoped endpoints.
