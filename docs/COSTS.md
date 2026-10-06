# COSTS — витрати й ліміти

> Джерело правди (коли з'явиться) — SQLite фабрики, звіт `fabrica costs`.
> Цей файл — людський підсумок: оновлюється на `/handoff` і в `/status`.

## Ліміти

| Ліміт | USD | Де задано |
|---|---|---|
| На серію | TODO | `.env` → `BUDGET_PER_EPISODE_USD` |
| На день | TODO | `.env` → `BUDGET_DAILY_USD` |
| На місяць | TODO | `.env` → `BUDGET_MONTHLY_USD` |

- **Не задано → платні виклики заборонені.** Без ліміту — лише явно `none` у `.env`.
- Від 80 % — попередження; рівно 100 % — ще можна; понад 100 % — зупинка (продовжити — лише явний force, він
  позначається в журналі як `forced`).
- День і місяць рахуємо за **UTC**. Журнал `output/fabrica.sqlite` — **один на машину**, тож платні виклики (Seedance,
  ElevenLabs, IMAGE, Sync) робимо **лише з Mac A**; у B ключів немає.
- Перевірка: `uv run fabrica costs la-garganta 1` (кошторис + уже витрачене + ліміти).

## Тарифи провайдерів

Планувальний коефіцієнт: **× 2 спроби** на кожен згенерований шот (repair, невдалі дублі).

| Провайдер | Етап | Одиниця | Ціна, USD | Перевірено (дата, джерело) |
|---|---|---|---|---|
| Claude API | script, shots, qc | 1M токенів in/out | TODO | |
| IMAGE API | refs, repair | зображення | TODO | |
| ElevenLabs | voice | 1K символів | TODO | |
| Seedance 2.5 | video, repair | секунда відео 720p (hero) | ≈ 0,23 | 2026-10-06, dimaShelest — звірити з першим рахунком |
| Seedance 2.5 | video, repair, found-footage | секунда відео 480p (secondary) | ≈ 0,11 | 2026-10-06, dimaShelest — звірити з першим рахунком |
| Sync | video (lip-sync) | секунда | TODO | |
| Cloudflare R2 | publish | ГБ-місяць | TODO | |

## Підсумок по серіях

| Дата | Серіал / серія | script | refs | voice | video | repair | Разом | Ліміт | Примітка |
|---|---|---|---|---|---|---|---|---|---|
| план | LA GARGANTA · ч.1 (тільки відео Seedance, × 2 спроби) | | | | $126–145 | | $126–145 | TODO | `series/la-garganta/part1_shotlist.md`; без lip-sync (46 с), голосу й стілів |

## Тестові та інші витрати

| Дата | Хто | Що | USD |
|---|---|---|---|
| — | — | — | |
