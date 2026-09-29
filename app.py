"""
Личный 2-летний трекер аспирантуры (Streamlit + SQLite).
Запуск из папки phd_tracker:
    streamlit run app.py
"""
from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from db import (  # noqa: E402
    DATA_DIR,
    DB_PATH,
    STATUSES,
    ensure_ready,
    export_backup,
    get_meta,
    list_phases,
    list_subtasks,
    list_tasks,
    reset_progress,
    set_subtask_done,
    update_task,
    weighted_progress,
)
from cloud_store import cloud_configured, is_streamlit_cloud  # noqa: E402
from plan_model import (  # noqa: E402
    CATEGORY_LABELS,
    STATUS_LABELS,
    TRACK_LABELS,
    category_label,
    status_label,
)
from viz import (  # noqa: E402
    category_progress_bar,
    phase_progress_bar,
    status_donut,
    timeline_figure,
    upcoming_and_overdue,
)

st.set_page_config(
    page_title="PhD Tracker — 2 года",
    page_icon="📌",
    layout="wide",
    initial_sidebar_state="expanded",
)

CUSTOM_CSS = """
<style>
    .block-container { padding-top: 1.2rem; max-width: 1400px; }
    .metric-card {
        background: linear-gradient(145deg, #0f172a 0%, #1e293b 100%);
        color: #f8fafc;
        border-radius: 14px;
        padding: 1rem 1.2rem;
        border: 1px solid #334155;
    }
    .metric-card h3 { margin: 0; font-size: 0.85rem; color: #94a3b8; font-weight: 500; }
    .metric-card .val { font-size: 1.8rem; font-weight: 700; margin-top: 0.25rem; }
    .task-card {
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 0.9rem 1rem;
        margin-bottom: 0.6rem;
        background: #ffffff;
    }
    .deadline-warn { color: #b91c1c; font-weight: 600; }
    .deadline-ok { color: #0369a1; }
    div[data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0f172a 0%, #1e293b 60%, #0f172a 100%);
    }
    div[data-testid="stSidebar"] * { color: #e2e8f0 !important; }
    div[data-testid="stSidebar"] .stRadio label { font-weight: 500; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def get_connection():
    """Fresh connection each Streamlit rerun (avoids cross-thread SQLite errors)."""
    return ensure_ready()


def metric_card(title: str, value: str) -> None:
    st.markdown(
        f'<div class="metric-card"><h3>{title}</h3><div class="val">{value}</div></div>',
        unsafe_allow_html=True,
    )


def page_dashboard(conn) -> None:
    meta = get_meta(conn)
    phases = list_phases(conn)
    tasks = list_tasks(conn)
    overall = weighted_progress(tasks)
    done_n = sum(1 for t in tasks if t["status"] == "done")
    doing_n = sum(1 for t in tasks if t["status"] == "doing")
    overdue, upcoming = upcoming_and_overdue(tasks)

    st.title(meta.get("title", "Личный 2-летний план аспирантуры"))
    st.caption(
        f"{meta.get('author', '')} · {meta.get('topic', '')}\n\n"
        f"Горизонт: {meta.get('horizon_start', '')} — {meta.get('horizon_end', '')}"
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Общий прогресс", f"{overall:.0f}%")
    with c2:
        metric_card("Задач готово", f"{done_n} / {len(tasks)}")
    with c3:
        metric_card("В работе", str(doing_n))
    with c4:
        metric_card("Просрочено", str(len(overdue)))

    st.markdown("---")
    left, right = st.columns([1.4, 1])
    with left:
        st.subheader("Прогресс по фазам")
        st.plotly_chart(phase_progress_bar(phases, tasks), width="stretch")
        st.subheader("Прогресс по категориям")
        st.plotly_chart(category_progress_bar(tasks), width="stretch")
    with right:
        st.subheader("Статусы")
        st.plotly_chart(status_donut(tasks), width="stretch")

        st.subheader("Просроченные (личный дедлайн)")
        if not overdue:
            st.success("Нет просроченных задач")
        else:
            for t in overdue:
                st.markdown(
                    f"- **{t['id']}** {t['title']}  \n"
                    f"  <span class='deadline-warn'>{t['personal_deadline']} "
                    f"({abs(t['_days'])} дн. назад)</span>",
                    unsafe_allow_html=True,
                )

        st.subheader("Ближайшие дедлайны")
        if not upcoming:
            st.info("Нет предстоящих дедлайнов")
        else:
            for t in upcoming:
                st.markdown(
                    f"- **{t['id']}** {t['title']}  \n"
                    f"  <span class='deadline-ok'>{t['personal_deadline']} "
                    f"(через {t['_days']} дн.)</span>",
                    unsafe_allow_html=True,
                )


def page_tasks(conn) -> None:
    st.title("План и задачи")
    phases = list_phases(conn)
    phase_ids = ["Все"] + [p["id"] for p in phases]
    cats = ["Все"] + sorted(CATEGORY_LABELS.keys())
    statuses = ["Все"] + list(STATUSES)

    f1, f2, f3 = st.columns(3)
    with f1:
        phase_f = st.selectbox(
            "Фаза",
            phase_ids,
            format_func=lambda x: x
            if x == "Все"
            else next((p["name"] for p in phases if p["id"] == x), x),
        )
    with f2:
        cat_f = st.selectbox(
            "Категория",
            cats,
            format_func=lambda x: "Все" if x == "Все" else category_label(x),
        )
    with f3:
        status_f = st.selectbox(
            "Статус",
            statuses,
            format_func=lambda x: "Все" if x == "Все" else status_label(x),
        )

    tasks = list_tasks(
        conn,
        phase=None if phase_f == "Все" else phase_f,
        category=None if cat_f == "Все" else cat_f,
        status=None if status_f == "Все" else status_f,
    )
    st.caption(f"Показано задач: {len(tasks)}")

    if not tasks:
        st.warning("Нет задач по выбранным фильтрам")
        return

    labels = [f"{t['id']} · {t['title']}" for t in tasks]
    choice = st.selectbox("Выберите задачу для редактирования", labels, key="task_pick")
    task = tasks[labels.index(choice)]
    subs = list_subtasks(conn, task["id"])

    st.markdown("---")
    st.subheader(task["title"])
    st.write(task.get("description") or "")
    m1, m2, m3 = st.columns(3)
    m1.markdown(f"**Фаза:** `{task['phase']}`")
    m2.markdown(f"**Категория:** {category_label(task['category'])}")
    m3.markdown(f"**Вес:** {task['weight']}")

    with st.form(f"edit_{task['id']}", clear_on_submit=False):
        c1, c2 = st.columns(2)
        with c1:
            new_status = st.selectbox(
                "Статус",
                list(STATUSES),
                index=list(STATUSES).index(task["status"]),
                format_func=status_label,
            )
            new_progress = st.slider("Готовность %", 0, 100, int(task["progress"]))
        with c2:
            new_personal = st.text_input(
                "Личный дедлайн (YYYY-MM-DD)",
                value=task["personal_deadline"] or "",
            )
            new_official = st.text_input(
                "Официальный дедлайн ИПРА (YYYY-MM-DD)",
                value=task["official_deadline"] or "",
            )
        new_notes = st.text_area("Заметки", value=task.get("notes") or "", height=140)
        saved = st.form_submit_button("💾 Сохранить", width="stretch")

    if saved:
        update_task(
            conn,
            task["id"],
            status=new_status,
            progress=new_progress,
            notes=new_notes,
            personal_deadline=new_personal.strip() or None,
            official_deadline=new_official.strip() or None,
        )
        st.success("Сохранено в progress.db")
        st.rerun()

    st.markdown("#### Подзадачи")
    if not subs:
        st.caption("Нет подзадач")
    else:
        for s in subs:
            checked = st.checkbox(
                s["title"],
                value=bool(s["done"]),
                key=f"sub_{s['id']}",
            )
            if checked != bool(s["done"]):
                set_subtask_done(conn, s["id"], checked)
                st.rerun()

    st.progress(int(task["progress"]) / 100.0, text=f"{task['progress']}%")
    if task.get("updated_at"):
        st.caption(f"Обновлено: {task['updated_at']}")


def page_timeline(conn) -> None:
    st.title("Таймлайн")
    st.caption(
        "Серые полосы — фазы личного плана. Голубые — задачи "
        "(от начала фазы до личного дедлайна). Красная линия — сегодня."
    )
    phases = list_phases(conn)
    tasks = list_tasks(conn)
    show_done = st.checkbox("Показывать выполненные задачи", value=False)
    filtered = tasks if show_done else [t for t in tasks if t["status"] != "done"]
    st.plotly_chart(timeline_figure(phases, filtered), width="stretch")

    st.subheader("Фазы")
    for p in phases:
        phase_tasks = [t for t in tasks if t["phase"] == p["id"]]
        pct = weighted_progress(phase_tasks)
        st.markdown(f"**{p['name']}** (`{p['start']}` — `{p['end']}`) — **{pct:.0f}%**")
        st.caption(p["goal"])
        st.progress(pct / 100.0)


def page_articles_diss(conn) -> None:
    st.title("Статьи и диссертация")
    tasks = list_tasks(conn)
    by_track = {t["track_key"]: t for t in tasks if t.get("track_key")}

    st.subheader("Статьи")
    article_keys = [
        ("article_1_draft", "article_1_published"),
        ("article_2_draft", "article_2_published"),
        ("article_3_draft", "article_3_published"),
    ]
    cols = st.columns(3)
    for i, (draft_k, pub_k) in enumerate(article_keys):
        with cols[i]:
            st.markdown(f"##### Статья №{i + 1}")
            for key in (draft_k, pub_k):
                t = by_track.get(key)
                if not t:
                    st.warning(f"Нет задачи: {key}")
                    continue
                label = TRACK_LABELS.get(key, key)
                st.markdown(f"**{label}**")
                st.caption(f"{status_label(t['status'])} · {t['progress']}%")
                st.progress(t["progress"] / 100.0)
                new_p = st.slider(
                    f"% · {t['id']}",
                    0,
                    100,
                    int(t["progress"]),
                    key=f"art_sl_{t['id']}",
                )
                new_s = st.selectbox(
                    f"Статус · {t['id']}",
                    list(STATUSES),
                    index=list(STATUSES).index(t["status"]),
                    format_func=status_label,
                    key=f"art_st_{t['id']}",
                )
                note = st.text_area(
                    f"Заметки · {t['id']}",
                    value=t.get("notes") or "",
                    key=f"art_nt_{t['id']}",
                    height=80,
                )
                if st.button(f"Сохранить {t['id']}", key=f"art_sv_{t['id']}"):
                    update_task(
                        conn,
                        t["id"],
                        status=new_s,
                        progress=new_p,
                        notes=note,
                    )
                    st.success("Сохранено")
                    st.rerun()

    st.markdown("---")
    st.subheader("Диссертация (4 блока × ~25%)")
    diss_keys = ["diss_block_1", "diss_block_2", "diss_block_3", "diss_block_4"]
    dcols = st.columns(4)
    diss_tasks = []
    for i, key in enumerate(diss_keys):
        t = by_track.get(key)
        with dcols[i]:
            if not t:
                st.warning(key)
                continue
            diss_tasks.append(t)
            st.markdown(f"**Блок {i + 1}**")
            st.caption(TRACK_LABELS.get(key, key))
            st.progress(t["progress"] / 100.0)
            st.write(f"{t['progress']}% · {status_label(t['status'])}")
            new_p = st.slider(
                "Готовность",
                0,
                100,
                int(t["progress"]),
                key=f"diss_sl_{t['id']}",
            )
            new_s = st.selectbox(
                "Статус",
                list(STATUSES),
                index=list(STATUSES).index(t["status"]),
                format_func=status_label,
                key=f"diss_st_{t['id']}",
            )
            note = st.text_area(
                "Заметки",
                value=t.get("notes") or "",
                key=f"diss_nt_{t['id']}",
                height=100,
            )
            if st.button("Сохранить", key=f"diss_sv_{t['id']}"):
                update_task(conn, t["id"], status=new_s, progress=new_p, notes=note)
                st.success("Сохранено")
                st.rerun()

    if diss_tasks:
        overall_diss = weighted_progress(diss_tasks)
        st.markdown(f"#### Суммарно по диссертации: **{overall_diss:.0f}%**")
        st.progress(overall_diss / 100.0)

    st.markdown("---")
    st.subheader("Конференции")
    conf_cols = st.columns(3)
    for i, key in enumerate(["conf_1", "conf_2", "conf_3"]):
        t = by_track.get(key)
        with conf_cols[i]:
            if not t:
                continue
            st.markdown(f"**{TRACK_LABELS.get(key, key)}**")
            st.caption(f"{status_label(t['status'])} · дедлайн {t['personal_deadline']}")
            st.progress(t["progress"] / 100.0)
            if st.button(f"Отметить готово · {t['id']}", key=f"conf_done_{t['id']}"):
                update_task(conn, t["id"], status="done", progress=100)
                st.rerun()


def page_settings(conn) -> None:
    st.title("Данные и настройки")
    st.write(f"База прогресса: `{DB_PATH}`")
    st.write(f"Каталог данных: `{DATA_DIR}`")
    if is_streamlit_cloud():
        if cloud_configured():
            st.success("Облако: прогресс синхронизируется в GitHub Gist.")
        else:
            st.warning(
                "Облако без secrets: прогресс может сброситься при перезапуске. "
                "Добавьте [cloud] github_token и gist_id в Streamlit Secrets "
                "(см. DEPLOY.md)."
            )
    else:
        st.info(
            "Локально: прогресс в SQLite. В облаке — через GitHub Gist (DEPLOY.md)."
        )

    backup = export_backup(conn)
    st.download_button(
        "⬇️ Экспорт бэкапа (JSON)",
        data=json.dumps(backup, ensure_ascii=False, indent=2),
        file_name=f"phd_progress_backup_{date.today().isoformat()}.json",
        mime="application/json",
        width="stretch",
    )

    st.markdown("---")
    st.subheader("Сброс")
    st.warning(
        "Сброс удалит все статусы, проценты, заметки и отметки подзадач, "
        "затем заново загрузит plan_seed.json."
    )
    confirm = st.text_input("Введите RESET для подтверждения")
    if st.button("Сбросить прогресс", type="primary", disabled=confirm != "RESET"):
        reset_progress(conn)
        st.success("Прогресс сброшен к seed-плану")
        st.rerun()


def require_password() -> bool:
    """Optional app password from Streamlit secrets [auth].password."""
    try:
        pwd = st.secrets.get("auth", {}).get("password")
    except Exception:
        pwd = None
    if not pwd:
        return True
    if st.session_state.get("authed"):
        return True
    st.title("PhD Tracker")
    entered = st.text_input("Пароль", type="password")
    if st.button("Войти") and entered == str(pwd):
        st.session_state["authed"] = True
        st.rerun()
    if entered:
        st.error("Неверный пароль")
    return False


def main() -> None:
    if not require_password():
        return
    conn = get_connection()
    with st.sidebar:
        st.markdown("### PhD Tracker")
        st.caption("Год 1 = скрины 1–2 ИПРА · Год 2 = скрины 3–4")
        page = st.radio(
            "Раздел",
            [
                "Дашборд",
                "План / задачи",
                "Таймлайн",
                "Статьи и диссертация",
                "Данные",
            ],
            label_visibility="collapsed",
        )
        st.markdown("---")
        meta = get_meta(conn)
        overall = weighted_progress(list_tasks(conn))
        st.metric("Общий прогресс", f"{overall:.0f}%")
        st.caption(meta.get("note", ""))

    if page == "Дашборд":
        page_dashboard(conn)
    elif page == "План / задачи":
        page_tasks(conn)
    elif page == "Таймлайн":
        page_timeline(conn)
    elif page == "Статьи и диссертация":
        page_articles_diss(conn)
    else:
        page_settings(conn)


if __name__ == "__main__":
    main()
