# HANDOFF — журнал передач

Кожна сесія завершується записом тут: `/handoff` → `collab log handoff …`. **Найновіші зверху.**
Повний промпт для партнера — у його скриньці `docs/comms/to-X.md`.

<!-- НОВІ ЗАПИСИ — ОДРАЗУ ПІД ЦИМ РЯДКОМ (найновіші зверху) -->

## 2026-10-06 09:26 +03:00 · Claude B · Рев'ю #10 виправлено, хук autostash (#12), каркас fabrica (#13)

- **Зроблено:**
  - промпт A від 06.10 07:32 — виконано пункти 1–3 (рев'ю #10, хук, каркас #2 і #3);
  - **PR #10:** усі знахідки рев'ю A (блокер, 2–11, дрібниці, A, B, C), тест на кожну; коментар-таблиця в PR;
  - **PR #12** `b/hook-autostash`: конфлікт autostash (відтворено тестом на старому хуку) і попередження «гілка ≠ main»;
  - **PR #13** `b/scaffold`: CLI `fabrica shotlist|validate|costs|schema`, `local_llm` (таймаут tags 3 с, обриви з'єднання, `length` без повторів).
- **Змінено:** гілки `b/schemas`, `b/costs` (merge `b/schemas` і `main`), `b/hook-autostash`, `b/scaffold`; у `main` — STATUS, comms.
- **Тести:** `b/schemas` 128 passed / 2 xfailed; `b/hook-autostash` 61 passed; `b/scaffold` 144 passed / 2 skipped / 2 xfailed (Windows).
- **Рішення:** записи в DECISIONS про схеми — після approve #10 (так просив A).
- **Відкрите / далі:** пункт 4 промпту (жива перевірка `/permissions`) не зроблено — сесію знову відкрито з `c:\project`; етап `fabrica script` чекає шаблонів A; `refs.yaml`.
- **Для партнера:** повторне рев'ю #10, рев'ю #11–#13, 2 правки розкадровки. Промпт → `docs/comms/to-A.md`.

---

## 2026-10-06 07:33 +02:00 · Claude A · Рев'ю PR #9 і #10, merge PR #8, контракт story.md

- **Зроблено:**
  - `/start`: 3 листи B прочитано.
  - **PR #9 — approve** (33 passed на macOS). Знайдено: конфлікт autostash хук не повідомляє (маркери `UU` + `stash@{0}`, а пише «успіх»). B змерджив PR #9 одразу після approve — п. 1 рев'ю лишається йому.
  - **PR #8 змерджено** (squash, `a29530c`), гілку `a/local-llm` видалено. Зауваження B 1–3 → його #2; п. 4 (інструкція JSON англійською) → моя зона, `fabrica/prompts/`.
  - **PR #10 — request-changes:**
    - дизайн («Відхилення» 1–6) — approve;
    - блокер — round-trip `shots.json` (`film_exclude` + `extra=forbid`);
    - важливо — правила shots по бітах, межі тизерів (SCREAMER на START, float 40,0), `check_shots` пропускає сцени, тихі втрати в `story.py` (`|` у тексті, `_`, мітки в коментарях, «3:17» у дужках, кирилична С);
    - з боку змісту — `Shot.location_id` (біт 5 ч.1 — дві локації), `supporting[].members` у `bible.py`.
    
    Код перевіряв агент `pr-reviewer`, 3 знахідки я відтворив сам.
  - **PLAYBOOK:** контракт формату `story.md` ↔ `fabrica/story.py`.
- **Змінено:** `docs/PLAYBOOK.md`, STATUS, MEMORY, comms; GitHub — рев'ю #9, #10, merge #8.
- **Тести:** main — 60 passed; PR #10 + main — 76 passed.
- **Рішення:** нових немає (рішення про схеми запише B після approve #10).
- **Відкрите / далі:** B — виправлення #10, #2, #3; A — повторне рев'ю #10, інструкція JSON у `fabrica/prompts/`, розкадровка ч.2; людина — кастинг, тест-пак, `/permissions` на Mac.
- **Для партнера:** ПРОМПТ ДЛЯ CLAUDE B → `docs/comms/to-B.md`.
## 2026-10-06 08:34 +03:00 · Claude B · Розкадровка ч.1 → shots.json і кошторис (#10), облік витрат (#11), merge #9

- **Зроблено:**
  - Промпт A від 06.10 (розкадровка → схеми, #3, PR #9).
  - **PR #9 перевірено наживо** (worktree, що відстає, + подвоєний FETCH_HEAD) і змерджено.
  - **PR #10 доповнено:** `Shot.tier` / `reuse` / `billed_seconds` / `has_dialogue_visible` / `dialogue[]`; конвертер `fabrica/shotlist.py`. `part1_shotlist.md` → 87 шотів без втрат, кошторис $126.02 / $145.26 збігся з розкадровкою по кожному tier (♻ 19 с, lip-sync 46 с). Правила PLAYBOOK тепер у `script_errors` / `shots_errors`. Виправлено баг: записаний `shots.json` не читався назад через `film_exclude`.
  - **PR #11** `b/costs`: SQLite-журнал витрат і ліміти `BUDGET_*`.
- **Змінено:** гілки `b/schemas` (`fabrica/models.py`, `shotlist.py`, `costs.py`, `bible.py`, `story.py`, тести) і `b/costs` (`fabrica/ledger.py`, `tests/test_ledger.py`); у `main` — STATUS, MEMORY, comms.
- **Тести:** `main` — 58 passed; `b/schemas` — 88 passed, 2 xfailed (strict: TEASER1 28 с і репліка 1.02); `b/costs` — 95 passed, 2 xfailed.
- **Рішення:** записів у DECISIONS ще немає — поля й поділ «модель / правила» чекають рев'ю A в #10.
- **Відкрите / далі:** #2 каркас (CLI, етап script на `local_llm`); схема `refs.yaml`; закрити #1 після живого `/permissions`; Ollama на D.
- **Для партнера:** `/review-pr 10`, `/review-pr 11`; виправити TEASER1 і репліку 1.02 у розкадровці. Промпт → `docs/comms/to-A.md`.

---

## 2026-10-06 07:00 +02:00 · Claude A · LA GARGANTA: логіка, календар, кастинг, розкадровка ч.1, тест-пак

- **Зроблено:**
  - **Логіку LA GARGANTA затверджено** й внесено: «підпис» сімох; персні бригади-трофеї (нова C13, у ч.1 замість персня — фото нічної зміни); рація на VHS; Beto у дзеркалі й у VHS-скрімері; склянка з сімома обличчями. ДНК, імена сімох і C12 прийнято. `bible.yaml` → approved (крім облич).
  - **Календар релізу:** ч.1 21.10 … ч.4 31.10, фільм 1–2.11; контрольна точка 16.10; ч.1 — лише коли готові 3 частини. Записано в DECISIONS, STATUS, `bible.yaml`.
  - **`docs/casting/la-garganta.md`:** EN-промпти для Gemini / Nano Banana — 6 героїв (base + лист 3/4, профіль, повний зріст, 3 емоції), сімка 1994 (+ мокрі варіанти; Tomás = ref Mateo), 9 локацій зі станами, реквізит-стіли для C05/C09/C12/C13/C07.
  - **`series/la-garganta/part1_shotlist.md`:** 87 шотів, 7:00, tier/♻/мітки/підказки. Відео ≈ $126 (оптимістично) – $145 (кліп ≥ 5 с), × 2 спроби; lip-sync — 46 с (не враховано).
  - **`series/la-garganta/test_pack.md`:** 5 вау-тестів Seedance — стартові кадри, промпти, критерії, запасні шляхи; ≈ $20.
  - **`COSTS.md`:** ціни Seedance 2.5 (0,23 / 0,11 $/с), план ч.1.
- **Змінено:** `series/la-garganta/*`, `docs/casting/`, `docs/` (DECISIONS, STATUS, MEMORY, COSTS); коміт `a045105` + цей.
- **Тести:** `uv run pytest -q` → 39 passed. Скрипт `story.md`: мітки, пари тизерів і всі 13 підказок (посіяні й розкриті) — OK.
- **Інцидент:** спільна тека стояла на гілці `a/local-llm` (її лишила інша сесія A), і мій коміт пам'яті ліг туди. Перенесено в `main` cherry-pick'ом, `a/local-llm` повернуто до стану origin (непушнутий коміт зайвий). Урок — у MEMORY.
- **Рішення:** логіка LA GARGANTA; календар релізу (→ DECISIONS).
- **Відкрите / далі:** людина — кастинг і тест-пак; A — розкадровка ч.2, шаблони промптів, `refs.yaml`; B — рев'ю PR #8, схеми під `part1_shotlist.md`, PR #9.
- **Для партнера:** ПРОМПТ ДЛЯ CLAUDE B → `docs/comms/to-B.md`.
## 2026-10-06 08:00 +03:00 · Claude B · PR #7 змерджено, рев'ю #8, схеми (#10) і FETCH_HEAD (#9)

- **Зроблено:**
  - `/start` вручну: 4 листи від A прочитано (READ).
  - **PR #7 змерджено**, `Closes #1` → `Refs #1`, бо живої перевірки `/permissions` не було.
  - **PR #8: approve** з 5 зауваженнями: збирання тестів ходить у мережу з таймаутом 600 с, обриви з'єднання не загорнуті, марні повтори при `length`, мова інструкції, `OLLAMA_MODELS` на Windows.
  - **PR #9** `b/fetch-race`: SessionStart → `git fetch` + `git rebase --autostash @{u}`; тести на справжніх git-репо.
  - **PR #10** `b/schemas`: `fabrica/models.py` (Script/Shots, правила міток, `check_refs`, `check_shots`), `fabrica/bible.py`, `fabrica/story.py` (розбір `story.md`, `check_script`), фікстура LA GARGANTA ч.1.
  - Поза репо: репо перенесено з C на `D:\project\serie-factory` (C у людини B переповнений).
- **Змінено:** `main`: comms, STATUS, MEMORY. Гілки: `b/fetch-race` (`.claude/hooks/session_start.py`, `tests/test_collab.py`), `b/schemas` (`fabrica/*`, `tests/test_models.py`, `tests/fixtures/`, `pyproject.toml`, `uv.lock`).
- **Тести:** `main` — 39 passed; `b/fetch-race` — 42 passed; `b/schemas` — 73 passed (Windows).
- **Рішення:** окремих записів у DECISIONS немає. Відхилення схем від пропозиції A описано в PR #10 на рев'ю. Після approve запишу в DECISIONS.
- **Відкрите / далі:** жива перевірка хуків і `/permissions` з кореня репо (#1); Ollama на D; #2 каркас fabrica; #3 облік витрат; deny-правила з прапорцем у кінці (`git push origin main --force`).
- **Для партнера:** `/review-pr 10`, `/review-pr 9`, merge #8. Промпт → `docs/comms/to-A.md`.

---

## 2026-10-05 13:38 +02:00 · Claude A · LA GARGANTA заповнено, рев'ю PR #7, Project «Producción»

- **Зроблено:**
  - `/start`: пошту B прочитано (READ).
  - **Рев'ю PR #7 → approve** (39 passed у worktree, без конфліктів). Зауваження: перед merge — жива перевірка `/permissions` або `Refs #1`; префіксні deny обходяться прапорцем у кінці; немає `Bash(cat .env)`.
  - **GitHub Project «Producción»** створено (https://github.com/orgs/seriefactory-studio/projects/1): #1 і PR #7 → Review, #2 і #4 → In progress, #3, #5, #6 → Ready.
  - **Біблія**: El Precio (блок а) → люди змінили формат і першу історію → El Precio в `series/_archive/`.
  - **LA GARGANTA** за текстом людини: `bible.yaml` (6 персонажів з візуальною ДНК, 9 локацій, правила світу, мова, табу, ризики), `story.md` (4 частини бітами, мітки, 7 тизерів, Película completa ≈27 хв, 5 питань логіки), `clues.md` (C01–C12, хибні сліди F1–F2, перевірка чесності).
  - Новий формат і мітка `SCREAMER` — у PROJECT_BRIEF, PLAYBOOK, ARCHITECTURE. Регіон — Мексика, м'який акцент; герої 18–19.
- **Змінено:** `series/`, `docs/` (BRIEF, PLAYBOOK, ARCHITECTURE, MEMORY, STATUS, DECISIONS), comms; коміти `56d3670`, `03585c1`, `530f700` + цей.
- **Тести:** `uv run pytest -q` → 30 passed. Скрипт перевірки `story.md`: у кожній частині рівно один HOOK_OPEN/MIDPOINT/CLIFF, SCREAMER ≤ 2, тизери в парах, ID підказок існують, заборонених слів немає.
- **Рішення:** 7 записів у DECISIONS: El Precio і мінісезони (обидва потім скасовано), формат 4 частини + фільм, LA GARGANTA, мітки + SCREAMER, Мексика, герої 18–19.
- **Відкрите / далі:** людина затверджує LA GARGANTA (питання логіки в `story.md`); B — merge PR #7, схеми `b/schemas`, гонка FETCH_HEAD у хуку; A — шаблони промптів script для LA GARGANTA, рев'ю схем.
- **Для партнера:** ПРОМПТ ДЛЯ CLAUDE B → `docs/comms/to-B.md`.

---

## 2026-10-05 10:47 +03:00 · Claude B · Windows-перевірка: система працює, PR #7 з PowerShell-дозволами

- **Зроблено:** перша сесія B. Windows-перевірка системи пам'яті (Issue #1): `uv sync`, тести, SessionStart і UserPromptSubmit (PowerShell і Git Bash), `collab` whoami/stamp/overview/digest. Усе працює, UTF-8 і BOM — OK. Пошту від A прочитано (READ), відповідь — `/msg` у `to-A.md`.
- **Змінено:** PR #7 `b/windows-setup`: PowerShell-двійники в `.claude/settings.json` і `allowed-tools` шести команд, `tests/test_settings.py`, README «Якщо щось не так». У `main`: STATUS, MEMORY, DECISIONS, comms.
- **Тести:** `uv run pytest -q` → 30 passed на `main` (Windows), 39 passed на `b/windows-setup`.
- **Рішення:** дозволи й заборони дублюємо для PowerShell (→ DECISIONS).
- **Відкрите / далі:** живий запуск хуків і слеш-команд у Claude Code не перевірено: сесію відкрито з батьківської теки `C:\project`, тому `.claude/` не підхопилась, і промпти цієї сесії хук не журналював. Наступна сесія B — у корені репо, далі #2 і #3.
- **Для партнера:** `/review-pr 7`. Повний промпт → `docs/comms/to-A.md`.

---

## 2026-10-05 09:31 +02:00 · Claude A · Система спільної пам'яті A↔B готова, лист і задачі для B

- **Зроблено:** система спільної пам'яті двох Claude:
  - `CLAUDE.md` (89 рядків) і пам'ять у `docs/`: BRIEF, ARCHITECTURE з 10 етапами, MEMORY, STATUS, HANDOFF, DECISIONS, COSTS, PLAYBOOK;
  - скриньки `docs/comms/` і журнал промптів людей `docs/prompts/`;
  - `.claude/hooks/collab.py` і два хуки, 6 слеш-команд, rules, агент `pr-reviewer`;
  - `.github/`: CODEOWNERS, шаблони, `scripts/setup_github.py`; README з першим запуском на Mac і Windows;
  - мітки `area:*` / `owner:*`, Issues #1–#6.
- **Змінено:** усе нове; коміт `2157009` + цей handoff-коміт у `main`.
- **Тести:** `uv run pytest -q` → 30 passed (macOS). Хуки запускаються через uv (Python 3.12) і системний python3 3.9. **На Windows не перевірено** — це Issue #1 для B.
- **Рішення:** 6 записів у DECISIONS: канал Git, `collab.py`, хуки через uv, порядок записів + `merge=union`, `fabrica/prompts/` у зоні A, медіа поза Git.
- **Відкрите / далі:** GitHub Project «Producción» (у токена нема scope `project`); Windows-перевірка (B, #1); біблія першого серіалу (A, #4).
- **Для партнера:** вітальний лист і ПРОМПТ ДЛЯ CLAUDE B — у `docs/comms/to-B.md`. GitHub B — `nuchay69-max`, а не `nychay69-max`.

---
