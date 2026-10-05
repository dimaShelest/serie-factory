# STATUS

_Оновлено: 2026-10-05 10:46 +03:00 · Claude B_

## Зроблено
- Система спільної пам'яті двох Claude: `CLAUDE.md`, `docs/*`, скриньки `docs/comms/`, журнал промптів
  `docs/prompts/`, `collab.py` + хуки SessionStart / UserPromptSubmit, 6 слеш-команд, rules, агент pr-reviewer.
  Перевірено на macOS (30 тестів) і на Windows 11 / PowerShell + Git Bash (B): хуки, collab, тести.
- GitHub: мітки `area:*` / `owner:*`, шаблони Issue і PR, CODEOWNERS, Issues тижня 1: #1–#6.

## В роботі
- **PR #7 `b/windows-setup`** (B): PowerShell-двійники дозволів і заборон + `tests/test_settings.py`. Чекає рев'ю A.
- B: живий запуск хуків і слеш-команд у Claude Code (сесію треба перезапустити з кореня репо).

## Заблоковано
- **GitHub Project «Producción»** — у токена A нема scope `project`.
  Розблокувати: `gh auth refresh -h github.com -s project` → `uv run --no-project .github/scripts/setup_github.py`

## Чекає на Claude B
- #1: після перезапуску в корені — перевірити хуки й `/start` наживо, синтаксис `PowerShell(...)` у `/permissions`; дописати в PR #7
- #2 каркас fabrica · #3 облік витрат з лімітами

## Чекає на Claude A
- **`/review-pr 7`** (`b/windows-setup`) і merge після approve — мерджить B
- #4 script: біблія першого серіалу, план E01, промпти, схема `script.json` (разом з B)
- Створити Project, щойно з'явиться scope

## Чекає на людей
- dimaShelest: `gh auth refresh -h github.com -s project`
- Обоє: ідея й жанр першого серіалу; TODO у `PROJECT_BRIEF.md` (регіон/акцент, KPI); ліміти бюджету
- Кожен: ключі API у своєму `.env`
- nuchay69-max: відкривати в VS Code теку `serie-factory`, а не `C:\project`
