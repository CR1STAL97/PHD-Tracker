"""Cloud progress sync for Streamlit Community Cloud (GitHub Gist)."""
from __future__ import annotations

import json
import os
from typing import Any

import urllib.error
import urllib.request


def is_streamlit_cloud() -> bool:
    return (
        os.environ.get("STREAMLIT_RUNTIME_ENV") == "cloud"
        or os.path.exists("/mount/src")
        or os.environ.get("HOSTNAME", "").startswith("streamlit")
    )


def _secrets_cloud() -> dict[str, str] | None:
    try:
        import streamlit as st

        cloud = st.secrets.get("cloud", None)
        if not cloud:
            return None
        token = cloud.get("github_token") or cloud.get("token")
        gist_id = cloud.get("gist_id")
        if token and gist_id:
            return {"token": str(token), "gist_id": str(gist_id)}
    except Exception:
        return None
    return None


def cloud_configured() -> bool:
    return _secrets_cloud() is not None


def _gist_request(
    method: str,
    gist_id: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    url = f"https://api.github.com/gists/{gist_id}"
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "phd-tracker",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub Gist API {e.code}: {detail}") from e


def load_progress_json() -> dict[str, Any] | None:
    cfg = _secrets_cloud()
    if not cfg:
        return None
    payload = _gist_request("GET", cfg["gist_id"], cfg["token"])
    files = payload.get("files") or {}
    # Prefer known name, else first JSON file
    content = None
    if "progress.json" in files:
        content = files["progress.json"].get("content")
    else:
        for meta in files.values():
            if meta.get("filename", "").endswith(".json"):
                content = meta.get("content")
                break
    if not content:
        return None
    data = json.loads(content)
    if not isinstance(data, dict) or "tasks" not in data:
        return None
    return data


def save_progress_json(backup: dict[str, Any]) -> None:
    cfg = _secrets_cloud()
    if not cfg:
        return
    body = {
        "files": {
            "progress.json": {
                "content": json.dumps(backup, ensure_ascii=False, indent=2),
            }
        }
    }
    _gist_request("PATCH", cfg["gist_id"], cfg["token"], body)
