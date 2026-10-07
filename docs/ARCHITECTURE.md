# ARCHITECTURE — конвеєр serie-factory

> Чернетка v0 (Claude A, 2026-10-05). Код етапів пише Claude B (`fabrica/`), промпти й контент —
> Claude A (`fabrica/prompts/`, `series/`). Зміни архітектури — через `/decision`.

## Стек

Python 3.12 + uv · Typer (CLI `fabrica`) · Pydantic (моделі й валідація) · FFmpeg (монтаж) ·
SQLite (стан конвеєра й витрати) · R2 (медіа) · локальна LLM через Ollama (сценарій, шоти) · Seedance (відео) ·
ElevenLabs (голос) · IMAGE API (референси) · Sync (lip-sync) · YouTube Data API (публікація).

## 10 етапів

Кожен етап — окрема команда `fabrica <етап> <серіал> <серія>`. Етапи **ідемпотентні**: вхід хешується,
і повторний запуск без змін нічого не генерує й нічого не коштує.

| # | Етап | Вхід | Вихід | Сервіс |
|---|---|---|---|---|
| 1 | **script** | `bible.yaml`, біти частини зі `story.md`, `clues.md` | `script.json`: сцени, репліки (ES), ремарки, мітки бітів, підказки | Ollama: qwen3.5-abliterated 9B (локально) |
| 2 | **shots** | script | `shots.json`: шоти 1–10 с (`SCREAMER` — 0,5–2 с) — план, камера, дія, промпт відео, репліки, мітки, звукові удари | Ollama: qwen3.5-abliterated 9B (локально) |
| 3 | **refs** | біблія (персонажі, локації), shots | референс-зображення персонажів і локацій, кеш за хешем | IMAGE API |
| 4 | **voice** | script, голоси персонажів | `wav` на кожну репліку + тривалості (вони задають довжину шота) | ElevenLabs |
| 5 | **video** | shots, refs, voice | кліп на шот (image-to-video), lip-sync для шотів з діалогом | Seedance 2.5 (Replicate), Sync |
| 6 | **qc** | кліпи | оцінка кожного шота: тривалість, артефакти, консистентність облич, відповідність промпту | FFmpeg + vision-LLM |
| 7 | **repair** | шоти, що не пройшли qc | перегенерація (ліміт спроб і бюджету), інакше — позначка для людини | як у 3–5 |
| 8 | **assemble** | кліпи, аудіо, музика | частина 16:9 (6–8 хв): склейка, субтитри ES, −14 LUFS. Після 4-ї частини — **Película completa** 25–30 хв: частини без рекапів і «Continuará…» | FFmpeg |
| 9 | **cut** | частина + мітки `TEASER{n}_START` / `TEASER{n}_CUT_BEFORE` | тизери 9:16 30–40 с з обривом на хуку, reframe, впалені субтитри | FFmpeg |
| 10 | **publish** | частина / фільм, тизери, метадані ES | YouTube (+ Shorts) за розкладом: 2 частини на тиждень, фільм після 4-ї; майстри в R2; TikTok — поки вручну | YouTube API, R2 |

### Наскрізне: облік витрат

- Кожен платний виклик — через одну обгортку `Ledger.charge()` (`fabrica/ledger.py`): **атомарний резерв** оцінки
  з перевіркою лімітів (паралельні процеси не перевищать ліміт) → виклик → **підтвердження** фактом і `request_id`
  провайдера. Падіння посеред виклику лишає резерв витратою («незвірений», `Ledger.unsettled()`).
- Ліміти — `BUDGET_PER_EPISODE_USD`, `BUDGET_DAILY_USD`, `BUDGET_MONTHLY_USD` (`.env`). **Не задано → платні виклики
  заборонені**; без ліміту — лише явно `none`. Від 80 % — попередження, рівно 100 % — ще можна, понад — **зупинка**
  (продовжити — лише явний force, позначається в журналі). Межі дня й місяця — UTC.
- Журнал `output/fabrica.sqlite` — один на машину (SQLite, WAL, гроші в мікродоларах). Платні виклики — лише з Mac A.
- `uv run fabrica costs <slug> <N>` — кошторис і ліміти; `docs/COSTS.md` — людський підсумок, оновлюється на `/handoff`.

## Лабораторія промптів (режим до golden) — рушій промптів v2

