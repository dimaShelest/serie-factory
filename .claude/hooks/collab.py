#!/usr/bin/env python3
"""Спільна пам'ять двох Claude: хто я, скриньки docs/comms, журнали HANDOFF/DECISIONS/prompts.

Тільки stdlib, Python 3.9+, однаково працює на macOS і Windows.
Запускати з кореня репо:

    uv run --no-project .claude/hooks/collab.py <команда> [--help]

Команди:
    whoami                      -> A | B | UNKNOWN
    stamp                       -> поточний час у форматі журналів
    inbox [--mark-read] [--all] -> нові повідомлення в МОЇЙ скриньці
    send --title T (--file F | текст | -)  -> повідомлення в скриньку ПАРТНЕРА
    log {handoff,decision} --title T (--file F | текст | -)  -> запис зверху журналу
    prompt-summary (--file F | текст | -)  -> підсумок зверху мого журналу промптів за сьогодні
    digest                      -> 3 останні HANDOFF + нові DECISIONS + промпти партнера з мого /handoff
    overview                    -> стан скриньок і останні handoff обох Claude
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PARTNER = {"A": "B", "B": "A"}
HUMAN = {"A": "dimaShelest, Mac", "B": "nuchay69-max, Windows"}

# Заголовки записів (один формат часу всюди: "2026-10-05 14:30 +03:00"):
#   HANDOFF.md / DECISIONS.md:  ## 2026-10-05 14:30 +03:00 · Claude A · Назва
#   comms/to-X.md:              ## 2026-10-05 14:30 +03:00 · від Claude A · NEW · Тема
#   prompts/<день>-X.md:        ### 14:30:05 +03:00 · сесія 4b052eb3
_STAMP = r"(?P<date>\d{4}-\d{2}-\d{2}) (?P<time>\d{2}:\d{2}) (?P<tz>[+-]\d{2}:\d{2})"
ENTRY_RE = re.compile(rf"^## {_STAMP} · Claude (?P<who>[AB]) · (?P<title>.*)$")
MSG_RE = re.compile(rf"^## {_STAMP} · від Claude (?P<who>[AB]) · (?P<status>NEW|READ) · (?P<title>.*)$")
PROMPT_RE = re.compile(r"^### (?P<time>\d{2}:\d{2}:\d{2}) (?P<tz>[+-]\d{2}:\d{2})(?: · .*)?$")
PROMPT_FILE_RE = re.compile(r"^(?P<date>\d{4}-\d{2}-\d{2})-(?P<who>[AB])\.md$")
# "Я — Claude A" (допускаємо кириличні А/В, бо їх легко набрати з української розкладки)
WHO_RE = re.compile(r"Я\s*[—–-]+\s*Claude\s+(?P<who>[ABАВ])(?![\w])")

LOG_MARK = "<!-- НОВІ ЗАПИСИ — ОДРАЗУ ПІД ЦИМ РЯДКОМ (найновіші зверху) -->"
SUMMARY_MARK = "<!-- підсумки /handoff — під цим рядком, найновіший зверху -->"
REDACTED = "[ПРИХОВАНО]"


# ---------------------------------------------------------------- базове


def setup_stdio() -> None:
    """Windows-консоль за замовчуванням не UTF-8 — без цього українська ламає вивід."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def read(path: Path) -> str:
    # utf-8-sig: PowerShell 5.1 пише файли з BOM
    return path.read_text(encoding="utf-8-sig") if path.exists() else ""


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def now() -> datetime:
    return datetime.now().astimezone()


def tz(dt: datetime) -> str:
    off = dt.strftime("%z") or "+0000"
    return f"{off[:3]}:{off[3:]}"


def stamp(dt: datetime | None = None) -> str:
    dt = dt or now()
    return f"{dt:%Y-%m-%d %H:%M} {tz(dt)}"


def parse_stamp(day: str, time: str, offset: str) -> datetime:
    return datetime.fromisoformat(f"{day}T{time}{offset}")


def git(*args: str, root: Path = ROOT, timeout: int = 30) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=timeout,
    )


# ---------------------------------------------------------------- хто я


def whoami(root: Path = ROOT) -> str | None:
    m = WHO_RE.search(read(root / "CLAUDE.local.md"))
    if not m:
        return None
    return {"А": "A", "В": "B"}.get(m.group("who"), m.group("who"))


def require_me(root: Path = ROOT) -> str:
    me = whoami(root)
    if not me:
        sys.exit(
            "Не знаю, хто я: немає CLAUDE.local.md з рядком «Я — Claude A» або «Я — Claude B».\n"
            "Спитай людину і створи файл (див. CLAUDE.md, розділ «Хто я»)."
        )
    return me


