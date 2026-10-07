# STATUS

_Оновлено: 2026-10-07 · Claude A (режим «лабораторія промптів»: платне — лише люди руками)_

Дошка: [Producción](https://github.com/orgs/seriefactory-studio/projects/1)

## Критичний шлях до контрольної точки пт 16.10

Усе, чого немає в цій таблиці, — після 16.10.

| # | Крок | Коли | Хто | Стан | Блокує → |
|---|---|---|---|---|---|
| 1 | Схеми + облік витрат + каркас CLI (#10–#13) | вт 06.10 | A | ✅ | 2 |
| 2 | **Лабораторія промптів**: шаблони, `fabrica prompts`, переглядач, `fabrica lab log/approve` | ср 07.10 | A | ✅ (PR) | 3, 4 |
| 3 | **Кастинг руками**: пакет `casting` (обличчя, 1994, локації, голоси) → тест у Gemini / ElevenLabs → `lab log` → golden | ср–пт 07–09.10 | **люди** | ⏳ пакет готовий | 4, 7 |
| 4 | **Тест-пак руками**: пакет `test-pack` → тест у Dreamina / SYNTX / Replicate playground → `lab log` → golden | чт–пт 08–09.10 | **люди** | ⏳ пакет готовий | 7 (шаблони відео golden) |
| 5 | Етап **voice** (ElevenLabs) | — | A | ✅ код (#14); голоси — через кастинг (п.3) | 8 |
| 6 | **Розкадровка ч.2** (`part2_shotlist.md` + кошторис) | ср–чт 07–08.10 | A | ▶ наступний | 9 |
| 7 | Етап **video** без провайдера: черга, кеш, сухий режим, облік витрат; клієнт Replicate — після golden | чт–пн 08–12.10 | A | ▶ після п.6 | 8 |
| 8 | Англійські описи шотів ч.1 (`part1_prompts_en.yaml`) → пакет ч.1 → тести людей → генерація (AUTOMATION_ENABLED=true) → QC → assemble | пн–ср 12–14.10 | A + люди | — | 9 |
| 9 | **Ч.2** тим самим шляхом | ср–пт 14–16.10 | A + люди | — | контрольна точка |

Автоматика вимкнена (`AUTOMATION_ENABLED=false`): платне до golden роблять лише люди руками. Перед увімкненням —
ліміти `BUDGET_*` (160 / 60 / 900) і ключі в `.env` на Mac.

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
5. **FFmpeg на Mac зламаний** (Homebrew): у Terminal `brew upgrade ffmpeg`. Без нього не буде тривалостей, аніматика й монтажу.
6. **Голоси:** після ключа ElevenLabs — `uv run fabrica voices --search spanish` → обрати voice_id для 9 ролей ч.1.

## На перевірку для B (Windows)
- `uv sync` → `uv run pytest -q` на свіжому `main` (очікувано 215 passed, 2 live-тести Ollama — skip).
- `uv run fabrica --help | more` і `uv run fabrica shotlist la-garganta 1` у PowerShell: без кракозябр і помилок кодування.
- У сесії Claude з кореня `D:\project\serie-factory`: `git push origin main --force-with-lease` має заблокувати
  `guard_git.py`; `/permissions` → закрити #1.
