"""Лінт промптів: слова, що ламають генератор або чіпляють фільтри (docs/research/2026-10-07-generators.md §6.11).

Списки — дані в prompts/lint.yaml (вік, заборонене у відео, found footage, омоніми, насильство, параметри в тексті,
заперечення, емоції словом, магніти тексту, кілька рухів камери). Кожен список діє лише для своїх kinds
(image / video / voice); список із footage — лише для lint(…, footage="vhs" | "phone").
Збіг — ціле слово / фраза без урахування регістру; пробіл і дефіс у фразі взаємозамінні. Перед перевіркою
маскуються whitelist (сталі речення компілятора), тож «No subtitles, no on-screen text.» чисте, а у відео — ще
й репліки в лапках. Рухи камери рахуються в кожному реченні зі словом camera.

    lint("video", "A boy runs fast.")  →  ["lint: «boy» (вік) → без віку: …", "lint: «fast» (заборонено у відео) → …"]
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from fabrica import config

LINT = config.ROOT / "prompts" / "lint.yaml"
KINDS = ("image", "video", "voice")
_QUOTED = re.compile(r'"[^"\n]*"|“[^”\n]*”|\{[^{}\n]*\}')       # репліки: "…" (типово), “…”, {…} (A/B)
_NORM = str.maketrans({"\u2019": "'", "\u2018": "'", "\u02bc": "'",            # ’ ‘ ʼ → '
                       "\u00a0": " ", "\u2010": "-", "\u2011": "-"})           # NBSP, дефіси
_LIST_KEYS = {"label", "kinds", "hint", "terms", "allow", "moves", "sentence", "footage"}
_SENT = re.compile(r"(?<=[.!?])\s+|\n")                                       # межі речень
_TERM_KEYS = {"term", "re", "show", "hint", "kinds"}


class LintError(ValueError):
    """prompts/lint.yaml зламаний — повідомлення пояснює, що виправити."""


@dataclass(frozen=True)
class _Rule:
    name: str
    label: str
    kinds: frozenset[str]
    hint: object                                    # str | {kind: str} | None
    shows: tuple[str | None, ...]                   # як показати термін t<i> (None → сам збіг, для re)
    hints: tuple[object, ...]                       # підказка терміна (None → підказка списку)
    rx: dict[str, re.Pattern]                       # kind → усі терміни разом, довші першими, групи t<i>
    allow: re.Pattern | None
    sentence: re.Pattern | None = None              # multi_camera: слово, що позначає речення про камеру
    footage: frozenset[str] | None = None           # лише для цих footage (vhs / phone); None — завжди


def _phrase(s: str) -> str:
    """Фраза → регулярний вираз: пробіл / дефіс між словами = будь-яка їх послідовність."""
    return r"[\s\-]+".join(re.escape(w) for w in re.split(r"[\s\-]+", s.strip()) if w)


def _word(body: str) -> str:
    return rf"(?<!\w)(?:{body})(?!\w)"


def _union(items: list[tuple[str, str]]) -> re.Pattern:
    """[(ім'я групи, вираз)] → один вираз; довші першими, щоб «prepa student» не дав ще й «student»."""
    return re.compile("|".join(f"(?P<{g}>{_word(b)})" for g, b in items) or "(?!)", re.I)


def _strs(v, where: str) -> list[str]:
    v = [v] if isinstance(v, str) else v
    if not isinstance(v, list) or not v or not all(isinstance(s, str) and s.strip() for s in v):
        raise LintError(f"{where}: потрібен непорожній рядок або список рядків")
    return v


def _check_hint(h, where: str) -> object:
    if h is None or (isinstance(h, str) and h.strip()):
        return h
    if isinstance(h, dict) and h and set(h) <= set(KINDS) and all(isinstance(s, str) and s.strip() for s in h.values()):
        return h
    raise LintError(f"{where}: hint — рядок або {{image|video|voice: рядок}}")


def _compile_re(body: str, where: str) -> str:
    try:
        re.compile(body)
    except re.error as e:
        raise LintError(f"{where}: регулярний вираз «{body}» зламаний — {e}") from None
    return body


def _mask_rx(phrases: Iterable[str], patterns: Iterable[str] = (), where: str = "allow") -> re.Pattern | None:
    bodies = [_phrase(p.strip().rstrip(".")) for p in sorted(phrases, key=len, reverse=True) if p.strip().rstrip(".")]
    bodies += [_compile_re(p, where) for p in patterns]
    return re.compile("|".join(_word(b) for b in bodies), re.I) if bodies else None


def _rule(name: str, spec, where: str) -> _Rule:
    if not isinstance(spec, dict):
        raise LintError(f"{where}: список має бути словником (label, kinds, terms | moves …)")
    if bad := set(spec) - _LIST_KEYS:
        raise LintError(f"{where}: невідомі ключі {sorted(bad)} (можна: {sorted(_LIST_KEYS)})")
    label = spec.get("label")
    if not isinstance(label, str) or not label.strip():
        raise LintError(f"{where}: бракує label (підпис у повідомленні)")
    kinds = spec.get("kinds")
    if not isinstance(kinds, list) or not kinds or not set(kinds) <= set(KINDS):
        raise LintError(f"{where}: kinds — непорожній список із {list(KINDS)}, а не {kinds!r}")
    if ("terms" in spec) == ("moves" in spec):
        raise LintError(f"{where}: потрібне рівно одне з terms або moves")
    if "sentence" in spec and "moves" not in spec:
        raise LintError(f"{where}: sentence — лише для списку з moves")
    hint = _check_hint(spec.get("hint"), f"{where}.hint")
    footage = frozenset(_strs(spec["footage"], f"{where}.footage")) if "footage" in spec else None
    allow = _mask_rx(_strs(spec["allow"], f"{where}.allow")) if "allow" in spec else None
    # терміни: (показ, вираз, підказка, kinds)
    terms: list[tuple[str, str, object, frozenset[str]]] = []
    if "moves" in spec:
        moves = spec["moves"]
        if not isinstance(moves, dict) or not moves:
            raise LintError(f"{where}.moves: словник «рух: [форми]»")
        for move, forms in moves.items():
            terms += [(str(move), _phrase(f), None, frozenset(kinds)) for f in _strs(forms, f"{where}.moves.{move}")]
    else:
        raw = spec["terms"]
        if not isinstance(raw, list) or not raw:
            raise LintError(f"{where}.terms: непорожній список")
        for i, t in enumerate(raw):
            w = f"{where}.terms[{i}]"
            if isinstance(t, (str, list)):
                t = {"term": t}
            if not isinstance(t, dict) or ("term" in t) == ("re" in t) or set(t) - _TERM_KEYS:
                raise LintError(f"{w}: рядок, список або {{term | re (+show), hint?, kinds?}}")
            tk = t.get("kinds", kinds)
            if not isinstance(tk, list) or not tk or not set(tk) <= set(kinds):
                raise LintError(f"{w}: kinds терміна мають бути з kinds списку {kinds}")
            th = _check_hint(t.get("hint"), f"{w}.hint")
            if "re" in t:
                show = t.get("show")
                if show is not None and (not isinstance(show, str) or not show.strip()):
                    raise LintError(f"{w}: show — рядок (без нього в повідомленні сам збіг)")
                if not isinstance(t["re"], str) or not t["re"].strip():
                    raise LintError(f"{w}: re — непорожній рядок (регулярний вираз)")
                terms.append((show, _compile_re(t["re"], w), th, frozenset(tk)))
            else:
                terms += [(s.strip(), _phrase(s), th, frozenset(tk)) for s in _strs(t["term"], w)]
    order = sorted(range(len(terms)), key=lambda i: -len(terms[i][1]))
    rx = {k: _union([(f"t{i}", terms[i][1]) for i in order if k in terms[i][3]]) for k in kinds}
    sentence = None
    if "moves" in spec:
        word = spec.get("sentence", "camera")
        if not isinstance(word, str) or not word.strip():
            raise LintError(f"{where}.sentence: слово, що позначає речення про камеру («camera»)")
        sentence = re.compile(_word(_phrase(word)), re.I)
    return _Rule(name, label, frozenset(kinds), hint, tuple(t[0] for t in terms), tuple(t[2] for t in terms),
                 rx, allow, sentence, footage)


def _parse(data, path: Path) -> tuple[re.Pattern | None, list[_Rule]]:
    where = path.name
    if not isinstance(data, dict) or not isinstance(data.get("lists"), dict) or not data["lists"]:
        raise LintError(f"{where}: потрібен непорожній словник lists")
    if bad := set(data) - {"version", "whitelist", "lists"}:
        raise LintError(f"{where}: невідомі ключі {sorted(bad)}")
    wl = data.get("whitelist") or {}
    if not isinstance(wl, dict) or set(wl) - {"phrases", "patterns"}:
        raise LintError(f"{where}.whitelist: словник із phrases / patterns")
    phrases = _strs(wl["phrases"], f"{where}.whitelist.phrases") if wl.get("phrases") else []
    patterns = _strs(wl["patterns"], f"{where}.whitelist.patterns") if wl.get("patterns") else []
    white = _mask_rx(phrases, patterns, f"{where}.whitelist.patterns")
    return white, [_rule(str(n), s, f"{where}: {n}") for n, s in data["lists"].items()]


_CACHE: dict[Path, tuple[tuple[int, int], dict, re.Pattern | None, list[_Rule]]] = {}


def _loaded(path: Path) -> tuple[dict, re.Pattern | None, list[_Rule]]:
    path = Path(path)
    try:
        st = path.stat()
    except FileNotFoundError:
        raise LintError(f"немає файлу лінту {path}") from None
    key = (st.st_mtime_ns, st.st_size)
    hit = _CACHE.get(path)
    if hit and hit[0] == key:
        return hit[1:]
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
    except yaml.YAMLError as e:
        raise LintError(f"{path.name}: YAML не читається — {e}") from None
    white, rules = _parse(data, path)
    _CACHE[path] = (key, data, white, rules)
    return data, white, rules


def load(path: Path = LINT) -> dict:
    """Списки лінту з YAML (перевірені: kinds, терміни, регулярні вирази). Зламано → LintError."""
    return _loaded(path)[0]


def _mask(text: str, rx: re.Pattern | None) -> str:
    """Збіги → пробіли тієї ж довжини: позиції й межі слів не зсуваються."""
    return rx.sub(lambda m: " " * len(m.group()), text) if rx else text


@lru_cache(maxsize=64)
def _allow_rx(allow: tuple[str, ...]) -> re.Pattern | None:
    return _mask_rx(allow)


def _allow(allow) -> tuple[str, ...]:
    """allow → кортеж рядків; словник (style.video_footage …) чи не-рядки — LintError, а не тихий whitelist ключів."""
    if allow is None:
        return ()
    if isinstance(allow, str):
        return (allow,)
    items = () if isinstance(allow, dict) or not isinstance(allow, Iterable) else tuple(allow)
    if isinstance(allow, dict) or not isinstance(allow, Iterable) or not all(isinstance(a, str) for a in items):
        raise LintError("allow — список сталих фраз (рядків), не словник і не інші типи")
    return items


def _hint(rule: _Rule, i: int, kind: str) -> str:
    for h in (rule.hints[i], rule.hint):
        h = h.get(kind) if isinstance(h, dict) else h
        if h:
            return h
    return ""


def _msg(show: str, label: str, hint: str) -> str:
    return f"lint: «{show}» ({label})" + (f" → {hint}" if hint else "")


def _terms(rule: _Rule, kind: str, text: str) -> list[str]:
    seen: dict[tuple[int, str], None] = {}
    for m in rule.rx[kind].finditer(_mask(text, rule.allow)):
        i = int(m.lastgroup[1:])
        seen.setdefault((i, rule.shows[i] or " ".join(m.group().split()).lower()))
    return [_msg(show, rule.label, _hint(rule, i, kind)) for i, show in seen]


def _camera(rule: _Rule, kind: str, text: str) -> list[str]:
    """Кожне речення зі словом camera («Camera: …» і проза «the camera pushes in…») — не більше одного руху."""
    out = []
    for s in _SENT.split(_mask(text, rule.allow)):
        if rule.sentence.search(s):
            moves = dict.fromkeys(rule.shows[int(m.lastgroup[1:])] for m in rule.rx[kind].finditer(s))
            if len(moves) > 1:
                out.append(_msg(" + ".join(moves), rule.label, _hint(rule, -1, kind)))
    return out


def lint(kind: str, text: str, *, allow: Iterable[str] = (), footage: str | None = None,
         path: Path = LINT) -> list[str]:
    """Попередження «lint: «слово» (список) → підказка» для промпту kind; без повторів, у порядку списків YAML.

    allow — додаткові сталі фрази компілятора, які не перевіряються: лише image_rules / video_constants із
    prompt_en.yaml, НІКОЛИ не style (це зміст, який теж лінтуємо; сталі style-фрази вже у whitelist YAML).
    footage — "vhs" / "phone" для found footage (вмикає списки з footage, напр. «cinematic»); None — звичайний шот.
    """
    if kind not in KINDS:
        raise LintError(f"невідомий kind «{kind}» — має бути один із {list(KINDS)}")
    if footage is not None and not isinstance(footage, str):
        raise LintError(f"footage — рядок (vhs / phone) або None, а не {footage!r}")
    allow_rx = _allow_rx(_allow(allow))
    _, white, rules = _loaded(path)
    text = (text or "").translate(_NORM)
    if kind == "video":                     # у картинці лапки — напис у кадрі, а не репліка: не ховаємо
        text = _QUOTED.sub(lambda m: " " * len(m.group()), text)
    text = _mask(_mask(text, white), allow_rx)
    out: list[str] = []
    for rule in rules:
        if kind in rule.kinds and (rule.footage is None or footage in rule.footage):
            out += (_camera if rule.sentence else _terms)(rule, kind, text)
    return list(dict.fromkeys(out))
