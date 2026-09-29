"""Helpers for plan categories and display labels."""
from __future__ import annotations

CATEGORY_LABELS = {
    "admin": "Админка / аттестация",
    "literature": "Литература",
    "modeling": "Модели",
    "code": "Код / численка",
    "article": "Статьи",
    "dissertation": "Диссертация",
    "study": "Учёба / экзамены",
    "conference": "Конференции",
}

STATUS_LABELS = {
    "todo": "К выполнению",
    "doing": "В работе",
    "done": "Готово",
    "blocked": "Заблокировано",
}

STATUS_COLORS = {
    "todo": "#94a3b8",
    "doing": "#3b82f6",
    "done": "#22c55e",
    "blocked": "#ef4444",
}

CATEGORY_COLORS = {
    "admin": "#64748b",
    "literature": "#8b5cf6",
    "modeling": "#0ea5e9",
    "code": "#06b6d4",
    "article": "#f59e0b",
    "dissertation": "#ef4444",
    "study": "#84cc16",
    "conference": "#ec4899",
}

TRACK_LABELS = {
    "article_1_draft": "Статья №1 — проект",
    "article_1_published": "Статья №1 — опубликована",
    "article_2_draft": "Статья №2 — проект",
    "article_2_published": "Статья №2 — опубликована",
    "article_3_draft": "Статья №3 — проект",
    "article_3_published": "Статья №3 — опубликована",
    "diss_block_1": "Диссертация — блок 1 (~25%)",
    "diss_block_2": "Диссертация — блок 2 (~25%)",
    "diss_block_3": "Диссертация — блок 3 (~25%)",
    "diss_block_4": "Диссертация — блок 4 (~25% + выводы)",
    "conf_1": "Конференция №1",
    "conf_2": "Конференция №2",
    "conf_3": "Конференция №3",
    "personal_ready": "Личная финальная готовность",
}


def category_label(key: str) -> str:
    return CATEGORY_LABELS.get(key, key)


def status_label(key: str) -> str:
    return STATUS_LABELS.get(key, key)