# ---------------------------------------------------------------- записи


@dataclass
class Entry:
    when: datetime
    who: str
    title: str
    body: str
    status: str = ""
    line: int = 0
    raw: str = ""


def parse_entries(text: str, regex: re.Pattern = ENTRY_RE) -> list[Entry]:
    """Розбирає markdown-журнал на записи за заголовками `## <штамп> · ...`."""
    lines = text.splitlines()
    heads = [(i, m) for i, line in enumerate(lines) if (m := regex.match(line))]
    out = []
    for k, (i, m) in enumerate(heads):
        end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
        chunk = lines[i:end]
        while chunk and chunk[-1].strip() in ("", "---"):
            chunk.pop()
        g = m.groupdict()
        out.append(Entry(
            when=parse_stamp(g["date"], g["time"], g["tz"]),
            who=g["who"], title=g["title"].strip(), status=g.get("status") or "",
            body="\n".join(chunk[1:]).strip(), line=i, raw="\n".join(chunk),
        ))
    return out


def insert_under_mark(text: str, block: str, mark: str = LOG_MARK) -> str:
    """Вставляє блок одразу під маркером (найновіше зверху)."""
    block = block.strip("\n")
    if mark in text:
        return text.replace(mark, f"{mark}\n\n{block}\n", 1)
    return f"{block}\n\n{text}"


def log_entry(kind: str, me: str, title: str, body: str, root: Path = ROOT,
              when: datetime | None = None) -> Path:
    path = root / "docs" / ("HANDOFF.md" if kind == "handoff" else "DECISIONS.md")
    block = f"## {stamp(when)} · Claude {me} · {one_line(title)}\n\n{body.strip()}\n\n---"
    write(path, insert_under_mark(read(path), block))
    return path


def last_entry_time(path: Path, who: str) -> datetime | None:
    times = [e.when for e in parse_entries(read(path)) if e.who == who]
    return max(times) if times else None


def one_line(text: str) -> str:
    return " ".join(text.split()) or "без назви"


# ---------------------------------------------------------------- скриньки


def inbox_path(who: str, root: Path = ROOT) -> Path:
    return root / "docs" / "comms" / f"to-{who}.md"


def inbox_header(who: str) -> str:
    p = PARTNER[who]
    return (
        f"# Скринька Claude {who}\n\n"
        f"Повідомлення ДЛЯ Claude {who} ({HUMAN[who]}) від Claude {p}. **Нові — внизу.**\n"
        f"Пише сюди лише Claude {p} (`/msg`, `/handoff`). Claude {who} лише міняє статус NEW → READ (`/start`).\n"
        "Формат заголовка: `## РРРР-ММ-ДД ГГ:ХХ ±ГГ:ХХ · від Claude X · NEW|READ · Тема`\n\n---\n"
    )


def messages(who: str, root: Path = ROOT) -> list[Entry]:
    return parse_entries(read(inbox_path(who, root)), MSG_RE)


def send(to: str, sender: str, title: str, body: str, root: Path = ROOT,
         when: datetime | None = None) -> Path:
    path = inbox_path(to, root)
    text = read(path) or inbox_header(to)
    block = f"## {stamp(when)} · від Claude {sender} · NEW · {one_line(title)}\n\n{body.strip()}\n\n---\n"
    write(path, text.rstrip("\n") + "\n\n" + block)
    return path


def mark_read(who: str, root: Path = ROOT) -> int:
    path = inbox_path(who, root)
    lines = read(path).splitlines()
    n = 0
    for i, line in enumerate(lines):
        m = MSG_RE.match(line)
        if m and m.group("status") == "NEW":
            lines[i] = line.replace(" · NEW · ", " · READ · ", 1)
            n += 1
    if n:
        write(path, "\n".join(lines) + "\n")
    return n


# ---------------------------------------------------------------- журнал промптів

