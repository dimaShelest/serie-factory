"""CLI фабрики: `uv run fabrica --help`.

Команди працюють з однією частиною історії. Файли між етапами — output/<slug>/part<N>/ (не в Git):
    script.json   етап script
    shots.json    етап shots (або конвертер розкадровки)
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from pydantic import ValidationError

from fabrica import bible as bible_mod
from fabrica import costs as costs_mod
from fabrica import shotlist as shotlist_mod
from fabrica import story as story_mod
from fabrica.ledger import Ledger
from fabrica.models import Script, Shots, check_refs, check_shots, script_errors, shots_errors

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"

app = typer.Typer(help="serie-factory: конвеєр іспаномовних AI-серіалів (docs/ARCHITECTURE.md).",
                  no_args_is_help=True, add_completion=False)

Slug = typer.Argument(..., help="серіал, напр. la-garganta (тека series/<slug>)")
Part = typer.Argument(..., min=1, max=4, help="частина 1–4")
Out = typer.Option(OUTPUT, "--out", help="коренева тека результатів")


def part_dir(out: Path, slug: str, part: int) -> Path:
    return out / slug / f"part{part}"


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")   # консоль Windows не UTF-8


def _report(title: str, errors: list[str]) -> bool:
    if errors:
        typer.echo(f"✗ {title}: {len(errors)}")
        for e in errors:
            typer.echo(f"  - {e}")
    else:
        typer.echo(f"✓ {title}")
    return not errors


@app.callback()
def _main() -> None:
    _utf8()


@app.command()
def shotlist(slug: str = Slug, part: int = Part, out: Path = Out) -> None:
    """Розкадровку series/<slug>/part<N>_shotlist.md → output/<slug>/part<N>/shots.json."""
    b = bible_mod.load(slug)
    src = bible_mod.SERIES / slug / f"part{part}_shotlist.md"
    script_path = part_dir(out, slug, part) / "script.json"
    script = Script.model_validate_json(script_path.read_text(encoding="utf-8")) if script_path.exists() else None
    raw, issues = shotlist_mod.convert(src, b, part, script)
    try:
        shots = Shots.model_validate(raw)
    except ValidationError as e:
        typer.echo(f"✗ shots.json не за схемою:\n{e}")
        raise typer.Exit(1) from None
    dest = part_dir(out, slug, part) / "shots.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(shots.model_dump_json(indent=2), encoding="utf-8")
    typer.echo(f"→ {dest} ({len(shots.shots)} шотів, {sum(s.duration_s for s in shots.shots):g} с)")
    _report("розбір розкадровки без втрат", issues)
    _report("правила PLAYBOOK (shots)", shots_errors(shots))
    if issues:
        raise typer.Exit(1)


@app.command()
def validate(slug: str = Slug, part: int = Part, out: Path = Out) -> None:
    """Перевірити script.json і shots.json частини: схема, PLAYBOOK, біблія, story.md, узгодженість."""
    b = bible_mod.load(slug)
    folder = part_dir(out, slug, part)
    ok, script = True, None
    if (folder / "script.json").exists():
        try:
            script = Script.model_validate_json((folder / "script.json").read_text(encoding="utf-8"))
        except ValidationError as e:
            typer.echo(f"✗ script.json не за схемою:\n{e}")
            raise typer.Exit(1) from None
        beats = story_mod.parse(bible_mod.SERIES / slug / "story.md").get(part, [])
        ok &= _report("script: правила PLAYBOOK", script_errors(script))
        ok &= _report("script: ID з біблії", check_refs(script, b))
        ok &= _report("script: без втрат щодо story.md", story_mod.check_script(script, beats))
    else:
        typer.echo(f"· script.json немає ({folder})")
    if (folder / "shots.json").exists():
        try:
            shots = Shots.model_validate_json((folder / "shots.json").read_text(encoding="utf-8"))
        except ValidationError as e:
            typer.echo(f"✗ shots.json не за схемою:\n{e}")
            raise typer.Exit(1) from None
        ok &= _report("shots: правила PLAYBOOK", shots_errors(shots))
        ok &= _report("shots: ID з біблії", check_refs(shots, b))
        if script:
            ok &= _report("shots покривають script", check_shots(shots, script))
    else:
        typer.echo(f"· shots.json немає ({folder})")
    if not ok:
        raise typer.Exit(1)


@app.command()
def costs(slug: str = Slug, part: int = Part, out: Path = Out,
          min_clip: float = typer.Option(0.0, "--min-clip", help="мінімальна оплачувана тривалість кліпу, с"),
          attempts: int = typer.Option(costs_mod.ATTEMPTS, "--attempts", help="планові спроби на шот")) -> None:
    """Кошторис відео частини за shots.json + уже витрачене й ліміти з .env."""
    shots = Shots.model_validate_json((part_dir(out, slug, part) / "shots.json").read_text(encoding="utf-8"))
    est = costs_mod.estimate(shots, costs_mod.load_rates(), attempts=attempts, min_clip_s=min_clip)
    typer.echo(f"Кошторис відео {slug} ч.{part} (× {attempts} спроби, кліп ≥ {min_clip:g} с):")
    for tier, t in sorted(est.tiers.items(), key=lambda kv: -kv[1].usd):
        typer.echo(f"  {tier:<14} {t.shots:>3} шотів  {t.screen_s:>6g} с  ${t.usd:>8.2f}")
    typer.echo(f"  {'разом':<14} {'':>3}        {'':>6}    ${est.usd:>8.2f}")
    typer.echo(f"  без генерації (♻): {est.reused_s:g} с · lip-sync: {est.lipsync_s:g} с (ставка Sync — TODO)")
    ledger = Ledger(out / "fabrica.sqlite")
    try:
        typer.echo(f"Уже витрачено на ч.{part}: ${ledger.spent(slug, part):.2f}")
        for w in ledger.check(slug, part, est.usd, force=True):
            typer.echo(f"  {w}")
    finally:
        ledger.close()


@app.command("schema")
def schema(kind: str = typer.Argument(..., help="script або shots")) -> None:
    """JSON-схема script.json / shots.json (для LLM: local_llm.generate_json)."""
    model = {"script": Script, "shots": Shots}.get(kind)
    if model is None:
        raise typer.BadParameter("script або shots")
    typer.echo(json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2))
