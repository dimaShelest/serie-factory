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
- 2026-10-05 · На Windows B: `python` = 3.12, `python3` = заглушка Microsoft Store, є `py`. uv 0.12.23, Git Bash є.
  Часові пояси: A пише +02:00, B — +03:00; `collab.py` порівнює з поясом, це нормально.

## Домовленості

- 2026-10-05 · Git — єдиний спільний мозок: чого нема в Git, того не існує. Ритуал: `/start` … `/handoff`.
- 2026-10-05 · Зони: A — `series/`, `fabrica/prompts/`, `docs/PLAYBOOK.md`; B — `fabrica/`, `dashboard/`, `.claude/`.
  Решта `docs/`, `tests/`, кореневі файли — спільні. Чужа зона → гілка + PR + рев'ю партнера.
- 2026-10-05 · Гілки `a/<тема>`, `b/<тема>`. Пам'ять (`docs/`) комітимо прямо в `main`. Коміти з префіксом `[A]` / `[B]`.
- 2026-10-05 · Скриньки comms: нові листи внизу; HANDOFF і DECISIONS: найновіші зверху. Час ставить `collab.py`.
- 2026-10-05 · Журнали (HANDOFF, DECISIONS, comms, prompts) мають `merge=union` у `.gitattributes`.
- 2026-10-05 · Медіа — не в Git (R2 + `output/`); у Git лише маніфести.

## Уроки

- 2026-10-05 · Claude Code читає хуки зі `settings.json` на старті сесії. Змінив хуки → перезапусти сесію
  або перевір через `/hooks`.
- 2026-10-05 · `@dataclass` у модулі, який завантажено через `importlib` без `sys.modules`, падає
  з `from __future__ import annotations`. У тестах імпортуємо хуки звичайним `import` через `sys.path`.
- 2026-10-05 · На Windows shell-інструмент Claude Code — **PowerShell**, правила `Bash(...)` на нього НЕ діють
  (ні allow, ні deny). Кожне правило дублюємо як `PowerShell(...)`; перевіряє `tests/test_settings.py`.
- 2026-10-05 · Хуки й `/start` підхоплюються лише тоді, коли Claude Code відкрито в КОРЕНІ репо
  (у VS Code — тека `serie-factory`). Відкрито батьківську теку → `.claude/` не діє, а промпти не журналюються.

## Що не працює

- 2026-10-05 · `gh project …` з токеном A без scope `project` → спершу `gh auth refresh -h github.com -s project`.
