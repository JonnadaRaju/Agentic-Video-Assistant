from __future__ import annotations

import json
import mimetypes
import os
import sys
from pathlib import Path
from typing import Any

import requests
import typer

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from agent.mcp_agent import run_agent_sync


BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
cli = typer.Typer(help="AI commands for Audio/Video Recorder")


def _get_token(email: str, password: str) -> str:
    response = requests.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=20,
    )
    if not response.ok:
        raise typer.BadParameter(
            f"Login failed: {response.status_code} {response.text[:150]}"
        )
    return response.json()["access_token"]


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _print_result(passed: bool, payload: Any):
    typer.echo("PASS" if passed else "FAIL")
    typer.echo(json.dumps(payload, indent=2, default=str))
    if not passed:
        raise typer.Exit(code=1)


def _print_agent_steps(steps: list[dict[str, Any]]) -> None:
    typer.echo("Reasoning steps:")
    if not steps:
        typer.echo("(none)")
        return
    for idx, step in enumerate(steps, start=1):
        tool = step.get("tool", "unknown")
        tool_input = step.get("input", {})
        preview = step.get("output_preview", "")
        typer.echo(f"{idx}. tool={tool} input={tool_input}")
        typer.echo(f"   preview={preview}")


@cli.command("transcribe-recording")
def transcribe_recording(
    recording_id: int = typer.Argument(...),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    token = _get_token(email, password)
    response = requests.post(
        f"{BASE_URL}/recordings/{recording_id}/transcribe",
        headers=_auth_headers(token),
        timeout=180,
    )
    payload = response.json() if response.content else {}
    _print_result(response.ok and "transcript" in payload, payload)


@cli.command("summarize-recording")
def summarize_recording(
    recording_id: int = typer.Argument(...),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    token = _get_token(email, password)
    response = requests.post(
        f"{BASE_URL}/recordings/{recording_id}/summarize",
        headers=_auth_headers(token),
        timeout=120,
    )
    payload = response.json() if response.content else {}
    _print_result(response.ok and "summary" in payload, payload)


@cli.command("search-recordings")
def search_recordings(
    query: str = typer.Argument(...),
    limit: int = typer.Option(5),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    token = _get_token(email, password)
    response = requests.post(
        f"{BASE_URL}/recordings/search",
        headers=_auth_headers(token),
        json={"query": query, "limit": limit},
        timeout=60,
    )
    payload = response.json() if response.content else {}
    _print_result(response.ok and "results" in payload, payload)


@cli.command("upload-video")
def upload_video(
    video_path: str = typer.Argument(..., help="Path to local video file"),
    duration: int | None = typer.Option(None, help="Optional duration in seconds"),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    path = Path(video_path)
    if not path.exists() or not path.is_file():
        raise typer.BadParameter(f"File not found: {video_path}")

    token = _get_token(email, password)
    mime_type = mimetypes.guess_type(path.name)[0] or "video/mp4"
    with path.open("rb") as fh:
        files = {"file": (path.name, fh, mime_type)}
        data = {"duration": str(duration)} if duration is not None else None
        response = requests.post(
            f"{BASE_URL}/videos/upload",
            headers=_auth_headers(token),
            files=files,
            data=data,
            timeout=180,
        )

    payload = response.json() if response.content else {}
    _print_result(response.ok and payload.get("id") is not None, payload)


@cli.command("list-videos")
def list_videos(
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    token = _get_token(email, password)
    response = requests.get(
        f"{BASE_URL}/videos",
        headers=_auth_headers(token),
        timeout=60,
    )
    payload = response.json() if response.content else []
    _print_result(response.ok and isinstance(payload, list), payload)


@cli.command("transcribe-video")
def transcribe_video(
    video_id: int = typer.Argument(...),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    token = _get_token(email, password)
    response = requests.post(
        f"{BASE_URL}/videos/{video_id}/transcribe",
        headers=_auth_headers(token),
        timeout=240,
    )
    payload = response.json() if response.content else {}
    _print_result(response.ok and "transcript" in payload, payload)


@cli.command("summarize-video")
def summarize_video(
    video_id: int = typer.Argument(...),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    token = _get_token(email, password)
    response = requests.post(
        f"{BASE_URL}/videos/{video_id}/summarize",
        headers=_auth_headers(token),
        timeout=120,
    )
    payload = response.json() if response.content else {}
    _print_result(response.ok and "summary" in payload, payload)


@cli.command("search-videos")
def search_videos(
    query: str = typer.Argument(...),
    limit: int = typer.Option(5),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    token = _get_token(email, password)
    response = requests.post(
        f"{BASE_URL}/videos/search",
        headers=_auth_headers(token),
        json={"query": query, "limit": limit},
        timeout=60,
    )
    payload = response.json() if response.content else {}
    _print_result(response.ok and "results" in payload, payload)


@cli.command("ask-agent")
def ask_agent(
    query: str = typer.Argument(...),
    user_id: int = typer.Option(..., help="Authenticated user id"),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    token = _get_token(email, password)
    result = run_agent_sync(query=query, user_id=user_id, token=token)
    _print_agent_steps(result.steps)

    payload = {
        "query": query,
        "answer": result.answer,
        "steps": result.steps,
    }
    _print_result(bool(result.answer.strip()), payload)


if __name__ == "__main__":
    cli()
