# fabrica/ — конвеєр (зона Claude B)

Python-пакет з CLI `fabrica` (Typer): 10 етапів — script, shots, refs, voice, video, qc, repair,
assemble, cut, publish — і наскрізний облік витрат. Опис — `docs/ARCHITECTURE.md`.

Каркас — Issue «Каркас fabrica» (Claude B). Виняток: `fabrica/prompts/` — шаблони промптів
генерації, зона Claude A (див. `.github/CODEOWNERS`).