_SECRET_RES = [re.compile(p) for p in (
    r"\bsk[-_][A-Za-z0-9_\-]{16,}",                     # OpenAI / Anthropic / ElevenLabs
    r"\bgh[pousr]_[A-Za-z0-9]{20,}",                    # GitHub
    r"\bgithub_pat_[A-Za-z0-9_]{20,}",
    r"\bAKIA[0-9A-Z]{16}\b",                            # AWS / R2-сумісні
    r"\bAIza[0-9A-Za-z_\-]{30,}",                       # Google
    r"\bxox[abprs]-[A-Za-z0-9\-]{10,}",                 # Slack
    r"\b(?:hf|r8)_[A-Za-z0-9]{30,}",                    # Hugging Face / Replicate
    r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}",  # JWT
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"(?i)\bbearer\s+[A-Za-z0-9._~+/\-]{16,}",
    # ключ=значення / ключ: значення (англ. і укр.)
    r"(?i)\b(?:api[_-]?key|secret|token|password|passwd|pwd|signature|credential|"
    r"пароль|ключ|токен|секрет)s?\b\s*[:=]\s*\S{6,}",
    # ENV-рядки: SOME_API_KEY=value
    r"\b[A-Z][A-Z0-9_]*(?:KEY|TOKEN|SECRET|PASSWORD|PASS)[A-Z0-9_]*\s*=\s*\S+",
)]
_TOKEN_SPLIT = re.compile(r"[\s\"'`<>()\[\]{},;|]+")


def _high_entropy(tok: str) -> bool:
    tok = tok.strip(".:")
    if len(tok) < 32 or "://" in tok or tok[:1] in "/~." or re.match(r"^[A-Za-z]:\\", tok):
        return False
    if tok.count("/") + tok.count("\\") >= 2:  # схоже на шлях
        return False
    if re.fullmatch(r"[0-9a-fA-F]{32,}", tok):
        return True
    classes = sum((any(c.islower() for c in tok), any(c.isupper() for c in tok),
                   sum(c.isdigit() for c in tok) >= 4))
    return classes == 3 and re.fullmatch(r"[A-Za-z0-9+/=_\-.]+", tok) is not None


def looks_secret(line: str) -> bool:
    return any(r.search(line) for r in _SECRET_RES) or any(
        _high_entropy(t) for t in _TOKEN_SPLIT.split(line))


def redact(text: str) -> str:
    """Рядки, схожі на секрети, повністю замінює на [ПРИХОВАНО]."""
    return "\n".join(REDACTED if looks_secret(line) else line for line in text.splitlines())


def prompt_path(who: str, day: date, root: Path = ROOT) -> Path:
    return root / "docs" / "prompts" / f"{day:%Y-%m-%d}-{who}.md"


def prompt_header(who: str, day: date) -> str:
    return (
        f"# Промпти людини · Claude {who} · {day:%Y-%m-%d}\n\n"
        "Пише хук UserPromptSubmit (`.claude/hooks/log_prompt.py`); секрети замінено на [ПРИХОВАНО].\n\n"
        f"## Підсумки сесій\n\n{SUMMARY_MARK}\n\n## Промпти\n"
    )


def append_prompt(who: str, prompt: str, session: str = "", root: Path = ROOT,
                  when: datetime | None = None) -> Path:
    when = when or now()
    path = prompt_path(who, when.date(), root)
    clean = redact(prompt.strip("\n"))
    longest = max((len(m) for m in re.findall(r"`+", clean)), default=0)
    fence = "`" * max(3, longest + 1)
    head = f"### {when:%H:%M:%S} {tz(when)}" + (f" · сесія {session}" if session else "")
    if not path.exists():
        write(path, prompt_header(who, when.date()))
    with path.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"\n{head}\n\n{fence}text\n{clean}\n{fence}\n")
    return path


def add_prompt_summary(who: str, summary: str, root: Path = ROOT,
                       when: datetime | None = None) -> Path:
    when = when or now()
    path = prompt_path(who, when.date(), root)
    text = read(path) or prompt_header(who, when.date())
    block = f"**/handoff о {when:%H:%M} {tz(when)}**\n\n{summary.strip()}\n"
    write(path, insert_under_mark(text, block, SUMMARY_MARK))
    return path


def prompts_since(who: str, since: datetime | None, root: Path = ROOT) -> list[tuple[datetime, str]]:
    out = []
    for path in sorted((root / "docs" / "prompts").glob(f"*-{who}.md")):
        fm = PROMPT_FILE_RE.match(path.name)
        # запас у день — часові пояси людей можуть відрізнятися
        if not fm or (since and fm.group("date") < (since.date() - timedelta(days=1)).isoformat()):
            continue
        lines = read(path).splitlines()
        heads = [(i, m) for i, line in enumerate(lines) if (m := PROMPT_RE.match(line))]
        for k, (i, m) in enumerate(heads):
            end = heads[k + 1][0] if k + 1 < len(heads) else len(lines)
            when = parse_stamp(fm.group("date"), m.group("time"), m.group("tz"))
            if since is None or when > since:
                out.append((when, "\n".join(lines[i + 1:end]).strip()))
    return sorted(out, key=lambda x: x[0])


# ---------------------------------------------------------------- звіти


