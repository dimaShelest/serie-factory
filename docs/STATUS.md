# STATUS

_Оновлено: 2026-10-06 · Claude A (новий режим: A будує все, B тестує на Windows)_

Дошка: [Producción](https://github.com/orgs/seriefactory-studio/projects/1)

## Критичний шлях до контрольної точки пт 16.10

Усе, чого немає в цій таблиці, — після 16.10.

| # | Крок | Коли | Хто | Стан | Блокує → |
|---|---|---|---|---|---|
| 1 | Схеми script/shots + облік витрат (#10, #11 → #13) | вт 06.10 | A | ✅ змерджено | 2 |
| 2 | Каркас fabrica (#13): CLI shotlist / validate / costs / schema | вт 06.10 | A | ✅ змерджено (решта #2 — з етапами 5–6) | 5, 6 |
| 3 | **Кастинг облич і плит** у Gemini / Nano Banana → `refs.yaml` | вт–ср 06–07.10 | **люди** + A | ⏳ чекає людей | 4, 6 |
| 4 | **Тест-пак Seedance** (5 вау-кадрів, ≈ $20) | чт 08.10 | **люди** (оплата) + A | ⏳ чекає оплати й п.3 | 6 (tier, мін. кліп, ціни) |
| 5 | Етап **voice** (ElevenLabs): голоси персонажів, wav на репліку, тривалості | ср–пт 07–09.10 | A | ▶ наступний | 6 (lip-sync), 8 |
| 6 | Етап **video** (Seedance 2.5): черга, кеш, ліміти, сухий режим, аніматик 480p | пт–пн 09–12.10 | A | — | 7 |
| 7 | **QC** (тривалість, артефакти, ДНК облич) + repair | пн–вт 12–13.10 | A | — | 8 |
| 8 | **assemble ч.1** (FFmpeg: склейка, субтитри ES, −14 LUFS) | вт–ср 13–14.10 | A | — | 9 |
| 9 | **Ч.2**: розкадровка → voice → video → QC → assemble | ср–пт 14–16.10 | A | — | контрольна точка |

Перед першим платним викликом (п.4–6) потрібні **ліміти `BUDGET_*` і ключі API в `.env` на Mac**. Без лімітів фабрика
платні виклики не робить.

## Календар релізу

| Дата | Що | Умова |
|---|---|---|
| **пт 16.10** | Контрольна точка | ч.1–2 готові, інакше зсуваємо весь календар |
| **ср 21.10** | Ч.1 «El Reto» | лише якщо готові 3 частини |
| **сб 24.10** | Ч.2 «Lo Que Pesa» | |
| **ср 28.10** | Ч.3 «Los Siete» | ч.4 готова до 28.10 |
| **сб 31.10** | Ч.4 «La Garganta» (Día de Muertos) | |
| **нд–пн 1–2.11** | Película completa | з готових частин |

## Зроблено (06.10)
- Новий режим ролей: CLAUDE.md, DECISIONS, MEMORY, CODEOWNERS (`* @dimaShelest`).
- Змерджено #10 (схеми), #12 (хук: конфлікт autostash і попередження «не на main»), #13 (каркас CLI + облік витрат
  з #11 після виправлень рев'ю). Відкритих PR немає. Тести — 215.
- Захист: `guard_git.py` (PreToolUse) блокує force-push / `--force-with-lease` / `reset --hard` / `clean -f`.
- LA GARGANTA: «¡Chuy, graba!» + C14; T1 = 32 с; групи `los_cuatro` / `los_siete`; приклад `refs.yaml`;
  мовці реплік 3.06 і 8.17 у розкадровці.
- Звіт 001 за листи A↔B №5–14 (`docs/comms/reports/001.md`).

## Після 16.10
- PR з автозвітами кожні 10 листів (`collab report-*`); Ollama на D: у B; dashboard; KPI; решта Issue #2
  (pydantic-settings, заглушки етапів, runs/stage_runs) — якщо не знадобиться раніше.
- `collab log` — вставляти за часом, а не зверху (merge=union переплутує порядок DECISIONS).
- `fabrica/local_llm.py` — перевести на спільний `fabrica/config.py`.

## Чекає на людей
1. **Ліміти бюджету** в `.env` на Mac: `BUDGET_PER_EPISODE_USD`, `BUDGET_DAILY_USD`, `BUDGET_MONTHLY_USD`
   (пропозиція A: 200 / 250 / 900; відео однієї частини ≈ $127–146).
2. **Кастинг** (06–07.10): за `docs/casting/la-garganta.md`, першим — Mateo.
3. **Оплата Seedance** і ключ `SEEDANCE_*` → тест-пак 08.10. **Ключ ElevenLabs** → етап voice.
4. dimaShelest: на Mac відкрити `/permissions` — чи немає помилок від правил `PowerShell(...)`.

## На перевірку для B (Windows)
- `uv sync` → `uv run pytest -q` на свіжому `main` (очікувано 215 passed, 2 live-тести Ollama — skip).
- `uv run fabrica --help | more` і `uv run fabrica shotlist la-garganta 1` у PowerShell: без кракозябр і помилок кодування.
- У сесії Claude з кореня `D:\project\serie-factory`: `git push origin main --force-with-lease` має заблокувати
  `guard_git.py`; `/permissions` → закрити #1.
