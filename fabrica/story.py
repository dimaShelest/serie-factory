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
H2_RE = re.compile(r"^## ", re.M)
BEAT_ROW_RE = re.compile(r"^\|\s*\d+\s*\|")                       # рядок, схожий на біт
TIME_RE = re.compile(r"(\d+):(\d{2})")
LABEL_RE = re.compile(r"`(HOOK_OPEN|MIDPOINT|SCREAMER|CLIFF|TEASER\d+_(?:START|CUT_BEFORE))`")
TOKEN_RE = re.compile(r"`([A-Z][A-Z0-9_]*)`")
ITALIC_RE = re.compile(r"(?<!\w)_(.+?)_(?!\w)|(?<![\w*])\*(?!\*)(.+?)(?<!\*)\*(?![\w*])")
CLUE_TOKENS = [
    (re.compile(r"^([+!])(C\d{2})(?:\s*→.*)?$"), lambda m: (m.group(1), m.group(2))),
    (re.compile(r"^хибний слід (F\d+)$"), lambda m: ("+", m.group(1))),
    (re.compile(r"^(F\d+) спростовано$"), lambda m: ("!", m.group(1))),
]


class StoryFormatError(ValueError):
    """story.md не за форматом: фабрика не вгадує, а зупиняється з місцем помилки."""


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


def quotes(text: str) -> list[str]:
    """Верхньорівневі «…» з урахуванням вкладених «» усередині."""
    out, depth, start = [], 0, 0
    for i, ch in enumerate(text):
        if ch == "«":
            if depth == 0:
                start = i + 1
            depth += 1
        elif ch == "»" and depth:
            depth -= 1
            if depth == 0:
                out.append(text[start:i].strip())
    return out


def _labels(cell: str, start: float, end: float, where: str) -> list[tuple[str, float | None]]:
    """`TEASER1_CUT_BEFORE` + `SCREAMER` (обличчя, ~0:33) → [(TEASER1_CUT_BEFORE, 33), (SCREAMER, 33)].

    Час — лише `~m:ss` або дужки, де є тільки час («(0:00)»); «на 3:17» у коментарі — не час мітки.
    """
    out = []
    for token in TOKEN_RE.findall(cell):
        if not LABEL_RE.fullmatch(f"`{token}`"):
            raise StoryFormatError(f"{where}: невідома мітка `{token}` (перелік — docs/PLAYBOOK.md)")
    for group in cell.split("·"):
        parens = re.findall(r"\(([^)]*)\)", group)
        approx = [m for p in parens for m in re.findall(r"~(\d+):(\d{2})", p)]
        exact = [m for p in parens if (m := re.fullmatch(r"\s*(\d+):(\d{2})\s*", p))]
        if len(approx) > 1 or (not approx and len(exact) > 1):
            raise StoryFormatError(f"{where}: кілька часів для однієї мітки: {group.strip()}")
        mm = approx[0] if approx else exact[0].groups() if exact else None
        at = int(mm[0]) * 60 + int(mm[1]) if mm else None
        if at is not None and not start <= at <= end:
            raise StoryFormatError(f"{where}: час мітки {at // 60}:{at % 60:02d} поза бітом")
        out += [(key, at) for key in LABEL_RE.findall(group)]
    return out


def _clues(cell: str, where: str) -> tuple[set[str], set[str]]:
    planted, revealed = set(), set()
    for token in (t.strip() for t in cell.split("·")):
        if token in ("", "—"):
            continue
        if re.search(r"[СсЕе]\d", token):
            raise StoryFormatError(f"{where}: «{token}» — кирилична літера в ID підказки (треба латинські C / F)")
        for regex, pick in CLUE_TOKENS:
            if m := regex.match(token):
                sign, clue = pick(m)
                (planted if sign == "+" else revealed).add(clue)
                break
        else:
            raise StoryFormatError(f"{where}: незрозумілий токен підказки «{token}» "
                                   "(очікую +C05 / !C05 / «хибний слід F1» / «F1 спростовано»)")
    return planted, revealed


def _segment(text: str, labels_cell: str) -> str:
    cell = labels_cell.strip().lower()
    if cell == "рекап":
        return "recap"
    if cell == "end card":
        return "end_card"
    if text.startswith("Назва"):
        return "title"
    return "main"


def _lines(body: str, where: str) -> list[str]:
    spans = [a or b for a, b in ITALIC_RE.findall(body)]
    found = [q for s in spans for q in quotes(s)]
    expected = len(re.findall(r"(?<!\w)[_*](?!\*)«", body))
    if len([s for s in spans if s.lstrip().startswith("«")]) != expected:
        raise StoryFormatError(f"{where}: курсив з репліками розібрано не повністю — перевір `_` у тексті")
    return found


def parse(path: Path) -> dict[int, list[Beat]]:
    """{номер частини: біти по порядку}. Не за форматом → StoryFormatError з номером рядка."""
    text = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    h2 = [m.start() for m in H2_RE.finditer(text)]
    parts = {}
    for h in PART_RE.finditer(text):
        part = int(h.group(1))
        end = next((p for p in h2 if p > h.start()), len(text))     # до наступного «## », а не до кінця файлу
        first_line = text.count("\n", 0, h.start()) + 1
        beats = []
        for offset, row in enumerate(text[h.start():end].splitlines()):
            if not BEAT_ROW_RE.match(row.strip()):
                continue
            where = f"story.md:{first_line + offset} (ч.{part})"
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) != 5:
                raise StoryFormatError(f"{where}: у рядку біта {len(cells)} комірок замість 5 (`|` у тексті?)")
            num, span, body, labels_cell, clues_cell = cells
            try:
                start, stop = (seconds(t) for t in re.split(r"[–—-]", span))
            except ValueError:
                raise StoryFormatError(f"{where}: час біта «{span}» — очікую 0:00–0:35") from None
            segment = _segment(body, labels_cell)
            beat = Beat(int(num), start, stop, segment, body, _labels(labels_cell, start, stop, where))
            beat.planted, beat.revealed = _clues(clues_cell, where)
            if segment == "main":
                beat.quotes = _lines(body, where)
            beats.append(beat)
        parts[part] = beats
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
