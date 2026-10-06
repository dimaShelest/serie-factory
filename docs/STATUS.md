# STATUS

_Оновлено: 2026-10-06 09:42 +03:00 · Claude B_

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
**Ролі з 06.10 (від людини B; лист A в Git ще не з'явився):** Claude A веде весь проєкт і всі зони коду;
Claude B — тестувальник і рев'юер на Windows. Відкриті PR B передано A (гілки тепер його):
- **PR #10** `b/schemas` — виправлено за рев'ю A, чекає повторного рев'ю. Win: 128 passed, 2 xfailed.
- **PR #11** `b/costs` (база #10) — облік витрат (#3).
- **PR #12** `b/hook-autostash` (база main) — хук: конфлікт autostash, «гілка ≠ main». Win: 61 passed.
- **PR #13** `b/scaffold` (база #11) — каркас #2, CLI `fabrica`. Win: 144 passed, 2 xfailed.
  Порядок merge: #10 → #11 → #13; #12 — окремо.
- Кастинг (A + людина).

## Заблоковано
- (нічого)

## Чекає на Claude B
- Тестування на Windows і рев'ю PR A (нових задач з коду B не бере).
- Жива перевірка хуків і `/permissions` з кореня репо (`D:\project\serie-factory`) → закрити #1.

## Чекає на Claude A
- Запушити лист і рішення про зміну ролей (у Git їх ще немає).
- PR #10–#13 тепер твої: повторне рев'ю / доведення й merge (#10 → #11 → #13, #12 окремо).
- Етап `fabrica script`, схема `refs.yaml` — колишні задачі B.
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
