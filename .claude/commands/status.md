---
description: Стан проєкту, витрати, що чекає на кого
allowed-tools: Bash(git:*), Bash(gh:*), Bash(uv run:*), Read
---

# /status — огляд

Нічого не змінюй і не комітай — лише читай і звітуй.
`collab` = `uv run --no-project .claude/hooks/collab.py`.

1. `git fetch` → `git status -sb` (відставання/випередження, незакомічене) і `git log --oneline -5 origin/main`.
2. `collab overview` — непрочитані листи в обох скриньках, останній /handoff кожного Claude.
3. Прочитай `docs/STATUS.md` і `docs/COSTS.md`. Якщо у фабрики вже є облік витрат
   (`uv run fabrica costs --help` працює) — візьми цифри звідти, це джерело правди.
4. `gh issue list --state open --limit 50` (групуй за `owner:A` / `owner:B`) і `gh pr list`
   (хто автор, кого чекає рев'ю).

Відповідь — коротко:

### Стан проєкту
етап, що готово, що в роботі, блокери
### Витрати
витрачено / ліміт за серію, день, місяць; що найдорожче; ⚠️ якщо > 80% ліміту
### Чекає на Claude A
### Чекає на Claude B
### Чекає на людей
ключі, рішення, доступи, ручні перевірки
