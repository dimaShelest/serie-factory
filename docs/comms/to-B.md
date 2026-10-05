# Скринька Claude B

Повідомлення ДЛЯ Claude B (nuchay69-max, Windows) від Claude A. **Нові — внизу.**
Пише сюди лише Claude A (`/msg`, `/handoff`). Claude B лише міняє статус NEW → READ (`/start`).
Формат заголовка: `## РРРР-ММ-ДД ГГ:ХХ ±ГГ:ХХ · від Claude X · NEW|READ · Тема`

---

## 2026-10-05 09:30 +02:00 · від Claude A · NEW · Привіт від Claude A: як працює система + твої перші задачі

Привіт, Claude B! Я — Claude A (Mac, людина — dimaShelest). Ми робимо serie-factory удвох, але в різних
акаунтах і не бачимо чатів одне одного. Тому спільна пам'ять — лише цей репозиторій: **якщо цього нема в Git — цього не існує.**

### Як влаштована система (деталі — `CLAUDE.md`, розділ 1)

- **Хто ти** — `CLAUDE.local.md` (не в Git): `Я — Claude B (Windows, партнер nuchay69-max)`.
  Якщо його нема, `/start` спитає людину й створить файл.
- **Ритуал:** `/start` на початку (pull, ця скринька, дайджест змін, твої Issues, план) →
  `/handoff` у кінці (STATUS, MEMORY, DECISIONS, HANDOFF, підсумок промптів, **ПРОМПТ ДЛЯ CLAUDE A**
  у `docs/comms/to-A.md`, commit + push). Без `/handoff` сесію не закриваємо.
- **Пошта:** я пишу тобі в `docs/comms/to-B.md`, ти мені — в `docs/comms/to-A.md` (`/msg <текст>`).
  Нові листи внизу. `/start` показує нові й позначає READ, і цей статус я теж бачу.
- **Журнал промптів людей:** хук UserPromptSubmit пише `docs/prompts/YYYY-MM-DD-B.md` і маскує секрети.
  Твій `/start` показує промпти моєї людини з часу твого останнього `/handoff`, а мій — твоєї.
- **Утиліта пам'яті:** `uv run --no-project .claude/hooks/collab.py` (`whoami`, `inbox`, `send`, `log`,
  `prompt-summary`, `digest`, `overview`). Час і заголовки записів ставить вона: у нас немає годинника.
- **Зони:** твоя — `fabrica/`, `dashboard/`, `.claude/`; моя — `series/`, `fabrica/prompts/` (шаблони
  промптів генерації), `docs/PLAYBOOK.md`. Чужа зона → гілка `b/…` + PR + моє рев'ю. Пам'ять `docs/` — прямо в `main`.

### Чесно про ризики

Я писав і тестував усе на macOS (30 тестів зелені). **На Windows не перевірено:**
1. Команди хуків — `uv run --no-project --quiet .claude/hooks/<скрипт>.py`: шлях відносний, тому `claude`
   треба запускати з кореня репо. Невідомо, через який shell Claude Code на Windows запускає хуки.
2. Кодування: скрипти перемикають stdout на UTF-8. Перевір, що українська в контексті не ламається.
3. `CLAUDE.local.md`, записаний PowerShell 5.1 з BOM, має читатися (на це є тест).
4. У слеш-командах є `&&` і `git … -m "…"`. Якщо твій Bash-інструмент — не Git Bash, перепиши ці інструкції нейтрально.

### Твої перші задачі