```
series/<slug>/bible.yaml, story.md          сюжет (укр.)
series/<slug>/prompt_en.yaml                англійський шар: ДНК, теги для відео, стани, локації (час доби, варіанти),
                                            стилі (фото / відео / VHS), правила кадру
series/<slug>/part<N>_prompts_en.yaml       режисерська схема шотів (оверлей v2): перший кадр, дія + кінцевий стан, камера,
                                            звук, ракурси людей, стан сцени, кліпи, handoff, вікно монтажу
series/<slug>/lab/{sequences,overrides,lessons}.yaml   послідовності (first30 + бюджет), правки зі студії, уроки
        │  fabrica/shotspec.py — ShotSpec (shots.json + оверлей + стан сцени + правки), кліпи за профілем генерації
        ▼
fabrica/compile.py — компілятори під модель: Nano Banana (порядкові референси), Seedance 2.5 (i2v / перший+останній
        кадр / t2v, порядок блоків ByteDance), ElevenLabs v4 / Voice Design; уроки; маршрут обличчя
        │  prompts/templates/** (версії, sha → golden) · prompts/providers.yaml (схеми API, ціни, профілі генерації)
        │  prompts/lint.yaml (слова, що ламають генерацію)
        ▼
Item: route + payload (тіло API, файли — «ref:<id>») + step (1–7) + needs  →  fabrica prompts (пакет + переглядач)
                                                                         →  fabrica studio (локальний застосунок)
        │  люди тестують руками → lab log → lab/results.yaml + media/lab/ → lab approve → prompts/golden.yaml
        ▼
етапи video / voice — той самий payload (лише golden), платні виклики через Ledger.charge()
```

- **Профіль генерації** (`prompts/providers.yaml → generation`): `lab-2.5` — лабораторія на одному платному акаунті
  (Seedance 2.5, 720p, кліп = шот 4–10 с, dropshot); `replicate-2.5` — автоматика з тими самими моделлю й роздільністю.
  `GENERATION_PROFILE` у `.env` перевизначає.
- **Маршрут відео:** обличчя до камери (`face: clear`) → `cloudflare:bytedance/seedance-2.5` з `use_virtual_avatar`
  (Seedance 2.x на Replicate відхиляє фотореальні обличчя, навіть згенеровані); решта → `replicate:bytedance/seedance-2.5`.
- **Негативу немає** в жодному API Seedance / Nano Banana: заборони — сталими реченнями в самому промпті («No subtitles,
  no on-screen text.», «No BGM; only ambience and action sounds.»), решта — позитивними формулюваннями.
- **Студія** (`fabrica/studio.py` + `fabrica/studio_ui/`): лише 127.0.0.1; стан послідовності, прогрес
  (`lab/progress.yaml`), запис результатів, бюджет, «Редагувати промпт» → `fabrica/rewrite.py` (Ollama; `REWRITE_BACKEND=
  claude` — Claude API, необов'язкова залежність `uv sync --extra claude`) → overrides + уроки.
- `AUTOMATION_ENABLED=false` за замовчуванням: `Ledger.reserve()` відмовляє будь-якому платному виклику.
- Кожен результат прив'язаний до `id@версії` шаблону, sha шаблону і sha промпту (payload + маршрут). Сід — стабільний.

## Дані

```
series/<slug>/               # Git, зона A: біблія, сюжет бітами, підказки
  bible.yaml  story.md  clues.md
fabrica/prompts/<етап>/      # Git, зона A: шаблони промптів генерації
fabrica/                     # Git, зона B: код етапів, CLI, моделі
output/<slug>/part<N>/        # НЕ в Git: script.json, shots.json + теки етапів voice/ video/ qc/ assemble/ cut/
output/<slug>/film/          # НЕ в Git: Película completa; майстри → R2
output/fabrica.sqlite        # НЕ в Git: журнал витрат (один на машину)
```

Між етапами передаються JSON-файли за Pydantic-схемами (`fabrica/models.py`), щоб будь-який етап
можна було перезапустити окремо. Схеми `script.json` і `shots.json` погоджують A і B: A відповідає
за зміст, B — за код.

## Відкриті питання

- TODO: конкретні моделі й тарифи Seedance / IMAGE API / Sync → `docs/COSTS.md`.
- TODO: TikTok — API чи ручне завантаження на старті.
- TODO: чи потрібен dashboard з першого місяця, чи вистачить `fabrica status`.
