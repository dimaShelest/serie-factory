# STATUS

_Оновлено: 2026-10-05 09:30 +02:00 · Claude A_

## Зроблено
- Система спільної пам'яті двох Claude: `CLAUDE.md`, `docs/*`, скриньки `docs/comms/`, журнал промптів
  `docs/prompts/`, `collab.py` + хуки SessionStart / UserPromptSubmit, 6 слеш-команд, rules, агент pr-reviewer.
  Перевірено на macOS (30 тестів).
- GitHub: мітки `area:*` / `owner:*`, шаблони Issue і PR, CODEOWNERS, Issues тижня 1: #1–#6.

## В роботі
- (нічого — чекаємо на Windows-перевірку від B)

## Заблоковано
- **GitHub Project «Producción»** — у токена A нема scope `project`.
  Розблокувати: `gh auth refresh -h github.com -s project` → `uv run --no-project .github/scripts/setup_github.py`

## Чекає на Claude B
- #1 Windows: перевірити хуки й команди; виправлення в `b/windows-setup` → PR; підтвердити лист через `/msg`
- #2 каркас fabrica · #3 облік витрат з лімітами

## Чекає на Claude A
- Рев'ю PR `b/windows-setup`, коли з'явиться
- #4 script: біблія першого серіалу, план E01, промпти, схема `script.json` (разом з B)
- Створити Project, щойно з'явиться scope

## Чекає на людей
- dimaShelest: `gh auth refresh -h github.com -s project`
- Обоє: ідея й жанр першого серіалу; TODO у `PROJECT_BRIEF.md` (регіон/акцент, KPI); ліміти бюджету
- Кожен: ключі API у своєму `.env`
