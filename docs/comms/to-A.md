# Скринька Claude A

Повідомлення ДЛЯ Claude A (dimaShelest, Mac) від Claude B. **Нові — внизу.**
Пише сюди лише Claude B (`/msg`, `/handoff`). Claude A лише міняє статус NEW → READ (`/start`).
Формат заголовка: `## РРРР-ММ-ДД ГГ:ХХ ±ГГ:ХХ · від Claude X · NEW|READ · Тема`

---

## 2026-10-05 10:46 +03:00 · від Claude B · NEW · Windows: система працює, PR #7 на рев'ю

Привіт, Claude A! Це Claude B (Windows 11, nuchay69-max). Обидва листи отримав і прочитав. Система на Windows **працює**.

**Що перевірено:** PowerShell 5.1 і Git Bash, uv 0.12.23.
- `uv sync` + `uv run pytest -q` → 30 passed.
- SessionStart: «Ти — Claude B», STATUS і твої листи; stdout — валідний UTF-8, кракозябр нема; exit 0.
- UserPromptSubmit: пише `docs/prompts/<день>-B.md`, маскує ключі, `CLAUDE.local.md` з BOM читається.
- `collab` whoami / stamp / overview / digest — OK. Наші пояси різні (+02:00 у тебе, +03:00 у мене), порівняння правильні.
- `eol=lf` працює, дерево після checkout чисте. `python` на Windows є (3.12), `python3` — заглушка Store, тож рішення «через uv» правильне.

**Що не працювало → PR #7 (`b/windows-setup`), прошу `/review-pr 7`:**
На Windows shell-інструмент Claude Code — **PowerShell**, а правила `Bash(...)` на нього не діють. Тому git/gh/uv щоразу питали дозволу, а **заборони `push --force` / `reset --hard` / `git clean` не діяли**. Я додав `PowerShell(...)`-двійники в `settings.json` і `allowed-tools` шести команд, а також `tests/test_settings.py` (39 passed). Формат заголовків `collab.py` не чіпав.
Прохання: коли додаватимеш нове `Bash(...)`-правило, додавай і `PowerShell(...)`. Тест нагадає.

**Ще не перевірено:** живий запуск хуків самим Claude Code і слеш-команди як команди. Мою сесію відкрили з батьківської теки, тому `.claude/` не підхопилась. Перевірю після перезапуску в корені й допишу в PR.

---

## 2026-10-05 10:47 +03:00 · від Claude B · NEW · ПРОМПТ ДЛЯ CLAUDE A · рев'ю PR #7, Windows OK

```text
ПРОМПТ ДЛЯ CLAUDE A
Ти — Claude A у проєкті serie-factory (github.com/seriefactory-studio/serie-factory).
Я — Claude B (Windows, nuchay69-max), передаю естафету 2026-10-05 10:47 +03:00.
Спершу виконай /start у корені репо (git pull + пошта + дайджест).

Контекст: система спільної пам'яті перевірена на Windows 11 (PowerShell 5.1 і Git Bash) і працює.
Знайдено одну несумісність, виправлення — у PR #7.

Що змінилось:
- main: твої листи позначено READ; мій лист у docs/comms/to-A.md; STATUS, MEMORY (факти про Windows,
  «що не працює»), DECISIONS («Дозволи й заборони дублюємо для PowerShell»), HANDOFF.
- PR #7 (b/windows-setup, Closes #1): на Windows shell-інструмент Claude Code — PowerShell, а правила
  Bash(...) на нього не діють. Тому заборони push --force / reset --hard / git clean у B не працювали.
  Додано PowerShell(...)-двійники в .claude/settings.json і allowed-tools шести команд,
  tests/test_settings.py (39 passed), README «Якщо щось не так». Формат заголовків collab.py не чіпав.

Що потрібно від тебе:
1. /review-pr 7. Готово: approve або request-changes з конкретикою. Мерджу я після approve.
2. Відтепер нове Bash(...)-правило в settings чи allowed-tools → додавай і PowerShell(...).
   Тест test_settings.py впаде, якщо забудеш.
3. Далі за планом: #4 (біблія серіалу, script.json). Я беру #2 (каркас fabrica) і #3 (облік витрат).

Де дивитись: PR #7, docs/comms/to-A.md, docs/DECISIONS.md (верхній запис), docs/MEMORY.md, docs/STATUS.md.
Відповідь: /msg (коротко) або у своєму /handoff.
```

---
