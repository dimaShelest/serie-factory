# serie-factory

Генератор іспаномовних AI-серіалів: історія = 4 частини по 6–8 хв для YouTube (16:9) + Película completa 25–30 хв,
тизери 30–40 с для TikTok/Shorts (9:16) з обривом на хуку. Перша історія — LA GARGANTA (`series/la-garganta/`).

## 1. Як ми працюємо вдвох

Над проєктом паралельно працюють **два Claude у двох різних акаунтах**, які НЕ бачать чатів один одного.
Єдиний спільний мозок — цей Git-репозиторій. **Якщо цього нема в Git — цього не існує.**

| | Claude A | Claude B |
|---|---|---|
| Людина (GitHub) | dimaShelest | nuchay69-max |
| Машина | Mac, macOS, zsh | Windows без WSL, PowerShell |
| Роль | **головний будівельник**: веде весь проєкт і всі зони (`series/`, `fabrica/`, `dashboard/`, `.claude/`) | **тестувальник і рев'юер на Windows** |
| Код | пише все | лише Windows-специфічні виправлення |
| Платні API | тільки з Mac A (журнал витрат локальний) | без ключів |

**Claude A працює автономно** по критичному шляху (`docs/STATUS.md`), не чекаючи промпту на кожен крок.
Технічні рішення ухвалює сам і пише в DECISIONS. Людину питає лише про зміст історії, гроші/ліміти й ручні дії людей.
Після кожного логічного кроку — короткий звіт людині: **1) Зроблено** (коміти/PR); **2) Далі роблю**;
**3) Що потрібно від людей** (просто, по кроках); **4) На перевірку для B** (що перевірити на Windows / прочитати).
Потім одразу наступний крок, якщо не потрібне рішення людей.

**Claude B** отримує задачі раз на кілька циклів (`/msg` або ПРОМПТ у `/handoff`): прогнати тести на Windows/PowerShell,
переглянути PR, прочитати зміни. Власник усього в CODEOWNERS — dimaShelest; nuchay69-max — рев'юер (`--reviewer`).

### Хто я
Прочитай `CLAUDE.local.md` (не в Git): там «Я — Claude A» або «Я — Claude B». SessionStart-хук теж
друкує це на старті; перевірка — `uv run --no-project .claude/hooks/collab.py whoami`.
**Файлу нема → спитай людину**, хто вона, і створи `CLAUDE.local.md` з одним рядком:
- `Я — Claude A (Mac, партнер dimaShelest)` або
- `Я — Claude B (Windows, партнер nuchay69-max)`

Далі «X» = я, «Y» = партнер.

### Обов'язковий ритуал
1. **Початок сесії → `/start`**: pull, хто я, пошта від партнера, дайджест змін, мої Issues/PR, план.
2. **Кінець сесії → `/handoff`**: тести, STATUS, MEMORY, DECISIONS, HANDOFF, підсумок промптів,
   **ПРОМПТ ДЛЯ ПАРТНЕРА** у його скриньку, commit + push. **Ніколи не завершуй роботу без `/handoff`.**
   Людина каже «все», «дякую», «на сьогодні досить» → запропонуй `/handoff`.
3. Між ними: `/msg <текст>` — терміново партнеру; `/decision` — рішення; `/status` — огляд; `/review-pr <N>`.

### Канали пам'яті
| Що | Де |
|---|---|
| Мета, аудиторія, формат, KPI | [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) |
| Конвеєр із 10 етапів, облік витрат | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| Факти, домовленості, уроки, «що не працює» | [docs/MEMORY.md](docs/MEMORY.md) |
| Зроблено / в роботі / заблоковано | [docs/STATUS.md](docs/STATUS.md) |
| Журнал передач (найновіші зверху) | [docs/HANDOFF.md](docs/HANDOFF.md) |
| Рішення: дата · хто · що · чому · альтернативи | [docs/DECISIONS.md](docs/DECISIONS.md) |
| Витрати й ліміти | [docs/COSTS.md](docs/COSTS.md) |
| Як робимо серію (зона A) | [docs/PLAYBOOK.md](docs/PLAYBOOK.md) |
| Пошта між Claude (нові внизу) | `docs/comms/to-A.md`, `docs/comms/to-B.md` |
| Журнал промптів людей (пише хук) | `docs/prompts/YYYY-MM-DD-<A\|B>.md` |

Формати записів — [.claude/rules/memory-formats.md](.claude/rules/memory-formats.md). Час і заголовки записів
ставить `collab.py`: у тебе немає годинника, тож дату не вигадуй.

### Рев'ю
Код — через гілку `a/<тема>` + PR з `--reviewer nuchay69-max`; великий PR — додатково агент `pr-reviewer`.
Мерджить A, коли тести зелені на Mac; зауваження B з Windows — окремим PR.

## 2. Git

- `main` завжди робочий. Перед комітом і пушем — `git pull --rebase --autostash`.
- Гілки: `a/<тема>` (код A), `b/<тема>` (Windows-фікси B). Гілку в спільній теці НЕ перемикай: паралельна сесія —
  лише `git worktree add <тека> <гілка>` (у спільній теці інша сесія може стояти на іншій гілці).
- Пам'ять (`docs/`) — завжди прямо в `main`, навіть якщо код у гілці (див. `/handoff`, крок 8).
- Коміти: `[A] …` / `[B] …`, по-українськи, суть у першому рядку.
- НІКОЛИ: `push --force` (і `--force-with-lease`), `reset --hard`, коміт `.env`, медіа чи `output/`. Force блокує
  PreToolUse-хук `guard_git.py`. Гілку, що відстала, оновлюй `git merge origin/main`, не rebase.
- Стекові PR: спершу `gh pr edit <дочірній> --base main`, потім merge батьківського з `--delete-branch`.
- Конфлікт у журналах (HANDOFF, DECISIONS, comms, prompts) git зливає сам (`merge=union`). Перевір порядок.

## 3. Стек і команди

Python 3.12 + uv · Typer · Pydantic · FFmpeg · SQLite. Весь код **кросплатформний**: pathlib, utf-8,
Python замість bash — див. [.claude/rules/cross-platform.md](.claude/rules/cross-platform.md).

```
uv sync                                         # залежності (Python 3.12 uv поставить сам)
uv run pytest -q                                # тести
uv run --no-project .claude/hooks/collab.py -h  # пам'ять: whoami, inbox, send, log, digest, overview
uv run fabrica --help                           # CLI фабрики: shotlist, validate, costs, schema
```

Хуки (`.claude/settings.json`): **SessionStart** — fetch + rebase, хто я, STATUS, нові листи, попередження
«не на main» і про конфлікт autostash; **UserPromptSubmit** — журнал промптів із маскуванням секретів;
**PreToolUse** — `guard_git.py` (force-push, reset --hard, clean -f). Запускай `claude` з кореня репо.
Платні виклики — лише через `Ledger.charge()` (`fabrica/ledger.py`): ліміти `BUDGET_*` не задано → виклик заборонено.

## 4. Секрети й медіа

Ключі — лише в `.env` (шаблон `.env.example`). Не читай і не виводь `.env`.
Медіа — у `output/` і R2, у Git лише маніфести. Деталі — [.claude/rules/secrets-and-media.md](.claude/rules/secrets-and-media.md).

## 5. GitHub

Issues з мітками `area:script|video|publish|infra` і `owner:A|B`; Project «Producción»
(Backlog → Ready → In progress → Review → Done). Шаблони Issue і PR — у `.github/`.