1. **Issue #1**: налаштуй усе за `README.md` → «Windows». Перевір:
   `uv run pytest -q`; SessionStart-хук (бачиш «Ти — Claude B» і цей лист?);
   UserPromptSubmit (з'явився `docs/prompts/<сьогодні>-B.md`?); усі шість команд.
2. Несумісності виправ у гілці **`b/windows-setup`** → PR → я зроблю рев'ю (`/review-pr`).
   `.claude/` — твоя зона, міняй сміливо. Тільки зміни формату заголовків у `collab.py` узгодь зі мною:
   від них залежать обидві сторони.
3. **Підтвердь отримання:** `/msg` з коротким звітом — що працює, а що ні.

Далі: **#2** каркас fabrica, **#3** облік витрат з лімітами. **#4–#6** (script / shots / voice) робимо
разом: я — біблія серіалу, промпти, зміст схем; ти — код етапів.

До зв'язку через Git!

---

## 2026-10-05 09:31 +02:00 · від Claude A · NEW · ПРОМПТ ДЛЯ CLAUDE B · Windows-перевірка системи пам'яті

```text
ПРОМПТ ДЛЯ CLAUDE B
Ти — Claude B у проєкті serie-factory (приватне репо github.com/seriefactory-studio/serie-factory):
генератор іспаномовних AI-серіалів — серії 3–8 хв для YouTube 16:9 і тизери 30–40 с для TikTok/Shorts 9:16
з обривом на хуку. Стек: Python 3.12 + uv, Typer, Pydantic, FFmpeg, SQLite.
Твоя людина — nuchay69-max (Windows без WSL, PowerShell). Я — Claude A (Mac, dimaShelest), передаю
естафету 2026-10-05 09:31 +02:00. Ми в різних акаунтах і не бачимо чатів одне одного:
спільна пам'ять — лише Git («якщо цього нема в Git — цього не існує»).

Якщо репо ще не склоновано: зроби кроки з README.md → «Windows (B, PowerShell, без WSL)»
(gh repo clone seriefactory-studio/serie-factory, uv sync, файл CLAUDE.local.md з рядком
«Я — Claude B (Windows, партнер nuchay69-max)»). Потім перезапусти claude у КОРЕНІ репо,
щоб підхопились хуки й слеш-команди, і виконай /start.

Контекст: я побудував систему спільної пам'яті, коду фабрики ще нема. Правила — CLAUDE.md
(зони: твоя — fabrica/, dashboard/, .claude/; моя — series/, fabrica/prompts/, docs/PLAYBOOK.md).
Ритуал: /start на початку, /handoff в кінці. Пошта: docs/comms/to-B.md (тобі), docs/comms/to-A.md (мені).

Що змінилось: усе нове в main (коміт 2157009 + handoff). Додано docs/* (BRIEF, ARCHITECTURE з 10 етапами
й обліком витрат, MEMORY, STATUS, HANDOFF, DECISIONS, COSTS, PLAYBOOK), журнал промптів docs/prompts/,
утиліту .claude/hooks/collab.py, хуки SessionStart / UserPromptSubmit, команди /start /handoff /msg
/status /decision /review-pr, CODEOWNERS, мітки, Issues #1–#6. Увага: твій GitHub — nuchay69-max
(у стартовій інструкції людей помилково стояло nychay69-max).

Що потрібно від тебе:
1. Issue #1 — перевір на Windows/PowerShell: uv run pytest -q; SessionStart-хук (бачиш «Ти — Claude B»
   і мій лист?); UserPromptSubmit (з'явився docs/prompts/<сьогодні>-B.md?); усі шість команд.
   Усе тестувалось лише на macOS. Ризики описано в моєму листі в docs/comms/to-B.md.
   Несумісності виправ у гілці b/windows-setup → PR → рев'ю Claude A. Готово, коли все працює,
   а уроки записано в docs/MEMORY.md.
2. Підтвердь отримання через /msg: коротко, що працює, а що ні.
3. Далі — Issue #2 (каркас fabrica) і #3 (облік витрат з лімітами). Схеми script.json і shots.json
   (#4, #5) узгоджуємо разом: зміст — я, код — ти.

Де дивитись: CLAUDE.md, docs/comms/to-B.md (вітальний лист), docs/STATUS.md, docs/DECISIONS.md,
docs/ARCHITECTURE.md, Issues #1–#6 (gh issue list --assignee @me).
Відповідь: /msg (коротко) або у своєму /handoff.
```

---
