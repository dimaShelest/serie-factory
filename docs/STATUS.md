# STATUS

_Оновлено: 2026-10-05 13:36 +02:00 · Claude A_

Дошка: [Producción](https://github.com/orgs/seriefactory-studio/projects/1)

## Зроблено
- Система спільної пам'яті A↔B працює на macOS і Windows (30 тестів у main).
- GitHub Project «Producción» створено; на дошці Issues #1–#6 і PR #7 зі статусами.
- Формат каналу: історія = 4 частини по 6–8 хв + Película completa 25–30 хв + тизери; мітки бітів з `SCREAMER`.
- **LA GARGANTA** (`series/la-garganta/`): біблія (6 персонажів з візуальною ДНК, 9 локацій, правила світу, табу,
  ризики), сюжет 4 частинами з мітками і 7 тизерами, ланцюжок 12 підказок + 2 хибні сліди. Статус — чернетка
  на затвердження людиною.
- Регіон — Мексика, м'який акцент; герої 18–19. El Precio — в архіві.

## В роботі
- **PR #7** `b/windows-setup` (B): approve від A. Перед merge B перевіряє `/permissions` наживо. Мерджить B.
- #2 каркас fabrica (B) · #4 script: біблія готова, далі — схема `script.json` (A зміст + B код).

## Заблоковано
- (нічого)

## Чекає на Claude B
- Merge PR #7 після живої перевірки `/permissions` (або `Refs #1` замість `Closes #1`)
- Схеми `script.json` / `shots.json` під новий формат → PR `b/schemas` (поля — лист у `docs/comms/to-B.md`)
- Виправити гонку `FETCH_HEAD` у `session_start.py` (MEMORY → «Що не працює»)
- #2 каркас fabrica · #3 облік витрат

## Чекає на Claude A
- Після merge PR #7 — перевірити `/permissions` на Mac (чи не дають помилок правила `PowerShell(...)`)
- Рев'ю контентної частини схем B; шаблони промптів `fabrica/prompts/script/` для LA GARGANTA
- Внести відповіді людини на «Питання логіки» в `story.md`

## Чекає на людей
- dimaShelest: затвердити LA GARGANTA — 5 питань логіки (`story.md`), візуальна ДНК, імена сімох, C12, SCREAMER у фіналі
- Обоє: числа KPI в `PROJECT_BRIEF.md`; ліміти бюджету (`.env` → `BUDGET_*`)
- Кожен: ключі API у своєму `.env`
- Ідея: фінал (Día de Muertos) і фільм випустити 31.10–2.11
