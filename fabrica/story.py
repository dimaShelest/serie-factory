"""Розбір series/<slug>/story.md: таблиці бітів кожної частини з мітками, часом, підказками й репліками.

Формат story.md — зона Claude A (див. «Формат і умовні позначки» у самому файлі). Фабрика використовує розбір,
щоб перевірити, що script.json не загубив жодного біта, мітки, підказки чи репліки (check_script).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from fabrica.models import Mark, Script, Unit, label_errors

PART_RE = re.compile(r"^## Частина (\d+)\b", re.M)
TIME_RE = re.compile(r"(\d+):(\d{2})")
LABEL_RE = re.compile(r"HOOK_OPEN|MIDPOINT|SCREAMER|CLIFF|TEASER\d+_(?:START|CUT_BEFORE)")
QUOTE_RE = re.compile(r"«([^»]+)»")
ITALIC_RE = re.compile(r"_([^_]+)_")


@dataclass
class Beat:
    n: int
    start_s: float
    end_s: float
    segment: str
    text: str
    labels: list[tuple[str, float | None]] = field(default_factory=list)   # (TEASER1_START, 0.0)
    planted: set[str] = field(default_factory=set)
    revealed: set[str] = field(default_factory=set)
    quotes: list[str] = field(default_factory=list)                      # іспанські репліки з _«…»_


def seconds(mmss: str) -> float:
    m = TIME_RE.search(mmss)
    if not m:
        raise ValueError(f"не час: {mmss!r}")
    return int(m.group(1)) * 60 + int(m.group(2))


def _labels(cell: str) -> list[tuple[str, float | None]]:
    out = []
    for group in cell.split("·"):           # `TEASER1_CUT_BEFORE` + `SCREAMER` (обличчя, ~0:33)
        paren = re.findall(r"\(([^)]*)\)", group)
        times = TIME_RE.findall(paren[-1]) if paren else []
        at = int(times[-1][0]) * 60 + int(times[-1][1]) if times else None   # «на 3:17, ~3:25» → 3:25
        out += [(key, at) for key in LABEL_RE.findall(group)]
    return out


def _segment(text: str, labels_cell: str) -> str:
    if "рекап" in labels_cell.lower():
        return "recap"
    if "end card" in labels_cell.lower():
        return "end_card"
    if text.startswith("Назва"):
        return "title"
    return "main"


def parse(path: Path) -> dict[int, list[Beat]]:
    """{номер частини: біти по порядку}."""
    text = path.read_text(encoding="utf-8-sig")
    heads = list(PART_RE.finditer(text))
    parts = {}
    for k, h in enumerate(heads):
        chunk = text[h.end(): heads[k + 1].start() if k + 1 < len(heads) else len(text)]
        beats = []
        for row in chunk.splitlines():
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) != 5 or not cells[0].isdigit():
                continue
            num, span, body, labels_cell, clues_cell = cells
            start, end = (seconds(t) for t in re.split(r"[–-]", span))
            segment = _segment(body, labels_cell)
            beat = Beat(int(num), start, end, segment, body, _labels(labels_cell))
            beat.planted = set(re.findall(r"\+(C\d{2})", clues_cell)) | set(
                re.findall(r"хибний слід (F\d+)", clues_cell))
            beat.revealed = set(re.findall(r"!(C\d{2})", clues_cell)) | set(
                re.findall(r"(F\d+) спростовано", clues_cell))
            if segment == "main":
                beat.quotes = [q.strip() for it in ITALIC_RE.findall(body) for q in QUOTE_RE.findall(it)]
            beats.append(beat)
        parts[int(h.group(1))] = beats
    return parts


def part_errors(beats: list[Beat]) -> list[str]:
    """Правила міток PLAYBOOK для однієї частини story.md (ті самі, що для script.json)."""
    units = [Unit(b.segment, b.start_s, b.end_s, i) for i, b in enumerate(beats)]
    marks = [Mark(key, i, at, at) if at is not None else Mark(key, i, b.start_s, b.end_s)
             for i, b in enumerate(beats) for key, at in b.labels]
    return label_errors(units, marks, tolerance=0.0)


def check_script(script: Script, beats: list[Beat]) -> list[str]:
    """script.json відповідає story.md біт у біт: сегменти, час, мітки, підказки, репліки."""
    if len(script.scenes) != len(beats):
        return [f"бітів у story.md {len(beats)}, а сцен у script.json {len(script.scenes)}"]
    errors = []
    for b, s in zip(beats, script.scenes):
        where = f"біт {b.n} / {s.id}"
        if s.segment != b.segment:
            errors.append(f"{where}: сегмент {s.segment} ≠ {b.segment}")
        if (s.approx_start_s, s.approx_end_s) != (b.start_s, b.end_s):
            errors.append(f"{where}: час {s.approx_start_s}–{s.approx_end_s} ≠ {b.start_s}–{b.end_s}")
        order = lambda x: (x[0], -1.0 if x[1] is None else x[1])  # noqa: E731
        got = sorted(((lb.key, lb.approx_s) for lb in s.labels), key=order)
        if got != sorted(b.labels, key=order):
            errors.append(f"{where}: мітки {got} ≠ {b.labels}")
        if set(s.clues.planted) != b.planted or set(s.clues.revealed) != b.revealed:
            errors.append(f"{where}: підказки +{sorted(s.clues.planted)} !{sorted(s.clues.revealed)} "
                          f"≠ +{sorted(b.planted)} !{sorted(b.revealed)}")
        lines = [ln.text_es for ln in s.lines]
        errors += [f"{where}: бракує репліки «{q}»" for q in b.quotes if q not in lines]
    return errors
