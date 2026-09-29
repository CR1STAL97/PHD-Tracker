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
            return {"token": str(token).strip(), "gist_id": str(gist_id).strip()}
    except Exception:
        return None
    return None


def cloud_configured() -> bool:
    return _secrets_cloud() is not None


def _http_json(
    method: str,
    url: str,
    token: str,
    body: dict[str, Any] | None = None,
) -> dict[str, Any]:
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API {e.code}: {detail}") from e


def _http_text(url: str, token: str) -> str:
    req = urllib.request.Request(
        url,
        method="GET",
        headers={
            "Accept": "application/vnd.github.raw",
            "Authorization": f"Bearer {token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "phd-tracker",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub raw API {e.code}: {detail}") from e


def load_progress_json() -> dict[str, Any] | None:
    cfg = _secrets_cloud()
    if not cfg:
        return None
    payload = _http_json(
        "GET",
        f"https://api.github.com/gists/{cfg['gist_id']}",
        cfg["token"],
    )
    files = payload.get("files") or {}
    file_meta = files.get("progress.json")
    if not file_meta:
        for meta in files.values():
            if str(meta.get("filename", "")).endswith(".json"):
                file_meta = meta
                break
    if not file_meta:
        return None

    content = file_meta.get("content")
    if file_meta.get("truncated") or not content:
        raw_url = file_meta.get("raw_url")
        if not raw_url:
            return None
        content = _http_text(raw_url, cfg["token"])

    if not content or not content.strip() or content.strip() == "{}":
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
    _http_json(
        "PATCH",
        f"https://api.github.com/gists/{cfg['gist_id']}",
        cfg["token"],
        body,
    )
