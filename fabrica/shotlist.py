"""Конвертер розкадровки series/<slug>/partN_shotlist.md (зона A, markdown) → shots.json.

Розкадровку пише людина / Claude A, тож колонки вільні. Тут — явні правила розбору; усе, що не лягло в поля
схеми, іде в `notes`, щоб нічого не загубити. Що не вдалося розібрати — у списку issues (порожній = без втрат).

Звукові ефекти розкадровка не пише окремо, тому їх виводимо з тексту: SCREAMER → `sting` (за визначенням
PLAYBOOK), «тиша» / «наростання» в дії → `silence` / `riser`.
"""

from __future__ import annotations

import re
from pathlib import Path

from fabrica.bible import Bible
from fabrica.models import Script

HEADER_RE = re.compile(r"^### Біт (\d+)\b(.*)$", re.M)
LABEL_RE = re.compile(r"`(HOOK_OPEN|MIDPOINT|SCREAMER|CLIFF|TEASER(\d+)_(START|CUT_BEFORE))`")
CLUE_RE = re.compile(r"([+!])(C\d{2})")
QUOTE_RE = re.compile(r"«([^»]+)»(?:\s*\(([^)]*)\))?")

TIERS = {"hero": "hero", "secondary": "secondary", "found-footage": "found_footage", "still": "still",
         "монтаж": "montage"}
# Групи з колонки «Хто». Пропозиція: перенести в bible.yaml (зона A), щоб не тримати назви історії в коді.
GROUPS = {"четверо": ["vale", "diego", "sofia", "mateo"], "сімка": ["los_siete"],
          "напарник": ["policia_companero"], "ведуча": ["conductora_noticias"]}
FRAMING = [("дуже загальний", "extreme_wide"), ("середньо-загальний", "medium_wide"),
           ("середньо-крупний", "medium_close"), ("загальний", "wide"), ("впритул", "close_up"),
           ("крупний", "close_up"), ("середній", "medium"), ("вставка", "insert")]


def _seconds(text: str) -> float:
    m = re.search(r"(\d+):(\d{2})", text)
    return int(m.group(1)) * 60 + int(m.group(2)) if m else float("nan")


def _people(cell: str, bible: Bible, issues: list[str], where: str) -> tuple[list[str], list[str]]:
    """«Lupita, Mónica, Iván» / «Beto (мокрий)» / «четверо» → (ids, нотатки)."""
    ids, notes = [], []
    if cell in ("", "—"):
        return ids, notes
    for part in cell.split(","):
        name = part.strip()
        if m := re.match(r"^(.*?)\s*\(([^)]*)\)$", name):
            name = m.group(1).strip()
            notes.append(f"{name}: {m.group(2)}")
        found = GROUPS.get(name.lower()) or ([bible.names[name]] if name in bible.names else None)
        if found is None:
            issues.append(f"{where}: невідомий персонаж «{name}»")
            continue
        ids += [i for i in found if i not in ids]
    return ids, notes


def _speaker(paren: str | None, who: list[str], camera: str, bible: Bible) -> tuple[str | None, bool]:
    if not paren:
        # «телефон Diego» без підпису репліки — говорить той, хто знімає, і його не видно
        if m := re.search(r"телефон\s+([^\s,]+)", camera):
            owner = bible.names.get(m.group(1))
            if owner:
                return owner, True
        return (who[0] if len(who) == 1 else None), False
    parts = [p.strip() for p in paren.split(",")]
    offscreen = any("за кадром" in p for p in parts)
    name = parts[0]
    found = GROUPS.get(name.lower()) or ([bible.names[name]] if name in bible.names else [None])
    return found[0], offscreen


def _reuse(cell: str, location: str | None) -> str | None:
    """«♻ …» = шот не генеруємо. «→ ч.3» тощо — лише нотатка (reuse_note)."""
    if not cell.startswith("♻"):
        return None
    if m := re.search(r"♻\s*(\d+\.\d{2})", cell):
        return f"shot:{m.group(1)}"
    if "плита" in cell:
        m = re.search(r"`([a-z0-9_]+)`", cell)
        return f"plate:{m.group(1) if m else location}"
    if "реквізит" in cell:
        return "asset:props"
    return "asset:other"


