# MEMORY — довгострокова пам'ять

Коротко, по пункту, з датою. Застаріле видаляй. Формати — `.claude/rules/memory-formats.md`.

## Факти

- 2026-10-05 · Репо приватне: `seriefactory-studio/serie-factory`, гілка `main`. Колаборатори (admin):
  `dimaShelest` (A), `nuchay69-max` (B).
- 2026-10-05 · GitHub партнера B — **nuchay69-max**. У стартовій інструкції було `nychay69-max`: такого акаунта не існує.
- 2026-10-05 · На Mac A системний `python3` — 3.9, команди `python` нема. Python 3.12 ставить uv
  (`.python-version`). Утиліти запускаємо через `uv run`.
- 2026-10-05 · Хуки Claude Code: `uv run --no-project --quiet .claude/hooks/<скрипт>.py`, відносно кореня репо.
  Тому `claude` треба запускати з кореня репо.
- 2026-10-06 · Репо B — `D:\project\serie-factory` (диск C у B майже повний). Ollama на Windows кладе моделі
  в `%USERPROFILE%\.ollama` (C) → перед `ollama pull` у B потрібен `OLLAMA_MODELS` на D.
- 2026-10-05 · На Windows B: `python` = 3.12, `python3` = заглушка Microsoft Store, є `py`. uv 0.12.23, Git Bash є.
  Часові пояси: A пише +02:00, B — +03:00; `collab.py` порівнює з поясом, це нормально.
- 2026-10-05 · GitHub Project «Producción»: https://github.com/orgs/seriefactory-studio/projects/1
  (Backlog / Ready / In progress / Review / Done). Нові Issues додає `.github/scripts/setup_github.py`.

## Домовленості

- 2026-10-05 · Git — єдиний спільний мозок: чого нема в Git, того не існує. Ритуал: `/start` … `/handoff`.
- 2026-10-05 · Зони: A — `series/`, `fabrica/prompts/`, `docs/PLAYBOOK.md`; B — `fabrica/`, `dashboard/`, `.claude/`.
  Решта `docs/`, `tests/`, кореневі файли — спільні. Чужа зона → гілка + PR + рев'ю партнера.
- 2026-10-05 · Гілки `a/<тема>`, `b/<тема>`. Пам'ять (`docs/`) комітимо прямо в `main`. Коміти з префіксом `[A]` / `[B]`.
- 2026-10-05 · Скриньки comms: нові листи внизу; HANDOFF і DECISIONS: найновіші зверху. Час ставить `collab.py`.
- 2026-10-05 · Журнали (HANDOFF, DECISIONS, comms, prompts) мають `merge=union` у `.gitattributes`.
- 2026-10-05 · Медіа — не в Git (R2 + `output/`); у Git лише маніфести.
- 2026-10-05 · Формат: історія = 4 частини по 6–8 хв (2 на тиждень) + Película completa 25–30 хв + тизери 30–40 с.
  Перша історія — LA GARGANTA (`series/la-garganta/`); відкладені — `series/_archive/`.
- 2026-10-05 · Мітки бітів — фіксований набір (`docs/PLAYBOOK.md` → «Мітки бітів»). Нова мітка — тільки через
  `/decision` і лист партнеру, бо від неї залежать схеми фабрики.
- 2026-10-05 · Контент: регіон — Мексика, м'який акцент, мінімум сленгу (без vosotros / coger / vale-«окей»).
  Усі герої 18+, насильство за кадром, текст у кадрі не генеруємо (накладаємо в монтажі).
- 2026-10-06 · Схеми між етапами — `fabrica/models.py` (PR #10). Правила міток однакові для `story.md`, script і shots
  (`label_errors`). `fabrica/story.py` розбирає таблиці `story.md`: формат таблиць (5 колонок, `~m:ss`,
  `+C`/`!C`, `_«…»_`) тепер контракт A↔B — зміна формату ламає `check_script`.

## Уроки

- 2026-10-05 · Claude Code читає хуки зі `settings.json` на старті сесії. Змінив хуки → перезапусти сесію
  або перевір через `/hooks`.
- 2026-10-05 · `@dataclass` у модулі, який завантажено через `importlib` без `sys.modules`, падає
  з `from __future__ import annotations`. У тестах імпортуємо хуки звичайним `import` через `sys.path`.
- 2026-10-05 · На Windows shell-інструмент Claude Code — **PowerShell**, правила `Bash(...)` на нього НЕ діють
  (ні allow, ні deny). Кожне правило дублюємо як `PowerShell(...)`; перевіряє `tests/test_settings.py`.
- 2026-10-05 · Хуки й `/start` підхоплюються лише тоді, коли Claude Code відкрито в КОРЕНІ репо
  (у VS Code — тека `serie-factory`). Відкрито батьківську теку → `.claude/` не діє, а промпти не журналюються.
- 2026-10-05 · `Path.write_text(..., newline=<невалідне>)` спершу ОБРІЗАЄ файл, а потім падає на перевірці
  параметра, тож файл лишається порожнім. Масові правки — через `git diff` одразу після запису.

- 2026-10-06 · Паралельні сесії Claude A в одній теці мають спільний HEAD. Інша сесія може перемкнути гілку
  (так коміт пам'яті потрапив на `a/local-llm`). Перед кожним комітом — `git branch --show-current`. Для роботи
  в гілці під час іншої сесії — `git worktree add`, а не `git switch`.
- 2026-10-06 · Кошторис відео: ≈ $18–21 за хвилину частини (Seedance 2.5, hero 720p / secondary 480p, × 2 спроби).
  Найбільша стаття — hero-шоти, тому вау-кадри й діалоги плануємо ощадно, а ♻-шоти генеруємо один раз.
- 2026-10-06 · Гілку з PR, що відстала від `main`, оновлюємо `git merge origin/main`, а НЕ rebase:
  після rebase push відхиляється, і виникає спокуса `--force-with-lease` — це теж force-push, а його заборонено.
  (B раз так зробив з `b/schemas`; у гілці були лише його коміти, нічого не втрачено.)

## Що не працює

- 2026-10-05 · `gh project …` потребує scope `project` (`gh auth refresh -h github.com -s project`; у A вже є).
- 2026-10-05 · SessionStart-хук: `git pull --rebase` інколи падає з «Cannot rebase onto multiple branches». Одночасний
  `git fetch` (автофетч VS Code) записує `main` у `.git/FETCH_HEAD` двічі. Помилка разова, хук не падає.
  Виправлення (зона B): `git fetch` + `git rebase --autostash @{u}` замість `git pull --rebase` — PR #9.
