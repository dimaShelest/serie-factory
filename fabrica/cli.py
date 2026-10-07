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
from fabrica import lab as lab_mod
from fabrica import lessons as lessons_mod
from fabrica import progress as progress_mod
from fabrica import prompts as prompts_mod
from fabrica import providers as providers_mod
from fabrica import shotlist as shotlist_mod
from fabrica import story as story_mod
from fabrica import video as video_mod
from fabrica import viewer as viewer_mod
from fabrica import voice as voice_mod
from fabrica.ledger import BudgetError, BudgetExceeded, BudgetNotConfigured, Ledger
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
        except (ValueError, KeyError, voice_mod.VoiceError, voice_mod.ElevenLabsError, BudgetError,
                lab_mod.GoldenError, video_mod.VideoError, video_mod.ProviderError) as e:
            typer.echo(f"✗ {e}", err=True)           # ConfigError, StoryFormatError, голоси, ключі …
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
    old = costs_mod.estimate(shots, costs_mod.load_rates(), attempts=attempts, min_clip_s=min_clip)
    try:                                         # кліпи рівно як піде в API (маршрут + payload, профіль кліпу)
        items = prompts_mod.build(slug, str(part), kinds=["video"], out_root=out)
        est, why = costs_mod.estimate_items(items, attempts=attempts, shots=shots), ""
    except (ValueError, KeyError) as e:          # промпти не збираються — старий кошторис за shots.json
        items, est, why = [], old, str(e).splitlines()[0] if str(e) else type(e).__name__
    if items:
        try:
            prof = providers_mod.generation().get("name", "")
        except providers_mod.ProviderError:
            prof = ""
        typer.echo(f"Кошторис відео {slug} ч.{part} за скомпільованими кліпами ({len(items)} кліпів, профіль "
                   f"{prof or '—'}, × {attempts} спроби):")
        for tier, t in sorted(est.tiers.items(), key=lambda kv: -kv[1].usd):
            typer.echo(f"  {tier:<14} {t.shots:>3} шотів  {t.screen_s:>6g} с у монтаж · генерація {t.billed_s:>5g} с  "
                       f"${t.usd:>8.2f}")
        typer.echo(f"  {'разом':<14} {'':>3}        {'':>6}    ${est.usd:>8.2f}")
        if est.unpriced:
            typer.echo(f"  ⚠️ без ціни в каталозі (не в сумі): {', '.join(est.unpriced)}")
        typer.echo(f"  для порівняння — за екранними секундами shots.json (кліп ≥ {min_clip:g} с): ${old.usd:>8.2f}")
    else:
        typer.echo(f"Кошторис відео {slug} ч.{part} (× {attempts} спроби, кліп ≥ {min_clip:g} с):"
                   + (f"  · промпти не зібрались ({why}) — рахую за shots.json" if why else ""))
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


@app.command()
@friendly
def voice(slug: str = Slug, part: int = Part, out: Path = Out,
          dry_run: bool = typer.Option(False, "--dry-run", help="без мережі й витрат: план, символи, кошторис"),
          force: bool = typer.Option(False, "--force", help="дозволити понад ліміт бюджету (позначається в журналі)")) -> None:
    """Етап voice: репліки shots.json → output/<slug>/part<N>/voice/*.mp3 + manifest.json (ElevenLabs)."""
    shots_path = part_dir(out, slug, part) / "shots.json"
    if not shots_path.exists():
        typer.echo(f"✗ немає {shots_path} — спершу `fabrica shotlist {slug} {part}`", err=True)
        raise typer.Exit(1)
    p = voice_mod.run(slug, part, out, dry_run=dry_run, force=force, log=typer.echo)
    if not dry_run:
        total = sum(i.duration_s or 0 for i in p.items)
        typer.echo(f"✓ {len(p.items)} реплік, {total:.1f} с аудіо → {part_dir(out, slug, part) / 'voice'}")


@app.command()
@friendly
def voices(search: str = typer.Option("", "--search", help="фільтр за назвою або мітками (напр. mexican, female)")) -> None:
    """Голоси в акаунті ElevenLabs — щоб людина обрала voice_id для bible.yaml (кастинг голосів)."""
    rows = voice_mod.client_from_env().voices()
    needle = search.lower()
    for v in rows:
        labels = v.get("labels") or {}
        text = f"{v.get('name', '')} {' '.join(str(x) for x in labels.values())}".lower()
        if needle and needle not in text:
            continue
        info = ", ".join(f"{k}: {val}" for k, val in labels.items() if val)
        typer.echo(f"{v.get('voice_id')}  {v.get('name')}  ({info})")