def convert(path: Path, bible: Bible, part: int, script: Script | None = None) -> tuple[dict, list[str]]:
    """partN_shotlist.md → (сирий shots.json, issues). Валідувати — Shots.model_validate + shots_errors."""
    text = path.read_text(encoding="utf-8-sig")
    issues: list[str] = []
    lines_by_scene = {s.id: s.lines for s in script.scenes} if script else {}
    heads = list(HEADER_RE.finditer(text))
    shots: list[dict] = []
    clock = 0.0
    for k, h in enumerate(heads):
        beat, title = int(h.group(1)), h.group(2)
        scene_id = f"s{beat:02d}"
        segment = "title" if "назва" in title else "end_card" if "end card" in title else \
            "recap" if "рекап" in title else "main"
        body = text[h.end(): heads[k + 1].start() if k + 1 < len(heads) else len(text)]
        beat_shots = []
        for row in body.splitlines():
            cells = [c.strip() for c in row.strip().strip("|").split("|")]
            if len(cells) != 11 or not re.fullmatch(r"\d+\.\d{2}", cells[0]):
                continue
            sid, at, dur, loc, who_cell, camera, action, said, tier, reuse_cell, marks = cells
            where = f"шот {sid}"
            duration = float(dur.replace(",", "."))
            if abs(_seconds(at) - round(clock)) > 1:
                issues.append(f"{where}: ~час {at}, а за сумою тривалостей {clock:g} с")
            location = None if loc in ("", "—") else loc
            who, notes = _people(who_cell, bible, issues, where)
            tier_id = TIERS.get(tier)
            if tier_id is None:
                issues.append(f"{where}: невідомий tier «{tier}»")
                tier_id = "secondary"

            dialogue = []
            for q, paren in QUOTE_RE.findall(said):
                speaker, off = _speaker(paren or None, who, camera, bible)
                line_id = None
                for ln in lines_by_scene.get(scene_id, []):
                    if ln.text_es == q:
                        line_id, speaker = ln.id, speaker or ln.character_id
                if speaker is None:
                    issues.append(f"{where}: не зрозуміло, хто каже «{q}»")
                off = off or speaker == "conductora_noticias" or tier_id == "montage"
                dialogue.append({"text_es": q, "character_id": speaker, "line_id": line_id, "offscreen": off})
            if said and not dialogue:
                issues.append(f"{where}: репліку не розібрано: {said}")

            labels = []
            for full, n, kind in LABEL_RE.findall(marks):
                labels.append({"label": f"TEASER_{kind}", "n": int(n)} if n else {"label": full})
            planted = [c for sign, c in CLUE_RE.findall(marks) if sign == "+"]
            revealed = [c for sign, c in CLUE_RE.findall(marks) if sign == "!"]
            rest = CLUE_RE.sub("", LABEL_RE.sub("", marks))
            rest = " ".join(t for t in (p.strip() for p in rest.split("·")) if t)
            if rest:
                notes.append(rest)

            sfx = []
            if any(lb["label"] == "SCREAMER" for lb in labels):
                sfx.append({"type": "sting", "at_s": 0})
            low = action.lower()
            if "тиша" in low:
                sfx.append({"type": "silence", "at_s": 0})
            elif "наростання" in low:
                sfx.append({"type": "riser", "at_s": 0})

            cam = camera.lower()
            footage = "vhs" if "vhs" in cam else "phone" if ("телефон" in cam or "селфі" in cam) else "camera"
            overlay = re.search(r"«([^»]+)»\s*\(накладаємо\)", action)
            visible = tier_id == "hero" and "спиною" not in cam and any(not d["offscreen"] for d in dialogue)
            beat_shots.append({
                "id": sid, "scene_id": scene_id, "segment": segment, "duration_s": duration, "tier": tier_id,
                "location_id": location, "characters": who,
                "framing": next((f for key, f in FRAMING if key in cam), None),
                "camera": "" if camera == "—" else camera, "action": action, "footage": footage,
                "dialogue": dialogue, "has_dialogue_visible": visible, "sfx": sfx, "labels": labels,
                "clues": {"planted": planted, "revealed": revealed},
                "reuse": _reuse(reuse_cell, location), "reuse_note": reuse_cell or None,
                "overlay_text": overlay.group(1) if overlay else None, "notes": notes,
            })
            clock += duration

        # мітка з заголовка біта («Біт 1 · HOOK_OPEN») — на перший шот, якщо в таблиці її немає
        for key in ("HOOK_OPEN", "MIDPOINT", "CLIFF"):
            if key in title and beat_shots and not any(
                    lb["label"] == key for s in beat_shots for lb in s["labels"]):
                beat_shots[0]["labels"].insert(0, {"label": key})
        shots += beat_shots
    return {"story": bible.slug, "part": part, "shots": shots}, issues
