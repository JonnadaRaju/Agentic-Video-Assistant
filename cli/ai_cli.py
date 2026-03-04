from __future__ import annotations

import json
import os
import sys
from typing import Any

import requests
import typer

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from agent.mcp_agent import run_agent_sync


BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
cli = typer.Typer(help="AI commands for Audio Recorder")


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


@cli.command("ask-agent")
def ask_agent(
    query: str = typer.Argument(...),
    user_id: int = typer.Option(..., help="Authenticated user id"),
    email: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    token = _get_token(email, password)
    result = run_agent_sync(query=query, user_id=user_id, token=token)
    typer.echo("Reasoning steps:")
    for idx, step in enumerate(result.steps, start=1):
        typer.echo(f"{idx}. tool={step['tool']} input={step['input']}")
        typer.echo(f"   preview={step['output_preview']}")
    payload = {"query": query, "answer": result.answer, "steps": result.steps}
    _print_result(bool(result.answer.strip()), payload)


if __name__ == "__main__":
    cli()