@app.command()
@friendly
def video(slug: str = Slug, part: int = Part, out: Path = Out,
          dry_run: bool = typer.Option(False, "--dry-run", help="без мережі й витрат: черга, причини блокування, кошторис"),
          only: str = typer.Option(None, "--only", help="один шот, напр. 4.03"),
          force: bool = typer.Option(False, "--force", help="дозволити понад ліміт (позначається в журналі)")) -> None:
    """Етап video: черга відеошотів за golden-промптами лабораторії → output/<slug>/part<N>/video/."""
    jobs = video_mod.run(slug, part, out, dry_run=dry_run, only=only, force=force, log=typer.echo)
    typer.echo(f"Черга: {part_dir(out, slug, part) / 'video' / 'queue.json'}")
    if not dry_run and any(j.state == "failed" for j in jobs):
        raise typer.Exit(1)


def _story(story: str | None) -> str:
    """--story або єдиний серіал у series/ (без _archive)."""
    if story:
        return story
    found = [p.name for p in bible_mod.SERIES.iterdir() if (p / "bible.yaml").exists() and not p.name.startswith("_")]
    if len(found) != 1:
        raise ValueError(f"вкажи --story (серіали: {', '.join(sorted(found)) or 'немає'})")
    return found[0]


@app.command()
@friendly
def prompts(slug: str = Slug,
            set_name: str = typer.Argument(..., metavar="НАБІР", help="casting | test-pack | номер частини 1–4"),
            kind: list[str] = typer.Option(None, "--kind", help="image | video | voice (можна кілька)"),
            only: str = typer.Option(None, "--only", help="один елемент або шот, напр. tp-T1 чи 4.03"),
            sequence: str = typer.Option(None, "--sequence",
                                         help="послідовність із series/<slug>/lab/sequences.yaml, напр. first30"),
            out: Path = Out) -> None:
    """Пакет промптів для ручних тестів: prompts/out/<slug>/<набір або послідовність>/ (*.md + index.html)."""
    for k in kind or []:
        if k not in prompts_mod.KINDS:
            raise ValueError(f"--kind {k}: має бути image, video або voice")
    if sequence:
        seq = prompts_mod.sequences(slug).get(sequence)
        if seq and str(seq["part"]) != set_name:
            raise ValueError(f"послідовність «{sequence}» — з частини {seq['part']}, а набір «{set_name}»")
        items = prompts_mod.select(prompts_mod.sequence_items(slug, sequence, out), kind or None, only, sequence)
    else:
        items = prompts_mod.build(slug, set_name, kind or None, only, out)
    producers = [] if set_name == "casting" else prompts_mod.build(slug, "casting")
    index = viewer_mod.write_package(slug, sequence or set_name, items, producers=producers)
    by_kind = ", ".join(f"{k}: {sum(1 for i in items if i.kind == k)}" for k in prompts_mod.KINDS
                        if any(i.kind == k for i in items))
    typer.echo(f"✓ {len(items)} промптів ({by_kind}) → {index.parent}")
    steps = " · ".join(f"{s.n} {s.title}: {n}" for s in prompts_mod.STEPS
                       if (n := sum(1 for i in items if i.step == s.n)))
    typer.echo(f"  кроки: {steps}")
    warns = [w for i in items for w in i.warnings]
    if warns:
        api, lint = sum(w.startswith("API:") for w in warns), sum(w.startswith("lint:") for w in warns)
        typer.echo(f"  ⚠️ попередження: API {api} · lint {lint} · дані {len(warns) - api - lint} "
                   f"(у {sum(1 for i in items if i.warnings)} елементах; див. переглядач)")
    typer.echo(f"Переглядач: {index}")


lab_app = typer.Typer(help="Лабораторія промптів: журнал ручних тестів і golden.", no_args_is_help=True)
app.add_typer(lab_app, name="lab")


