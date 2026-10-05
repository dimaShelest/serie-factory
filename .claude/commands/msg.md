---
description: Швидке повідомлення іншому Claude у docs/comms + commit + push
argument-hint: <текст повідомлення>
allowed-tools: Bash(git:*), Bash(uv run:*), Read, Write
---

# /msg — повідомлення партнеру

Текст від людини: $ARGUMENTS

`collab` = `uv run --no-project .claude/hooks/collab.py`.

1. `collab whoami` → **X** (я), **Y** (партнер). Текст порожній → спитай людину, що передати.
2. Зроби повідомлення **самодостатнім**: партнер не бачить цієї розмови. Якщо текст посилається на
   «це», «той файл», «як домовились» — додай конкретику: шляхи, коміти, PR, Issue. Суть людини не змінюй.
   Тема — до 8 слів.
3. `git pull --rebase --autostash`
4. Запиши текст у `.claude/tmp/msg.md` (Write), потім:
   `collab send --title "<тема>" --file .claude/tmp/msg.md`
5. Закоміть ЛИШЕ скриньку:
   `git add docs/comms/to-Y.md` → `git commit -m "[X] msg → Y: <тема>"` → `git push`
   (відмова → `git pull --rebase --autostash` і ще раз).
6. Покажи людині надісланий текст одним блоком: її можна й переслати партнеру в месенджер.
