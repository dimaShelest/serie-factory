"""CLI фабрики: `uv run fabrica --help`.

Команди працюють з однією частиною історії. Результати — output/<slug>/part<N>/ (не в Git):
    script.json   етап script
    shots.json    етап shots (або конвертер розкадровки)
    voice/ video/ qc/ assemble/ cut/   медіа етапів (кожен етап — своя тека)
Журнал витрат — один на машину: output/fabrica.sqlite.
Код виходу: 0 — усе гаразд, 1 — є помилки (перевірки, ліміти, файли), 2 — неправильні аргументи.
"""

from __future__ import annotations

import functools
import json
import sys
from collections.abc import Callable
from pathlib import Path

import typer
from pydantic import ValidationError

from fabrica import bible as bible_mod
from fabrica import config
from fabrica import costs as costs_mod
from fabrica import shotlist as shotlist_mod
from fabrica import story as story_mod
from fabrica.ledger import BudgetExceeded, BudgetNotConfigured, Ledger
from fabrica.models import Script, Shots, check_refs, check_shots, script_errors, shots_errors

OUTPUT = config.ROOT / "output"

app = typer.Typer(help="serie-factory: конвеєр іспаномовних AI-серіалів (docs/ARCHITECTURE.md).",
                  no_args_is_help=True, add_completion=False, pretty_exceptions_enable=False)

Slug = typer.Argument(..., help="серіал, напр. la-garganta (тека series/<slug>)")
Part = typer.Argument(..., min=1, max=4, help="частина 1–4")
Out = typer.Option(OUTPUT, "--out", help="коренева тека результатів")


def part_dir(out: Path, slug: str, part: int) -> Path:
    return out / slug / f"part{part}"


def _utf8() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")   # консоль / pipe у Windows не UTF-8


def main() -> None:
    """Точка входу `fabrica`: UTF-8 вмикаємо ДО Typer, бо `--help` спрацьовує раніше за callback."""
    _utf8()
    app()


