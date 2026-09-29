"""SQLite persistence for PhD tracker progress."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "progress.db"
SEED_PATH = DATA_DIR / "plan_seed.json"

STATUSES = ("todo", "doing", "done", "blocked")


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False: Streamlit reruns scripts in different threads
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(conn: sqlite3.Connection | None = None) -> sqlite3.Connection:
    own = conn is None
    if own:
        conn = connect()
    assert conn is not None
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS phases (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            start TEXT NOT NULL,
            end TEXT NOT NULL,
            goal TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            phase TEXT NOT NULL REFERENCES phases(id),
            category TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            personal_deadline TEXT,
            official_deadline TEXT,
            weight REAL NOT NULL DEFAULT 1,
            track_key TEXT,
            status TEXT NOT NULL DEFAULT 'todo'
                CHECK(status IN ('todo', 'doing', 'done', 'blocked')),
            progress INTEGER NOT NULL DEFAULT 0
                CHECK(progress >= 0 AND progress <= 100),
            notes TEXT NOT NULL DEFAULT '',
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS subtasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id TEXT NOT NULL REFERENCES tasks(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            done INTEGER NOT NULL DEFAULT 0,
            position INTEGER NOT NULL DEFAULT 0
        );
        """
    )
    conn.commit()
    if own:
        return conn
    return conn


def is_seeded(conn: sqlite3.Connection) -> bool:
    row = conn.execute("SELECT COUNT(*) AS n FROM tasks").fetchone()
    return bool(row and row["n"] > 0)


