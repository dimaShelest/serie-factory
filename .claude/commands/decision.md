---
description: Записати рішення в docs/DECISIONS.md (дата · хто · рішення · чому · альтернативи)
argument-hint: <рішення> [чому] [альтернативи]
allowed-tools: Bash(git:*), Bash(uv run:*), Read, Write, Edit
---

# /decision — запис рішення

Від людини: $ARGUMENTS

`collab` = `uv run --no-project .claude/hooks/collab.py`.

1. `collab whoami` → **X**, **Y**.
2. Збери поля з тексту й розмови: **рішення**, **чому**, **альтернативи** (що відкинули і чому), **наслідки**
   (що міняється в коді чи процесі). Немає «чому» або «альтернатив» — спитай людину одним питанням.
3. `git pull --rebase --autostash`
4. Тіло запису → `.claude/tmp/decision.md`:
   ```
   - **Рішення:** …
   - **Чому:** …
   - **Альтернативи:** … — відкинуто, бо …
   - **Наслідки:** …
   ```
   `collab log decision --title "<рішення до 10 слів>" --file .claude/tmp/decision.md`
5. Рішення змінює домовленість у `docs/MEMORY.md` → онови MEMORY.
   Рішення зачіпає зону партнера або спільні правила → `collab send --title "Рішення: …" --file …`.
6. `git add docs/DECISIONS.md docs/MEMORY.md docs/comms` → `git commit -m "[X] decision: <назва>"` → `git push`.
7. Покажи людині запис.