def friendly(fn: Callable) -> Callable:
    """Очікувані помилки — одним рядком з підказкою і кодом 1, без трейсбеку."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except typer.Exit:
            raise
        except FileNotFoundError as e:
            typer.echo(f"✗ немає файлу: {e.filename or e}", err=True)
        except ValidationError as e:
            typer.echo(f"✗ дані не за схемою:\n{e}", err=True)
        except (ValueError, KeyError) as e:            # ConfigError, StoryFormatError, невідомий slug …
            typer.echo(f"✗ {e}", err=True)
        raise typer.Exit(1)
    return wrapper


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")       # файл міг зберегти PowerShell 5.1 з BOM


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:   # однакові байти на Mac і Windows
        f.write(text)


def _report(title: str, errors: list[str]) -> bool:
    if errors:
        typer.echo(f"✗ {title}: {len(errors)}")
        for e in errors:
            typer.echo(f"  - {e}")
    else:
        typer.echo(f"✓ {title}")
    return not errors


@app.command()
@friendly
def shotlist(slug: str = Slug, part: int = Part, out: Path = Out) -> None:
    """Розкадровку series/<slug>/part<N>_shotlist.md → output/<slug>/part<N>/shots.json."""
    b = bible_mod.load(slug)
    src = bible_mod.SERIES / slug / f"part{part}_shotlist.md"
    script_path = part_dir(out, slug, part) / "script.json"
    script = Script.model_validate_json(_read(script_path)) if script_path.exists() else None
    raw, issues = shotlist_mod.convert(src, b, part, script)
    shots = Shots.model_validate(raw)
    dest = part_dir(out, slug, part) / "shots.json"
    _write(dest, shots.model_dump_json(indent=2) + "\n")
    typer.echo(f"→ {dest} ({len(shots.shots)} шотів, {sum(s.duration_s for s in shots.shots):g} с)")
    if script is None:
        typer.echo("· script.json немає: етап script ще не запускали, тож репліки без підпису мовця й узгодженість "
                   "зі script не перевіряються")
        for issue in issues:
            typer.echo(f"  · {issue}")
        ok = True
    else:
        ok = _report("розбір розкадровки без втрат", issues)
    ok &= _report("правила PLAYBOOK (shots)", shots_errors(shots))
    if not ok:
        raise typer.Exit(1)


@app.command()
@friendly
def validate(slug: str = Slug, part: int = Part, out: Path = Out) -> None:
    """Перевірити script.json і shots.json частини: схема, PLAYBOOK, біблія, story.md, узгодженість."""
    b = bible_mod.load(slug)
    folder = part_dir(out, slug, part)
    has_script, has_shots = (folder / "script.json").exists(), (folder / "shots.json").exists()
    if not (has_script or has_shots):
        typer.echo(f"✗ нема що перевіряти: у {folder} немає ні script.json, ні shots.json "
                   f"(спершу `fabrica shotlist {slug} {part}`)", err=True)
        raise typer.Exit(1)
    ok, script = True, None
    if has_script:
        script = Script.model_validate_json(_read(folder / "script.json"))
        beats = story_mod.parse(bible_mod.SERIES / slug / "story.md").get(part, [])
        ok &= _report("script: правила PLAYBOOK", script_errors(script))
        ok &= _report("script: ID з біблії", check_refs(script, b))
        ok &= _report("script: без втрат щодо story.md", story_mod.check_script(script, beats))
    else:
        typer.echo(f"· script.json немає ({folder})")
    if has_shots:
        shots = Shots.model_validate_json(_read(folder / "shots.json"))
        ok &= _report("shots: правила PLAYBOOK", shots_errors(shots))
        ok &= _report("shots: ID з біблії", check_refs(shots, b))
        if script:
            ok &= _report("shots покривають script", check_shots(shots, script))
    else:
        typer.echo(f"· shots.json немає ({folder})")
    if not ok:
        raise typer.Exit(1)


@app.command()
@friendly
def costs(slug: str = Slug, part: int = Part, out: Path = Out,
          min_clip: float = typer.Option(0.0, "--min-clip", min=0, help="мінімальна оплачувана тривалість кліпу, с"),
          attempts: int = typer.Option(costs_mod.ATTEMPTS, "--attempts", min=1, help="планові спроби на шот")) -> None:
    """Кошторис відео частини за shots.json + уже витрачене й ліміти з .env. Перевищення ліміту — код 1."""
    shots_path = part_dir(out, slug, part) / "shots.json"
    if not shots_path.exists():
        typer.echo(f"✗ немає {shots_path} — спершу `fabrica shotlist {slug} {part}`", err=True)
        raise typer.Exit(1)
    shots = Shots.model_validate_json(_read(shots_path))
    est = costs_mod.estimate(shots, costs_mod.load_rates(), attempts=attempts, min_clip_s=min_clip)
    typer.echo(f"Кошторис відео {slug} ч.{part} (× {attempts} спроби, кліп ≥ {min_clip:g} с):")
    for tier, t in sorted(est.tiers.items(), key=lambda kv: -kv[1].usd):
        typer.echo(f"  {tier:<14} {t.shots:>3} шотів  {t.screen_s:>6g} с  ${t.usd:>8.2f}")
    typer.echo(f"  {'разом':<14} {'':>3}        {'':>6}    ${est.usd:>8.2f}")
    typer.echo(f"  без генерації (♻): {est.reused_s:g} с · lip-sync: {est.lipsync_s:g} с (ставка Sync — TODO)")
    ledger = Ledger(out / "fabrica.sqlite")
    try:
        typer.echo(f"Уже витрачено на ч.{part}: ${ledger.spent(slug, part):.2f}")
        for w in ledger.check(slug, part, est.usd):
            typer.echo(f"  ⚠️ {w}")
    except BudgetNotConfigured as e:
        typer.echo(f"  ⚠️ {e}")                         # кошторис можна дивитись і без лімітів
    except BudgetExceeded as e:
        typer.echo(f"✗ {e}", err=True)
        raise typer.Exit(1) from None
    finally:
        ledger.close()


@app.command("schema")
def schema(kind: str = typer.Argument(..., help="script або shots")) -> None:
    """JSON-схема script.json / shots.json (для LLM: local_llm.generate_json)."""
    model = {"script": Script, "shots": Shots}.get(kind)
    if model is None:
        raise typer.BadParameter("script або shots")
    typer.echo(json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2))
