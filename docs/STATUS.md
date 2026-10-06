# STATUS

_Оновлено: 2026-10-06 08:00 +03:00 · Claude B_

Дошка: [Producción](https://github.com/orgs/seriefactory-studio/projects/1)

## Календар LA GARGANTA

| Дата | Що | Хто | Умова / статус |
|---|---|---|---|
| вт–ср 06–07.10 | Кастинг облич, плити локацій, реквізит-стіли | dimaShelest + A | промпти — `docs/casting/la-garganta.md` |
| чт 08.10 | Тест-пак Seedance (5 вау-кадрів, ≈ $20) | dimaShelest + A | `series/la-garganta/test_pack.md` |
| 08–15.10 | Генерація й монтаж ч.1 → ч.2 | A + фабрика B | розкадровка ч.1 — `part1_shotlist.md`; ч.2 — TODO |
| **пт 16.10** | **Контрольна точка** | обоє | ч.1–2 не готові → зсуваємо весь календар |
| 17–20.10 | Ч.3 | A + фабрика B | ч.1 не публікуємо, доки не готові 3 частини |
| **ср 21.10** | **Ч.1 «El Reto»** | publish | |
| **сб 24.10** | **Ч.2 «Lo Que Pesa»** | publish | |
| **ср 28.10** | **Ч.3 «Los Siete»** | publish | ч.4 має бути готова до 28.10 |
| **сб 31.10** | **Ч.4 «La Garganta»** (Día de Muertos) | publish | |
| **нд–пн 1–2.11** | **Película completa** | publish | збираємо з готових частин |

## Зроблено
- Система спільної пам'яті A↔B працює на macOS і Windows. PR #7 (PowerShell-правила) змерджено. Тести в main — 39.
  Issue #1 відкритий до живої перевірки `/permissions` у сесії B з кореня репо.
- GitHub Project «Producción»; формат «4 частини + Película completa»; мітки бітів з `SCREAMER`; Мексика, герої 18–19.
- **LA GARGANTA** затверджено (крім облич):
  - логіка: «підпис» сімох, персні-трофеї C13, рація, Beto у дзеркалі, склянка;
  - 13 підказок C01–C13, календар релізу.
- **Виробництво:**
  - кастинг-промпти (6 героїв, сімка 1994, 9 локацій, реквізит);
  - розкадровка ч.1 (87 шотів, 7:00; відео ≈ $126–145);
  - тест-пак Seedance;
  - ціни Seedance у `COSTS.md`.

## В роботі
- **PR #8** `a/local-llm` (A): approve від B (46 passed, 2 skip на Windows), 5 незаблокувальних зауважень. Мерджить A.
- **PR #9** `b/fetch-race` (B): SessionStart → `git fetch` + `git rebase --autostash @{u}`. Чекає рев'ю A.
- **PR #10** `b/schemas` (B): Pydantic-схеми `script.json` / `shots.json`, правила міток, перевірка `story.md`
  без втрат (ч.1 — фікстура). 73 passed. Писалось до `part1_shotlist.md` і C13 — B оновить. Чекає рев'ю A («Відхилення»).
- #2 каркас fabrica · #3 облік витрат — B, ще не почато · кастинг (A + людина).

## Заблоковано
- (нічого)

## Чекає на Claude B
- PR #10: додати колонки `part1_shotlist.md` (tier, ♻) у `shots.json`; перевірити схеми на оновленому `story.md` (C13).
- Жива перевірка хуків і `/permissions` з кореня репо (`D:\project\serie-factory`) → закрити #1.
- Ollama на Windows — після рішення людини B про місце на диску (C переповнений; моделі → `OLLAMA_MODELS` на D).
- #2 каркас fabrica · #3 облік витрат.

## Чекає на Claude A
- `/review-pr 10` (схеми) і `/review-pr 9` (FETCH_HEAD); merge PR #8.
- Розкадровка ч.2; шаблони промптів `fabrica/prompts/script/` і `shots/` для LA GARGANTA.
- Після кастингу — `series/la-garganta/refs.yaml` (маніфест затверджених refs).
- Після тест-паку — оновити tier і кошторис `part1_shotlist.md`.

## Чекає на людей
- dimaShelest: кастинг облич і локацій у Gemini/Nano Banana (`docs/casting/la-garganta.md`), потім тест-пак Seedance.
- dimaShelest: на Mac відкрити `/permissions` і переконатися, що правила `PowerShell(...)` після PR #7 не дають помилок.
- Обоє: числа KPI в `PROJECT_BRIEF.md`; ліміти бюджету (`.env` → `BUDGET_*`): орієнтир ≈ $150–200 на частину лише за відео.
- Кожен: ключі API у своєму `.env`.
