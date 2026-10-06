# STATUS

_Оновлено: 2026-10-06 07:32 +02:00 · Claude A_

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
- #2 каркас fabrica · #3 облік витрат — B, ще не почато · кастинг (A + людина).

## Заблоковано
- (нічого)

## Чекає на Claude B
- PR #10: виправлення за рев'ю A (блокер + 2–5, 7, 9–11) + `Shot.location_id`, `members` у `bible.py`, поля
  розкадровки (`tier`, `reuse`, lipsync). Після approve — рішення про схеми в DECISIONS.
- PR #8, зауваження 1–3 (таймаут `/api/tags`, обриви з'єднання, `done_reason=length`) → у #2.
- Хук: autostash-конфлікт мовчить (див. MEMORY → «Що не працює»); поточна гілка ≠ main → попередження.
- Жива перевірка хуків і `/permissions` з кореня репо (`D:\project\serie-factory`) → закрити #1.
- Ollama на Windows — після рішення людини B про місце на диску (C переповнений; моделі → `OLLAMA_MODELS` на D).
- #2 каркас fabrica · #3 облік витрат.

## Чекає на Claude A
- Повторне рев'ю PR #10 після виправлень.
- Перенести інструкцію JSON-генерації з `fabrica/local_llm.py` у `fabrica/prompts/` англійською (зауваження 4 до PR #8).
- Розкадровка ч.2; шаблони промптів `fabrica/prompts/script/` і `shots/` для LA GARGANTA.
- Після кастингу — `series/la-garganta/refs.yaml` (маніфест затверджених refs).
- Після тест-паку — оновити tier і кошторис `part1_shotlist.md`.

## Чекає на людей
- dimaShelest: кастинг облич і локацій у Gemini/Nano Banana (`docs/casting/la-garganta.md`), потім тест-пак Seedance.
- dimaShelest: на Mac відкрити `/permissions` і переконатися, що правила `PowerShell(...)` після PR #7 не дають помилок.
- Обоє: числа KPI в `PROJECT_BRIEF.md`; ліміти бюджету (`.env` → `BUDGET_*`): орієнтир ≈ $150–200 на частину лише за відео.
- Кожен: ключі API у своєму `.env`.
