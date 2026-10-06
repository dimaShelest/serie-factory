# STATUS

_Оновлено: 2026-10-06 08:34 +03:00 · Claude B_

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
- Система спільної пам'яті A↔B працює на macOS і Windows. Змерджено PR #7 (PowerShell-правила), #8 (локальна LLM,
  Ollama), #9 (SessionStart: fetch + rebase @{u}). Тести в main — 60.
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
- **PR #10** `b/schemas` (B): **changes requested** від A. Дизайн («Відхилення» 1–6) — approve. Блокер — round-trip
  `shots.json` (`film_exclude`). Важливі — правила shots по бітах, межі тизерів, тихі втрати в `story.py`
  (кирилична С, `|`, `_`, «3:17» у коментарі). Від змісту: `Shot.location_id`, `members` сімки в `bible.py`.
  **Стан на кінець сесії B 06.10:** уже виправлено блокер (round-trip, тест), HOOK/CLIFF по бітах, `members` у
  `bible.py`, поля розкадровки (`tier`, `reuse`, `billed_seconds`, `has_dialogue_visible`, `dialogue[]`), конвертер
  `part1_shotlist.md` → `shots.json` (кошторис $126.02 / $145.26 = як у розкадровці). Решта пунктів рев'ю — наступна сесія B.
- **PR #11** `b/costs` (B, база — #10): #3 облік витрат — SQLite-журнал, ліміти `BUDGET_*` (80 % / стоп / force).
- #2 каркас fabrica — B, ще не почато · кастинг (A + людина).

## Заблоковано
- (нічого)

## Чекає на Claude B
- PR #10: решта рев'ю A — SCREAMER на TEASER_START, межа 40,0, `check_shots` (пропущені сцени, мітки по сценах),
  `story.py` (кінець ч.4, `|` і `_` у тексті, мітки в коментарях, «3:17» у дужках, кирилична «С»). Після approve — DECISIONS.
- PR #8, зауваження 1–3 (таймаут `/api/tags`, обриви з'єднання, `done_reason=length`) → у #2.
- Хук: autostash-конфлікт мовчить (див. MEMORY → «Що не працює»); поточна гілка ≠ main → попередження.
- Жива перевірка хуків і `/permissions` з кореня репо (`D:\project\serie-factory`) → закрити #1.
- Ollama на Windows — після рішення людини B про місце на диску (C переповнений; моделі → `OLLAMA_MODELS` на D).
- #2 каркас fabrica. (#3 — у PR #11.)

## Чекає на Claude A
- Повторне рев'ю PR #10 після виправлень; рев'ю PR #11.
- Розкадровка ч.1: **TEASER1 = 28 с** (1.01 → 1.07), а треба 30–40; **1.02 «¡Chuy, graba, graba!…»** ≠ `story.md`
  «¡Graba, graba!…» — котра канонічна? (тести `xfail(strict)` у `tests/test_shotlist.py`, PR #10)
- Перенести інструкцію JSON-генерації з `fabrica/local_llm.py` у `fabrica/prompts/` англійською (зауваження 4 до PR #8).
- Розкадровка ч.2; шаблони промптів `fabrica/prompts/script/` і `shots/` для LA GARGANTA.
- Після кастингу — `series/la-garganta/refs.yaml` (маніфест затверджених refs).
- Після тест-паку — оновити tier і кошторис `part1_shotlist.md`.

## Чекає на людей
- dimaShelest: кастинг облич і локацій у Gemini/Nano Banana (`docs/casting/la-garganta.md`), потім тест-пак Seedance.
- dimaShelest: на Mac відкрити `/permissions` і переконатися, що правила `PowerShell(...)` після PR #7 не дають помилок.
- Обоє: числа KPI в `PROJECT_BRIEF.md`; ліміти бюджету (`.env` → `BUDGET_*`): орієнтир ≈ $150–200 на частину лише за відео.
- Кожен: ключі API у своєму `.env`.
