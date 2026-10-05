# COSTS — витрати й ліміти

> Джерело правди (коли з'явиться) — SQLite фабрики, звіт `fabrica costs`.
> Цей файл — людський підсумок: оновлюється на `/handoff` і в `/status`.

## Ліміти

| Ліміт | USD | Де задано |
|---|---|---|
| На серію | TODO | `.env` → `BUDGET_PER_EPISODE_USD` |
| На день | TODO | `.env` → `BUDGET_DAILY_USD` |
| На місяць | TODO | `.env` → `BUDGET_MONTHLY_USD` |

Від 80 % ліміту — попередження, від 100 % — зупинка конвеєра.

## Тарифи провайдерів

| Провайдер | Етап | Одиниця | Ціна, USD | Перевірено (дата, джерело) |
|---|---|---|---|---|
| Claude API | script, shots, qc | 1M токенів in/out | TODO | |
| IMAGE API | refs, repair | зображення | TODO | |
| ElevenLabs | voice | 1K символів | TODO | |
| Seedance | video, repair | секунда відео | TODO | |
| Sync | video (lip-sync) | секунда | TODO | |
| Cloudflare R2 | publish | ГБ-місяць | TODO | |

## Підсумок по серіях

| Дата | Серіал / серія | script | refs | voice | video | repair | Разом | Ліміт | Примітка |
|---|---|---|---|---|---|---|---|---|---|
| — | — | | | | | | | | |

## Тестові та інші витрати

| Дата | Хто | Що | USD |
|---|---|---|---|
| — | — | — | |
