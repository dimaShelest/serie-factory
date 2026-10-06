---
description: Рев'ю PR партнера (код, зони, кросплатформність, пам'ять) з вердиктом у GitHub
argument-hint: <номер PR>
allowed-tools: Bash(git:*), Bash(gh:*), Bash(uv run:*), Read, Write, Grep, Glob, Agent, PowerShell(git:*), PowerShell(gh:*), PowerShell(uv run:*)
---

# /review-pr — рев'ю PR партнера

PR: $ARGUMENTS (порожньо → `gh pr list --search "review-requested:@me"` і спитай, який).

`collab` = `uv run --no-project .claude/hooks/collab.py`.

1. `collab whoami` → **X**, **Y**.
2. `gh pr view <N> --json title,author,headRefName,baseRefName,body,files,reviewRequests,statusCheckRollup`
   і `gh pr diff <N>`. Великий PR (> ~400 рядків) → делегуй агенту `pr-reviewer` і перевір його висновки.
3. Контекст: пов'язані Issues, `docs/DECISIONS.md`, `docs/ARCHITECTURE.md`, `.github/CODEOWNERS`.
4. Перевір:
   - **Коректність:** логіка, крайові випадки, помилки API, повтори й ліміти витрат.
   - **Кросплатформність:** `pathlib`, `encoding="utf-8"`, без bash і шляхів з `\`/`/` руками,
     `subprocess` зі списком аргументів (див. `.claude/rules/cross-platform.md`).
   - **Безпека:** немає ключів, `.env`, медіа, великих файлів.
   - **Зони:** чужа зона зачеплена → чи є на це причина в описі PR.
   - **Тести** є й проходять. **Пам'ять** (STATUS/MEMORY/DECISIONS) оновлена, де треба.
5. Локальні тести, якщо робоче дерево чисте (`git status --porcelain` порожній):
   `gh pr checkout <N>` → `uv run pytest -q` → `git switch -`. Дерево брудне → пропусти й напиши про це.
6. Вердикт → `.claude/tmp/review.md` (зауваження з `файл:рядок`, спершу блокери), далі одне з:
   `gh pr review <N> --approve | --request-changes | --comment --body-file .claude/tmp/review.md`
7. Повідомлення автору: `collab send --title "Рев'ю PR #<N>: <вердикт>" --file .claude/tmp/review.md`
   → commit `docs/comms/to-Y.md` → push.
8. **Мерджить автор PR** після approve. Сам не мерджи, хіба що людина прямо попросить.
