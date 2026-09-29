"""Plotly visualizations for the PhD tracker."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from plan_model import CATEGORY_COLORS, STATUS_COLORS, category_label
from db import weighted_progress


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def phase_progress_bar(phases: list[dict[str, Any]], tasks: list[dict[str, Any]]) -> go.Figure:
    rows = []
    by_phase: dict[str, list[dict[str, Any]]] = {}
    for t in tasks:
        by_phase.setdefault(t["phase"], []).append(t)
    for p in phases:
        pct = weighted_progress(by_phase.get(p["id"], []))
        rows.append({"Фаза": p["id"], "Название": p["name"], "Прогресс %": round(pct, 1)})
    df = pd.DataFrame(rows)
    fig = px.bar(
        df,
        x="Фаза",
        y="Прогресс %",
        text="Прогресс %",
        hover_data=["Название"],
        color="Прогресс %",
        color_continuous_scale="Tealgrn",
        range_y=[0, 100],
    )
    fig.update_traces(textposition="outside")
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        height=320,
        coloraxis_showscale=False,
        yaxis_title="",
        xaxis_title="",
    )
    return fig


def category_progress_bar(tasks: list[dict[str, Any]]) -> go.Figure:
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for t in tasks:
        by_cat.setdefault(t["category"], []).append(t)
    rows = []
    for cat, items in sorted(by_cat.items(), key=lambda x: category_label(x[0])):
        rows.append(
            {
                "Категория": category_label(cat),
                "cat": cat,
                "Прогресс %": round(weighted_progress(items), 1),
            }
        )
    df = pd.DataFrame(rows)
    colors = [CATEGORY_COLORS.get(c, "#64748b") for c in df["cat"]]
    fig = go.Figure(
        go.Bar(
            x=df["Прогресс %"],
            y=df["Категория"],
            orientation="h",
            marker_color=colors,
            text=df["Прогресс %"],
            textposition="auto",
        )
    )
    fig.update_layout(
        margin=dict(l=20, r=20, t=30, b=20),
        height=max(280, 36 * len(df) + 80),
        xaxis=dict(range=[0, 100], title="Прогресс %"),
        yaxis_title="",
    )
    return fig


def status_donut(tasks: list[dict[str, Any]]) -> go.Figure:
    counts: dict[str, int] = {}
    for t in tasks:
        counts[t["status"]] = counts.get(t["status"], 0) + 1
    labels = list(counts.keys())
    values = [counts[k] for k in labels]
    colors = [STATUS_COLORS.get(k, "#94a3b8") for k in labels]
    fig = go.Figure(
        go.Pie(
            labels=labels,
            values=values,
            hole=0.55,
            marker=dict(colors=colors),
            textinfo="label+value",
        )
    )
    fig.update_layout(margin=dict(l=10, r=10, t=30, b=10), height=320, showlegend=False)
    return fig


def timeline_figure(
    phases: list[dict[str, Any]],
    tasks: list[dict[str, Any]],
    *,
    today: date | None = None,
) -> go.Figure:
    today = today or date.today()
    rows = []
    for p in phases:
        rows.append(
            {
                "Task": p["name"],
                "Start": p["start"],
                "Finish": p["end"],
                "Kind": "Фаза",
                "Status": "phase",
                "Category": "phase",
            }
        )
    for t in tasks:
        start = t.get("personal_deadline")
        # Use phase start as bar start when only deadline is known
        phase = next((p for p in phases if p["id"] == t["phase"]), None)
        bar_start = phase["start"] if phase else start
        bar_end = start or (phase["end"] if phase else None)
        if not bar_start or not bar_end:
            continue
        # Ensure start <= end
        if bar_start > bar_end:
            bar_start, bar_end = bar_end, bar_start
        rows.append(
            {
                "Task": f"{t['id']}: {t['title'][:48]}",
                "Start": bar_start,
                "Finish": bar_end,
                "Kind": "Задача",
                "Status": t["status"],
                "Category": t["category"],
            }
        )
    if not rows:
        fig = go.Figure()
        fig.update_layout(title="Нет данных для таймлайна", height=400)
        return fig

    df = pd.DataFrame(rows)
    fig = px.timeline(
        df,
        x_start="Start",
        x_end="Finish",
        y="Task",
        color="Kind",
        hover_data=["Status", "Category"],
        color_discrete_map={"Фаза": "#cbd5e1", "Задача": "#38bdf8"},
    )
    today_ts = datetime.combine(today, datetime.min.time())
    fig.add_shape(
        type="line",
        x0=today_ts,
        x1=today_ts,
        y0=0,
        y1=1,
        yref="paper",
        line=dict(color="#ef4444", width=2, dash="dash"),
    )
    fig.add_annotation(
        x=today_ts,
        y=1.02,
        yref="paper",
        text="Сегодня",
        showarrow=False,
        font=dict(color="#ef4444", size=12),
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_layout(
        margin=dict(l=20, r=20, t=40, b=20),
        height=max(480, 22 * len(df) + 120),
        legend_title_text="",
        xaxis_title="",
        yaxis_title="",
    )
    return fig


def upcoming_and_overdue(
    tasks: list[dict[str, Any]],
    *,
    today: date | None = None,
    limit: int = 8,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    today = today or date.today()
    overdue: list[dict[str, Any]] = []
    upcoming: list[dict[str, Any]] = []
    for t in tasks:
        if t["status"] == "done":
            continue
        d = _parse_date(t.get("personal_deadline"))
        if not d:
            continue
        item = {**t, "_deadline": d, "_days": (d - today).days}
        if d < today:
            overdue.append(item)
        else:
            upcoming.append(item)
    overdue.sort(key=lambda x: x["_deadline"])
    upcoming.sort(key=lambda x: x["_deadline"])
    return overdue[:limit], upcoming[:limit]