def load_seed(seed_path: Path | None = None) -> dict[str, Any]:
    path = seed_path or SEED_PATH
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def seed_database(
    conn: sqlite3.Connection,
    seed: dict[str, Any] | None = None,
    *,
    force: bool = False,
) -> None:
    if is_seeded(conn) and not force:
        return
    if force:
        conn.executescript(
            "DELETE FROM subtasks; DELETE FROM tasks; DELETE FROM phases; DELETE FROM meta;"
        )
    data = seed or load_seed()
    now = _utc_now()
    for key, value in data.get("meta", {}).items():
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            (key, json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value),
        )
    for phase in data["phases"]:
        conn.execute(
            """
            INSERT OR REPLACE INTO phases(id, name, start, end, goal)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                phase["id"],
                phase["name"],
                phase["start"],
                phase["end"],
                phase["goal"],
            ),
        )
    for task in data["tasks"]:
        conn.execute(
            """
            INSERT OR REPLACE INTO tasks(
                id, phase, category, title, description,
                personal_deadline, official_deadline, weight, track_key,
                status, progress, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'todo', 0, '', ?)
            """,
            (
                task["id"],
                task["phase"],
                task["category"],
                task["title"],
                task.get("description", ""),
                task.get("personal_deadline"),
                task.get("official_deadline"),
                float(task.get("weight", 1)),
                task.get("track_key"),
                now,
            ),
        )
        for pos, title in enumerate(task.get("subtasks", [])):
            conn.execute(
                """
                INSERT INTO subtasks(task_id, title, done, position)
                VALUES (?, ?, 0, ?)
                """,
                (task["id"], title, pos),
            )
    conn.commit()


def get_meta(conn: sqlite3.Connection) -> dict[str, str]:
    rows = conn.execute("SELECT key, value FROM meta").fetchall()
    return {r["key"]: r["value"] for r in rows}


def export_backup(conn: sqlite3.Connection) -> dict[str, Any]:
    return {
        "exported_at": _utc_now(),
        "meta": get_meta(conn),
        "phases": list_phases(conn),
        "tasks": [
            {**t, "subtasks": list_subtasks(conn, t["id"])} for t in list_tasks(conn)
        ],
    }


def import_backup(conn: sqlite3.Connection, data: dict[str, Any]) -> None:
    """Replace DB contents with a backup/export payload."""
    conn.executescript(
        "DELETE FROM subtasks; DELETE FROM tasks; DELETE FROM phases; DELETE FROM meta;"
    )
    now = _utc_now()
    for key, value in (data.get("meta") or {}).items():
        conn.execute(
            "INSERT OR REPLACE INTO meta(key, value) VALUES (?, ?)",
            (key, value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)),
        )
    for phase in data.get("phases") or []:
        conn.execute(
            """
            INSERT OR REPLACE INTO phases(id, name, start, end, goal)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                phase["id"],
                phase["name"],
                phase["start"],
                phase["end"],
                phase.get("goal", ""),
            ),
        )
    for task in data.get("tasks") or []:
        conn.execute(
            """
            INSERT OR REPLACE INTO tasks(
                id, phase, category, title, description,
                personal_deadline, official_deadline, weight, track_key,
                status, progress, notes, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task["id"],
                task["phase"],
                task["category"],
                task["title"],
                task.get("description", ""),
                task.get("personal_deadline"),
                task.get("official_deadline"),
                float(task.get("weight", 1)),
                task.get("track_key"),
                task.get("status", "todo"),
                int(task.get("progress") or 0),
                task.get("notes") or "",
                task.get("updated_at") or now,
            ),
        )
        for pos, sub in enumerate(task.get("subtasks") or []):
            if isinstance(sub, dict):
                title = sub.get("title", "")
                done = 1 if sub.get("done") else 0
                position = int(sub.get("position", pos))
            else:
                title = str(sub)
                done = 0
                position = pos
            conn.execute(
                """
                INSERT INTO subtasks(task_id, title, done, position)
                VALUES (?, ?, ?, ?)
                """,
                (task["id"], title, done, position),
            )
    conn.commit()


def persist_cloud(conn: sqlite3.Connection) -> str | None:
    """Push progress to GitHub Gist when cloud secrets are configured.

    Returns None on success / skipped, or error message string.
    """
    try:
        from cloud_store import cloud_configured, save_progress_json
    except ImportError:
        from src.cloud_store import cloud_configured, save_progress_json  # type: ignore

    if not cloud_configured():
        return None
    try:
        save_progress_json(export_backup(conn))
        return None
    except Exception as exc:  # noqa: BLE001 — surface sync errors to UI
        return str(exc)


def ensure_ready(db_path: Path | None = None) -> sqlite3.Connection:
    # On Streamlit Cloud the repo filesystem is ephemeral — keep DB in /tmp
    try:
        from cloud_store import cloud_configured, is_streamlit_cloud, load_progress_json
    except ImportError:
        from src.cloud_store import cloud_configured, is_streamlit_cloud, load_progress_json  # type: ignore

    path = db_path
    if path is None and is_streamlit_cloud():
        path = Path("/tmp/phd_tracker_progress.db")

    conn = init_db(connect(path))

    # Important: do NOT reload from Gist on every Streamlit rerun — that wiped
    # in-progress local edits when sync lagged. Only hydrate when DB is empty.
    if is_seeded(conn):
        return conn

    seed = load_seed()
    restored = False
    if cloud_configured():
        try:
            remote = load_progress_json()
        except Exception:
            remote = None
        if remote and remote.get("tasks"):
            import_backup(conn, remote)
            restored = True

    if not restored:
        seed_database(conn, seed, force=False)
        if cloud_configured():
            persist_cloud(conn)
    return conn


def list_phases(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM phases ORDER BY start").fetchall()
    return [dict(r) for r in rows]


def list_tasks(
    conn: sqlite3.Connection,
    *,
    phase: str | None = None,
    category: str | None = None,
    status: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if phase:
        clauses.append("phase = ?")
        params.append(phase)
    if category:
        clauses.append("category = ?")
        params.append(category)
    if status:
        clauses.append("status = ?")
        params.append(status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    rows = conn.execute(
        f"SELECT * FROM tasks {where} ORDER BY personal_deadline IS NULL, personal_deadline, id",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def get_task(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    return dict(row) if row else None


def list_subtasks(conn: sqlite3.Connection, task_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT * FROM subtasks
        WHERE task_id = ?
        ORDER BY position, id
        """,
        (task_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_task(
    conn: sqlite3.Connection,
    task_id: str,
    *,
    status: str | None = None,
    progress: int | None = None,
    notes: str | None = None,
    personal_deadline: str | None = None,
    official_deadline: str | None = None,
) -> None:
    task = get_task(conn, task_id)
    if not task:
        raise KeyError(task_id)
    new_status = status if status is not None else task["status"]
    new_progress = progress if progress is not None else task["progress"]
    new_notes = notes if notes is not None else task["notes"]
    new_personal = (
        personal_deadline if personal_deadline is not None else task["personal_deadline"]
    )
    new_official = (
        official_deadline if official_deadline is not None else task["official_deadline"]
    )
    if new_status not in STATUSES:
        raise ValueError(f"invalid status: {new_status}")
    new_progress = max(0, min(100, int(new_progress)))
    if new_status == "done" and progress is None and task["status"] != "done":
        new_progress = 100
    conn.execute(
        """
        UPDATE tasks
        SET status = ?, progress = ?, notes = ?,
            personal_deadline = ?, official_deadline = ?, updated_at = ?
        WHERE id = ?
        """,
        (
            new_status,
            new_progress,
            new_notes,
            new_personal or None,
            new_official or None,
            _utc_now(),
            task_id,
        ),
    )
    conn.commit()
    err = persist_cloud(conn)
    if err:
        try:
            import streamlit as st

            st.session_state["cloud_sync_error"] = err
        except Exception:
            pass
    else:
        try:
            import streamlit as st

            st.session_state.pop("cloud_sync_error", None)
            st.session_state["cloud_sync_ok"] = True
        except Exception:
            pass


def set_subtask_done(conn: sqlite3.Connection, subtask_id: int, done: bool) -> str:
    row = conn.execute(
        "SELECT task_id FROM subtasks WHERE id = ?", (subtask_id,)
    ).fetchone()
    if not row:
        raise KeyError(subtask_id)
    conn.execute(
        "UPDATE subtasks SET done = ? WHERE id = ?",
        (1 if done else 0, subtask_id),
    )
    task_id = row["task_id"]
    subs = list_subtasks(conn, task_id)
    if subs:
        done_n = sum(1 for s in subs if s["done"])
        pct = int(round(100 * done_n / len(subs)))
        status = None
        if pct == 100:
            status = "done"
        elif pct > 0:
            current = get_task(conn, task_id)
            if current and current["status"] == "todo":
                status = "doing"
        update_task(conn, task_id, progress=pct, status=status)
    else:
        conn.commit()
        persist_cloud(conn)
    return task_id


def reset_progress(conn: sqlite3.Connection) -> None:
    seed_database(conn, force=True)
    persist_cloud(conn)


def weighted_progress(tasks: list[dict[str, Any]]) -> float:
    if not tasks:
        return 0.0
    total_w = sum(float(t.get("weight") or 1) for t in tasks)
    if total_w <= 0:
        return 0.0
    done = sum(float(t.get("weight") or 1) * (t.get("progress") or 0) / 100.0 for t in tasks)
    return 100.0 * done / total_w
