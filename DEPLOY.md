# Деплой PhD Tracker на Streamlit Community Cloud

Чтобы открывать трекер по ссылке без `Start.bat`, нужен **GitHub** + бесплатный **Streamlit Cloud**. Прогресс в облаке хранится в **секретном GitHub Gist** (локальный SQLite на Cloud не переживает перезапуски).

## 1. Репозиторий на GitHub

1. Создайте аккаунт на [github.com](https://github.com), если ещё нет.
2. Установите Git: [git-scm.com](https://git-scm.com/download/win) (или `winget install Git.Git`).
3. В папке `phd_tracker` выполните:

```powershell
cd "c:\Users\Admin\YandexDisk\Spall Fracture things\PHD 2026\План работы в аспе\phd_tracker"
git init -b main
git add .
git commit -m "PhD tracker for Streamlit Cloud"
```

4. На GitHub: **New repository** → имя например `phd-tracker` → **без** README.
5. Привяжите и запушьте (подставьте свой логин):

```powershell
git remote add origin https://github.com/ВАШ_ЛОГИН/phd-tracker.git
git push -u origin main
```

## 2. Секретный Gist для прогресса

1. [github.com/settings/tokens](https://github.com/settings/tokens) → **Generate new token (classic)** → галочка **gist** → скопируйте токен `ghp_...`.
2. [gist.github.com](https://gist.github.com) → файл `progress.json` с содержимым `{}` → **Create secret gist**.
3. В URL вида `https://gist.github.com/login/abcdef...` скопируйте id `abcdef...`.

## 3. Деплой в Streamlit Cloud

1. Откройте [share.streamlit.io](https://share.streamlit.io) → войти через GitHub.
2. **New app** → репозиторий `phd-tracker` → Main file: `app.py` → Deploy.
3. **Settings → Secrets** → вставьте (подставьте свои значения):

```toml
[auth]
password = "ваш-пароль"

[cloud]
github_token = "ghp_..."
gist_id = "abcdef..."
```

4. Save → приложение перезапустится. Откройте выданную ссылку вида `https://....streamlit.app`.

## 4. Локально по-прежнему

`Start.bat` работает как раньше: прогресс в `data/progress.db` на Яндекс.Диске. Облако и локаль — **разные** хранилища; при необходимости перенесите через **Данные → Экспорт бэкапа**.

## Важно

- Не коммитьте `.streamlit/secrets.toml` и `progress.db`.
- Без блока `[cloud]` в Secrets облачный прогресс может обнуляться после сна приложения.
- Пароль `[auth]` желателен: URL публичный.