def clip(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit].rstrip() + "\n… (обрізано)"


def digest(me: str, root: Path = ROOT) -> str:
    p = PARTNER[me]
    docs = root / "docs"
    since = last_entry_time(docs / "HANDOFF.md", me)
    out = [f"# Дайджест для Claude {me}",
           f"Мій останній /handoff: {stamp(since) if since else 'ще не було'}", ""]

    out.append("## 3 останні записи HANDOFF")
    handoffs = parse_entries(read(docs / "HANDOFF.md"))[:3]
    out += [h.raw + "\n" for h in handoffs] or ["(порожньо)"]

    out.append(f"\n## Нові DECISIONS {'з ' + stamp(since) if since else '(усі)'}")
    new = [d for d in parse_entries(read(docs / "DECISIONS.md")) if since is None or d.when > since]
    out += [d.raw + "\n" for d in new] or ["(немає)"]

    prompts = prompts_since(p, since, root)
    out.append(f"\n## Промпти людини партнера (Claude {p}) {'з ' + stamp(since) if since else '(усі)'}: {len(prompts)}")
    for when, body in prompts[-30:]:
        out.append(f"### {stamp(when)}\n{clip(body, 1500)}\n")
    if not prompts:
        out.append("(немає)")
    return "\n".join(out)


def overview(root: Path = ROOT) -> str:
    out = []
    for who in ("A", "B"):
        msgs = messages(who, root)
        new = [m for m in msgs if m.status == "NEW"]
        last = last_entry_time(root / "docs" / "HANDOFF.md", who)
        out.append(
            f"Claude {who} ({HUMAN[who]}): останній /handoff — {stamp(last) if last else 'ще не було'}; "
            f"непрочитаних у скриньці to-{who}.md — {len(new)}"
            + (" (найстаріше: " + stamp(new[0].when) + f" «{new[0].title}»)" if new else "")
        )
    return "\n".join(out)


# ---------------------------------------------------------------- CLI


def _body(args: argparse.Namespace) -> str:
    if args.file:
        return read(Path(args.file))
    if args.text == ["-"] or not args.text:
        return sys.stdin.buffer.read().decode("utf-8-sig", "replace")
    return " ".join(args.text)


def main(argv: list[str] | None = None) -> int:
    setup_stdio()
    ap = argparse.ArgumentParser(description="Спільна пам'ять Claude A / Claude B")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("whoami")
    sub.add_parser("stamp")
    p_in = sub.add_parser("inbox")
    p_in.add_argument("--mark-read", action="store_true")
    p_in.add_argument("--all", action="store_true", help="показати й прочитані")
    for name in ("send", "log", "prompt-summary"):
        sp = sub.add_parser(name)
        if name == "log":
            sp.add_argument("kind", choices=["handoff", "decision"])
        if name != "prompt-summary":
            sp.add_argument("--title", required=True)
        sp.add_argument("--file", help="взяти текст з файлу (зручно на Windows)")
        sp.add_argument("text", nargs="*", help="текст; '-' або нічого = stdin")
    sub.add_parser("digest")
    sub.add_parser("overview")
    args = ap.parse_args(argv)

    if args.cmd == "whoami":
        print(whoami() or "UNKNOWN")
    elif args.cmd == "stamp":
        print(stamp())
    elif args.cmd == "inbox":
        me = require_me()
        msgs = [m for m in messages(me) if args.all or m.status == "NEW"]
        print(f"Скринька Claude {me}: {len(msgs)} {'повідомлень' if args.all else 'нових'}\n")
        for m in msgs:
            print(m.raw + "\n")
        if args.mark_read and msgs:
            print(f"Позначено READ: {mark_read(me)}. Закоміть docs/comms/to-{me}.md, щоб партнер це бачив.")
    elif args.cmd == "send":
        me = require_me()
        path = send(PARTNER[me], me, args.title, _body(args))
        print(f"Надіслано Claude {PARTNER[me]} → {path.relative_to(ROOT).as_posix()}")
    elif args.cmd == "log":
        me = require_me()
        path = log_entry(args.kind, me, args.title, _body(args))
        print(f"Записано зверху → {path.relative_to(ROOT).as_posix()}")
    elif args.cmd == "prompt-summary":
        me = require_me()
        path = add_prompt_summary(me, _body(args))
        print(f"Підсумок додано → {path.relative_to(ROOT).as_posix()}")
    elif args.cmd == "digest":
        print(digest(require_me()))
    elif args.cmd == "overview":
        print(overview())
    return 0


if __name__ == "__main__":
    sys.exit(main())
