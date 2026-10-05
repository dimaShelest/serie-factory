# serie-factory

Генератор іспаномовних AI-серіалів: серії 3–8 хв для YouTube (16:9) і тизери 30–40 с для TikTok/Shorts (9:16)
з обривом на хуку.

## 1. Як ми працюємо вдвох

Над проєктом паралельно працюють **два Claude у двох різних акаунтах**, які НЕ бачать чатів один одного.
Єдиний спільний мозок — цей Git-репозиторій. **Якщо цього нема в Git — цього не існує.**

| | Claude A | Claude B |
|---|---|---|
| Людина (GitHub) | dimaShelest | nuchay69-max |
| Машина | Mac, macOS, zsh | Windows без WSL, PowerShell |
| Фокус | продакшн і контент | код і автоматизація |
| Зона власності | `series/`, `fabrica/prompts/` (промпти генерації), `docs/PLAYBOOK.md` | `fabrica/`, `dashboard/`, `.claude/` |

Спільне (редагують обидва): решта `docs/`, `tests/`, кореневі файли. Власників перевіряє `.github/CODEOWNERS`.

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

### Чужа зона
Зміна в зоні партнера → гілка + PR + рев'ю іншого Claude (`/review-pr`). PR мерджить автор після approve.
Дрібниця в чужій зоні (одрук) → можна відразу, але з `/msg` партнеру.

## 2. Git

- `main` завжди робочий. Перед комітом і пушем — `git pull --rebase --autostash`.
- Гілки: `a/<тема>` (Claude A), `b/<тема>` (Claude B). Фічі й усе в чужій зоні — через гілку й PR.
- Пам'ять (`docs/`) — завжди прямо в `main`, навіть якщо код у гілці (див. `/handoff`, крок 8).
- Коміти: `[A] …` / `[B] …`, по-українськи, суть у першому рядку.
- НІКОЛИ: `push --force`, `reset --hard`, коміт `.env`, медіа чи `output/`.
- Конфлікт у журналах (HANDOFF, DECISIONS, comms, prompts) git зливає сам (`merge=union`). Перевір порядок.

## 3. Стек і команди

Python 3.12 + uv · Typer · Pydantic · FFmpeg · SQLite. Весь код **кросплатформний**: pathlib, utf-8,
Python замість bash — див. [.claude/rules/cross-platform.md](.claude/rules/cross-platform.md).

```
uv sync                                         # залежності (Python 3.12 uv поставить сам)
uv run pytest -q                                # тести
uv run --no-project .claude/hooks/collab.py -h  # пам'ять: whoami, inbox, send, log, digest, overview
uv run fabrica --help                           # CLI фабрики (з'явиться після каркаса — Issue B)
```

Хуки (`.claude/settings.json`): **SessionStart** — pull, хто я, STATUS, нові листи;
**UserPromptSubmit** — журнал промптів із маскуванням секретів. Запускай `claude` з кореня репо.

## 4. Секрети й медіа

Ключі — лише в `.env` (шаблон `.env.example`). Не читай і не виводь `.env`.
Медіа — у `output/` і R2, у Git лише маніфести. Деталі — [.claude/rules/secrets-and-media.md](.claude/rules/secrets-and-media.md).

## 5. GitHub

Issues з мітками `area:script|video|publish|infra` і `owner:A|B`; Project «Producción»
(Backlog → Ready → In progress → Review → Done). Шаблони Issue і PR — у `.github/`.
