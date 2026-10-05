# serie-factory

Генератор іспаномовних AI-серіалів: серії 3–8 хв для YouTube (16:9) і тизери 30–40 с
для TikTok/Shorts (9:16) з обривом на хуку. Python 3.12 + uv · Typer · Pydantic · FFmpeg · SQLite.

Над проєктом працюють двоє людей, і в кожного свій Claude Code:

| | Людина | Машина | Claude | Зона |
|---|---|---|---|---|
| A | dimaShelest | Mac | Claude A | контент і продакшн: `series/`, `fabrica/prompts/`, `docs/PLAYBOOK.md` |
| B | nuchay69-max | Windows | Claude B | код і автоматизація: `fabrica/`, `dashboard/`, `.claude/` |

Claude-и не бачать чатів один одного: **вся пам'ять — у цьому репо** (`docs/`). Правила для Claude — [CLAUDE.md](CLAUDE.md).

## Перший запуск

### Mac (A)

```zsh
brew install git gh uv ffmpeg
curl -fsSL https://claude.ai/install.sh | bash        # Claude Code
gh auth login
gh repo clone seriefactory-studio/serie-factory && cd serie-factory
git config pull.rebase true && git config rebase.autoStash true
uv sync                                               # поставить Python 3.12 і залежності
cp .env.example .env                                  # і заповни ключі
printf 'Я — Claude A (Mac, партнер dimaShelest)\n' > CLAUDE.local.md
uv run pytest -q
claude                                                # з КОРЕНЯ репо
```

### Windows (B, PowerShell, без WSL)

```powershell
winget install --id Git.Git -e          # Git for Windows (потрібен і Claude Code)
winget install --id GitHub.cli -e
winget install --id astral-sh.uv -e
winget install --id Gyan.FFmpeg -e
irm https://claude.ai/install.ps1 | iex # Claude Code
# перевідкрий PowerShell, щоб оновився PATH
gh auth login
gh repo clone seriefactory-studio/serie-factory; cd serie-factory
git config pull.rebase true; git config rebase.autoStash true
uv sync
Copy-Item .env.example .env             # і заповни ключі
Set-Content -Path CLAUDE.local.md -Value 'Я — Claude B (Windows, партнер nuchay69-max)' -Encoding utf8
uv run pytest -q
claude                                  # з КОРЕНЯ репо
```

Не хочеш створювати `CLAUDE.local.md` руками — просто запусти `/start`: Claude спитає, хто ти, і створить файл сам.

При першому запуску Claude Code спитає, чи довіряти теці: погодься, інакше хуки з `.claude/settings.json`
не запрацюють. Перевірка — команда `/hooks`.

## Щоденна робота

1. `claude` у корені репо → хук сам зробить `git pull` і покаже STATUS і нові листи.
2. **`/start`**: Claude прочитає пошту від партнера, дайджест змін і твої Issues, а потім запропонує план.
3. Працюєте. Термінове партнеру — `/msg <текст>`, рішення — `/decision`, огляд — `/status`, рев'ю — `/review-pr <N>`.
4. **`/handoff`** — обов'язково в кінці: Claude оновить пам'ять, закомітить, запушить і покаже
   **ПРОМПТ ДЛЯ ПАРТНЕРА**. Перешли його в месенджер: партнер вставить його своєму Claude
   (або його Claude сам прочитає промпт на `/start`).

## Структура

```
CLAUDE.md            правила для обох Claude (перший розділ — «Як ми працюємо вдвох»)
docs/                спільна пам'ять: BRIEF, ARCHITECTURE, MEMORY, STATUS, HANDOFF, DECISIONS, COSTS, PLAYBOOK
docs/comms/          пошта між Claude: to-A.md, to-B.md
docs/prompts/        журнал промптів людей (пише хук, секрети приховано)
series/              серіали: біблії, персонажі, плани серій (A)
fabrica/             конвеєр і CLI `fabrica` (B); fabrica/prompts/ — шаблони промптів (A)
dashboard/           панель стану (B)
tests/               тести (`uv run pytest -q`)
.claude/             команди, хуки, правила, агенти Claude Code (B)
.github/             CODEOWNERS, шаблони Issue/PR, scripts/setup_github.py
```

## Якщо щось не так

- **Хук не спрацював** → `claude` запущено не з кореня репо, або `uv` не в PATH (`uv --version`).
- **`git pull` конфліктує** → хук скасує rebase і попередить. Розв'яжи вручну або попроси Claude.
- **Кракозябри замість української у Windows** → `chcp 65001` або Windows Terminal. Скрипти самі пишуть UTF-8.
- **GitHub Project** → `gh auth refresh -h github.com -s project`, потім
  `uv run --no-project .github/scripts/setup_github.py`.
