---
description: Кінець сесії — тести, пам'ять, журнал передач, промпт для партнера, commit + push
allowed-tools: Bash(git:*), Bash(gh:*), Bash(uv run:*), Read, Write, Edit, PowerShell(git:*), PowerShell(gh:*), PowerShell(uv run:*)
---

# /handoff — передача естафети (ОБОВ'ЯЗКОВО в кінці кожної сесії)

`collab` = `uv run --no-project .claude/hooks/collab.py`. Формати записів — `.claude/rules/memory-formats.md`.
Чернетки для `--file` пиши в `.claude/tmp/` (він у .gitignore).

0. `collab whoami` → **X** (я), **Y** (партнер). `git branch --show-current` → гілка.
   `git pull --rebase --autostash`, щоб редагувати свіжу пам'ять.

1. **Тести.** Є тести в `tests/` → `uv run pytest -q`. Падіння не ховай: пиши в HANDOFF і STATUS.

2. **docs/STATUS.md** — онови «Оновлено», «Зроблено / В роботі / Заблоковано», «Чекає на A/B/людей».
   Застаріле прибирай: STATUS показує стан зараз, а не історію.

3. **docs/MEMORY.md** — лише НОВІ довгострокові знання цієї сесії (факти, домовленості, уроки,
   «що не працює»), по пункту, з датою. Застаріле видаляй або виправляй.

4. **DECISIONS** — кожне рішення сесії окремо (якщо ще не записане через /decision):
   `collab log decision --title "<рішення>" --file .claude/tmp/decision.md`

5. **HANDOFF** — `collab log handoff --title "<тема сесії>" --file .claude/tmp/handoff.md`. Тіло:
   ```
   - **Зроблено:** …
   - **Змінено:** файли/зони, коміти, PR
   - **Тести:** результат
   - **Рішення:** … (→ DECISIONS)
   - **Відкрите / далі:** …
   - **Для партнера:** коротко (повний промпт → comms/to-Y.md)
   ```

6. **Підсумок промптів** — `collab prompt-summary --file .claude/tmp/summary.md`:
   по пункту на кожну задачу, яку давала людина в цій сесії: `- <задача> → <що вийшло / де>`.

7. **ПРОМПТ ДЛЯ ПАРТНЕРА.** Склади самодостатній промпт: партнер не бачив цієї розмови. Шаблон:
   ```
   ПРОМПТ ДЛЯ CLAUDE Y
   Ти — Claude Y у проєкті serie-factory (github.com/seriefactory-studio/serie-factory).
   Я — Claude X, передаю естафету <collab stamp>.
   Спершу виконай /start у корені репо (git pull + пошта + дайджест).
   Контекст: <1–3 речення: де зараз проєкт>
   Що змінилось: <пункти з посиланнями на файли / коміти / PR>
   Що потрібно від тебе: <нумеровані задачі + критерій «готово»>
   Де дивитись: <docs/…, Issue #, PR #>
   Відповідь: /msg (коротко) або у своєму /handoff.
   ```
   Надіслати: `collab send --title "ПРОМПТ ДЛЯ CLAUDE Y · <тема>" --file .claude/tmp/prompt.md`

8. **Commit + push.** `git status` — не додавай `.env`, медіа, `output/`.
   - **На main:** `git add` пам'ять (`docs/`) + свої зміни → `git commit -m "[X] handoff: <тема>"` →
     `git pull --rebase --autostash` → `git push`.
   - **На гілці `x/…`:** код комітом у гілку → `git push -u origin HEAD` →
     `gh pr create --fill` (якщо зачеплена зона партнера: `--reviewer <GitHub партнера>`) або оновлений PR.
     Пам'ять (`docs/`) завжди йде в **main**: `git stash push -- docs` → `git switch main` →
     `git pull --rebase --autostash` → `git stash pop` → commit → push → `git switch -`.
   - Push відхилено → `git pull --rebase --autostash` і ще раз. НІКОЛИ не `--force`.

9. **Відповідь людині:**
   - 3–5 рядків: що зроблено, що лишилось, де PR/коміт;
   - блок «ПРОМПТ ДЛЯ CLAUDE Y» **дослівно** в fenced code block — людина перешле його в месенджер.
