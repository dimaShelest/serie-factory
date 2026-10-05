# HANDOFF — журнал передач

Кожна сесія завершується записом тут: `/handoff` → `collab log handoff …`. **Найновіші зверху.**
Повний промпт для партнера — у його скриньці `docs/comms/to-X.md`.

<!-- НОВІ ЗАПИСИ — ОДРАЗУ ПІД ЦИМ РЯДКОМ (найновіші зверху) -->

## 2026-10-05 13:38 +02:00 · Claude A · LA GARGANTA заповнено, рев'ю PR #7, Project «Producción»

- **Зроблено:**
  - `/start`: пошту B прочитано (READ).
  - **Рев'ю PR #7 → approve** (39 passed у worktree, без конфліктів). Зауваження: перед merge — жива перевірка `/permissions` або `Refs #1`; префіксні deny обходяться прапорцем у кінці; немає `Bash(cat .env)`.
  - **GitHub Project «Producción»** створено (https://github.com/orgs/seriefactory-studio/projects/1): #1 і PR #7 → Review, #2 і #4 → In progress, #3, #5, #6 → Ready.
  - **Біблія**: El Precio (блок а) → люди змінили формат і першу історію → El Precio в `series/_archive/`.
  - **LA GARGANTA** за текстом людини: `bible.yaml` (6 персонажів з візуальною ДНК, 9 локацій, правила світу, мова, табу, ризики), `story.md` (4 частини бітами, мітки, 7 тизерів, Película completa ≈27 хв, 5 питань логіки), `clues.md` (C01–C12, хибні сліди F1–F2, перевірка чесності).
  - Новий формат і мітка `SCREAMER` — у PROJECT_BRIEF, PLAYBOOK, ARCHITECTURE. Регіон — Мексика, м'який акцент; герої 18–19.
- **Змінено:** `series/`, `docs/` (BRIEF, PLAYBOOK, ARCHITECTURE, MEMORY, STATUS, DECISIONS), comms; коміти `56d3670`, `03585c1`, `530f700` + цей.
- **Тести:** `uv run pytest -q` → 30 passed. Скрипт перевірки `story.md`: у кожній частині рівно один HOOK_OPEN/MIDPOINT/CLIFF, SCREAMER ≤ 2, тизери в парах, ID підказок існують, заборонених слів немає.
- **Рішення:** 7 записів у DECISIONS: El Precio і мінісезони (обидва потім скасовано), формат 4 частини + фільм, LA GARGANTA, мітки + SCREAMER, Мексика, герої 18–19.
- **Відкрите / далі:** людина затверджує LA GARGANTA (питання логіки в `story.md`); B — merge PR #7, схеми `b/schemas`, гонка FETCH_HEAD у хуку; A — шаблони промптів script для LA GARGANTA, рев'ю схем.
- **Для партнера:** ПРОМПТ ДЛЯ CLAUDE B → `docs/comms/to-B.md`.

---

## 2026-10-05 10:47 +03:00 · Claude B · Windows-перевірка: система працює, PR #7 з PowerShell-дозволами

- **Зроблено:** перша сесія B. Windows-перевірка системи пам'яті (Issue #1): `uv sync`, тести, SessionStart і UserPromptSubmit (PowerShell і Git Bash), `collab` whoami/stamp/overview/digest. Усе працює, UTF-8 і BOM — OK. Пошту від A прочитано (READ), відповідь — `/msg` у `to-A.md`.
- **Змінено:** PR #7 `b/windows-setup`: PowerShell-двійники в `.claude/settings.json` і `allowed-tools` шести команд, `tests/test_settings.py`, README «Якщо щось не так». У `main`: STATUS, MEMORY, DECISIONS, comms.
- **Тести:** `uv run pytest -q` → 30 passed на `main` (Windows), 39 passed на `b/windows-setup`.
- **Рішення:** дозволи й заборони дублюємо для PowerShell (→ DECISIONS).
- **Відкрите / далі:** живий запуск хуків і слеш-команд у Claude Code не перевірено: сесію відкрито з батьківської теки `C:\project`, тому `.claude/` не підхопилась, і промпти цієї сесії хук не журналював. Наступна сесія B — у корені репо, далі #2 і #3.
- **Для партнера:** `/review-pr 7`. Повний промпт → `docs/comms/to-A.md`.

---

## 2026-10-05 09:31 +02:00 · Claude A · Система спільної пам'яті A↔B готова, лист і задачі для B

- **Зроблено:** система спільної пам'яті двох Claude:
  - `CLAUDE.md` (89 рядків) і пам'ять у `docs/`: BRIEF, ARCHITECTURE з 10 етапами, MEMORY, STATUS, HANDOFF, DECISIONS, COSTS, PLAYBOOK;
  - скриньки `docs/comms/` і журнал промптів людей `docs/prompts/`;
  - `.claude/hooks/collab.py` і два хуки, 6 слеш-команд, rules, агент `pr-reviewer`;
  - `.github/`: CODEOWNERS, шаблони, `scripts/setup_github.py`; README з першим запуском на Mac і Windows;
  - мітки `area:*` / `owner:*`, Issues #1–#6.
- **Змінено:** усе нове; коміт `2157009` + цей handoff-коміт у `main`.
- **Тести:** `uv run pytest -q` → 30 passed (macOS). Хуки запускаються через uv (Python 3.12) і системний python3 3.9. **На Windows не перевірено** — це Issue #1 для B.
- **Рішення:** 6 записів у DECISIONS: канал Git, `collab.py`, хуки через uv, порядок записів + `merge=union`, `fabrica/prompts/` у зоні A, медіа поза Git.
- **Відкрите / далі:** GitHub Project «Producción» (у токена нема scope `project`); Windows-перевірка (B, #1); біблія першого серіалу (A, #4).
- **Для партнера:** вітальний лист і ПРОМПТ ДЛЯ CLAUDE B — у `docs/comms/to-B.md`. GitHub B — `nuchay69-max`, а не `nychay69-max`.

---
