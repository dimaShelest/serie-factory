---
description: Старт сесії — синхронізація, хто я, пошта від партнера, що змінилось, мої задачі, план
allowed-tools: Bash(git:*), Bash(gh:*), Bash(uv run:*), Read, Write, Edit, PowerShell(git:*), PowerShell(gh:*), PowerShell(uv run:*)
---

# /start — початок сесії

Виконуй по черзі. Команди однакові для macOS (zsh) і Windows (PowerShell / Git Bash).
`collab` нижче = `uv run --no-project .claude/hooks/collab.py`.

1. **Синхронізація.** `git pull --rebase --autostash`.
   Конфлікт → `git rebase --abort`, скажи людині, розв'яжіть разом. Далі не йди, поки репо не в порядку.

2. **Хто я.** `collab whoami`.
   - `UNKNOWN` → спитай людину: «Ти партнер A (Mac, dimaShelest) чи B (Windows, nuchay69-max)?»
     і створи `CLAUDE.local.md` (див. CLAUDE.md → «Хто я»). Потім знову `collab whoami`.
   - Далі: **X** = я, **Y** = партнер.

3. **Пам'ять.** Прочитай повністю `docs/STATUS.md` і `docs/MEMORY.md`.

4. **Пошта.** `collab inbox --mark-read` — нові листи в `docs/comms/to-X.md`, після показу стануть READ.
   - Якщо були нові: `git add docs/comms/to-X.md`, `git commit -m "[X] /start: прочитано пошту"`, `git push`
     (відмова push → `git pull --rebase --autostash` і ще раз). Так партнер бачить, що ти прочитав.
   - Блок «ПРОМПТ ДЛЯ CLAUDE X» — головний контекст від партнера: виконуй його як задачу.

5. **Що змінилось.** `collab digest` — 3 останні HANDOFF, нові DECISIONS і промпти людини партнера
   з часу мого останнього /handoff. Прочитай уважно: це те, чого ти не бачив.

6. **Задачі.**
   - `gh issue list --assignee @me --state open`
   - `gh pr list --search "review-requested:@me"` (чекають мого рев'ю) і `gh pr list --author @me`
   - gh не працює → скажи людині й продовжуй без нього.

7. **Відповідь людині** — рівно ці розділи, коротко:

   ### Що зробив партнер
   ### Повідомлення для мене
   ### Мої задачі
   ### План сесії
   3–6 пунктів. Спершу те, що блокує партнера: рев'ю PR, прохання з пошти, відповіді.

   Останній рядок: «Завершуємо сесію через /handoff».