@lab_app.command("log")
@friendly
def lab_log(item: str = typer.Argument(..., help="id елемента з пакета, напр. tp-T1-frame, cast-mateo-front"),
            tool: str = typer.Option(..., "--tool", help="syntx | gemini | nano-banana | dreamina | replicate | elevenlabs"),
            score: int = typer.Option(..., "--score", min=1, max=5, help="оцінка 1–5"),
            file: Path = typer.Option(None, "--file", help="файл результату (копіюється в media/lab/)"),
            notes: str = typer.Option("", "--notes", help="що вийшло, що виправити"),
            story: str = typer.Option(None, "--story", help="серіал (типово — єдиний у series/)")) -> None:
    """Записати результат ручного тесту промпту (прив'язується до версії шаблону й промпту)."""
    slug = _story(story)
    e = lab_mod.log(slug, item, tool, score, file, notes)
    typer.echo(f"✓ #{e['id']} {e['item']} · {e['tool']} · {e['score']}/5 · {e['template']}@v{e['template_version']} "
               f"· промпт {e['prompt_sha']}" + (f" · {e['file']}" if e["file"] else ""))
    if e.get("last_frame"):
        typer.echo(f"  останній кадр: {e['last_frame']}")
    for w in e.get("warnings") or []:
        typer.echo(f"  ⚠️ {w}")
    if e["item"] == item and not item.endswith(lab_mod.LAST):
        if status := progress_mod.on_log(slug, item, score, e["prompt_sha"]):
            typer.echo(f"  статус у студії: {status}")


@lab_app.command("approve")
@friendly
def lab_approve(target: str = typer.Argument(..., help="id шаблону (image.start_frame) або елемента (tp-T1-frame)"),
                force: bool = typer.Option(False, "--force", help="без результату ≥ 4 у журналі"),
                story: str = typer.Option(None, "--story")) -> None:
    """Позначити версію шаблону або промпт елемента як golden — лише їх використовує автоматика."""
    slug = _story(story)
    typer.echo(f"★ {lab_mod.approve(slug, target, force)}")
    if target not in prompts_mod.load_templates():
        item = lab_mod.find_item(slug, target)
        progress_mod.set_status(slug, item.id, "approved", item.prompt_sha)


@lab_app.command("status")
@friendly
def lab_status(story: str = typer.Option(None, "--story")) -> None:
    """Шаблони: версія, golden, скільки тестів і середня оцінка."""
    for line in lab_mod.status(_story(story)):
        typer.echo(line)


@lab_app.command("lessons")
@friendly
def lab_lessons(off: list[str] = typer.Option(None, "--off", help="вимкнути урок, напр. L3 (можна кілька)"),
                on: list[str] = typer.Option(None, "--on", help="увімкнути урок знову"),
                story: str = typer.Option(None, "--story")) -> None:
    """Уроки лабораторії (series/<slug>/lab/lessons.yaml): список; --off / --on — вимкнути / увімкнути."""
    slug = _story(story)
    for lid, active in [*((x, False) for x in off or []), *((x, True) for x in on or [])]:
        lessons_mod.set_active(slug, lid, active)
        typer.echo(f"{'✓ увімкнено' if active else '✗ вимкнено'} {lid}")
    rows = lessons_mod.all(slug)
    if not rows:
        typer.echo(f"Уроків ще немає ({lessons_mod.path(slug).relative_to(config.ROOT).as_posix()}) — їх додає студія.")
    for r in rows:
        scope = ", ".join(f"{k}: {v}" for k, v in (r.get("scope") or {}).items()) or "усі"
        typer.echo(f"{'●' if r.get('active', True) else '○'} {r['id']:<4} [{scope}] {r['rule']}"
                   + (f"\n       проблема: {r['problem']}" if r.get("problem") else ""))


@app.command()
@friendly
def studio(story: str = typer.Option(None, "--story", help="серіал (типово — єдиний у series/)"),
           sequence: str = typer.Option(None, "--sequence", help="послідовність, напр. first30 (типово — перша)"),
           port: int = typer.Option(8765, "--port", min=1, max=65535, help="порт на 127.0.0.1"),
           no_open: bool = typer.Option(False, "--no-open", help="не відкривати браузер")) -> None:
    """Студія: локальний застосунок для ручних тестів (копіювати промпти, позначати прогрес, журнал, «Редагувати»)."""
    from fabrica import studio as studio_mod

    try:
        studio_mod.serve(_story(story), sequence, port, open_browser=not no_open, log=typer.echo)
    except studio_mod.StudioError as e:
        raise ValueError(str(e)) from None


@app.command("schema")
def schema(kind: str = typer.Argument(..., help="script або shots")) -> None:
    """JSON-схема script.json / shots.json (для LLM: local_llm.generate_json)."""
    model = {"script": Script, "shots": Shots}.get(kind)
    if model is None:
        raise typer.BadParameter("script або shots")
    typer.echo(json.dumps(model.model_json_schema(), ensure_ascii=False, indent=2))
