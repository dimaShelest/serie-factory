"""Етап video: черга генерації відеошотів без прив'язки до провайдера (Issue #5 / критичний шлях п.7).

Автомат бере РІВНО ті промпти, сіди й референси, що й лабораторія (`fabrica prompts <slug> <N> --kind video`),
і лише golden:
- шаблон `video.shot` — golden (lab.require_golden);
- стартовий кадр — файл golden-елемента `p<N>-<шот>-frame` з журналу лабораторії (або вже згенерований).

Черга — output/<slug>/part<N>/video/queue.json: стан кожного шота (blocked / pending / done / failed), причини
блокування, хеш промпту, оцінка вартості. Результат — video/<key>.mp4, де key = sha(промпт + стартовий кадр):
той самий вхід вдруге не генеруємо (кеш). Кожен платний виклик — Ledger.charge() (резерв → факт), тож ліміти,
режим лабораторії (AUTOMATION_ENABLED) і незвірені резерви працюють як у voice.

Провайдер — інтерфейс VideoProvider. Клієнт Replicate (Seedance 2.5) підключимо, коли промпти стануть golden.
Сухий режим (dry_run): без мережі й витрат — план, причини блокування, кошторис.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from fabrica import config
from fabrica import costs as costs_mod
from fabrica import lab as lab_mod
from fabrica import prompts as prompts_mod
from fabrica.ledger import Ledger


class VideoError(RuntimeError):
    """Етап не може працювати: немає провайдера, golden, стартового кадру тощо."""


class ProviderError(RuntimeError):
    def __init__(self, message: str, charged: bool) -> None:
        super().__init__(message)
        self.charged = charged          # False — гроші точно не списано (помилка до прийняття задачі)


class VideoProvider(Protocol):
    name: str

    def submit(self, prompt: str, negative: str, params: dict, first_frame: Path, refs: list[Path]) -> str:
        """Відправити задачу; повертає id задачі провайдера (для звірки з рахунком)."""

    def poll(self, job_id: str) -> tuple[str, str | None]:
        """("running" | "succeeded" | "failed", url результату або текст помилки)."""

    def download(self, url: str, dest: Path) -> None:
        """Зберегти результат у dest."""


class ReplicateProvider:
    """Seedance 2.5 через Replicate. Клієнт підключаємо, коли шаблони відео стануть golden (DECISIONS 2026-10-07)."""

    name = "replicate"

    def __init__(self) -> None:
        raise VideoError("Клієнт Replicate ще не підключено: спершу golden-промпти відео (fabrica lab approve), "
                         "потім підключимо клієнт і REPLICATE_API_TOKEN / SEEDANCE_MODEL у .env.")


@dataclass
class Job:
    shot_id: str
    item_id: str
    prompt_sha: str
    resolution: str
    duration_s: float
    estimate_usd: float
    state: str = "pending"                  # blocked | pending | done | failed
    reasons: list[str] = field(default_factory=list)
    first_frame: str | None = None
    key: str | None = None
    file: str | None = None
    provider_job: str | None = None
    error: str | None = None


def _sha_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _frame_file(slug: str, frame_item_id: str, g: dict, results: list[dict]) -> Path | None:
    """Файл golden-стартового кадру з журналу лабораторії."""
    entry = g["items"].get(slug, {}).get(frame_item_id)
    if not entry or not entry.get("result"):
        return None
    row = next((r for r in results if r["id"] == entry["result"] and r.get("file")), None)
    if not row:
        return None
    path = Path(row["file"]) if Path(row["file"]).is_absolute() else config.ROOT / row["file"]
    return path if path.is_file() else None


def plan(slug: str, part: int, out: Path, *, only: str | None = None, min_clip_s: float = 0.0) -> list[Job]:
    items = {i.id: i for i in prompts_mod.build(slug, str(part), ["image", "video"], out_root=out)}
    g, results = lab_mod.golden(), lab_mod.results(slug)
    rates = costs_mod.load_rates()
    template_ok = True
    videos = [i for i in items.values() if i.kind == "video"]
    if videos:
        try:
            lab_mod.require_golden(videos[0].template)
        except lab_mod.GoldenError:
            template_ok = False
    folder = out / slug / f"part{part}" / "video"
    jobs = []
    for item in videos:
        shot_id = item.id.removeprefix(f"p{part}-").removesuffix("-video")
        if only and shot_id != only:
            continue
        res, dur = item.params.get("resolution", "480p"), float(item.params.get("duration_s", 0))
        job = Job(shot_id, item.id, item.prompt_sha, res, dur, round(rates.get(res, 0) * max(dur, min_clip_s), 4))
        if not template_ok:
            job.reasons.append(f"шаблон {item.template.ref} не golden")
        if item.warnings:
            job.reasons += item.warnings
        frame = _frame_file(slug, f"p{part}-{shot_id}-frame", g, results)
        if frame is None:
            job.reasons.append(f"немає golden-стартового кадру p{part}-{shot_id}-frame (лабораторія)")
        else:
            job.first_frame = frame.as_posix()
            job.key = hashlib.sha256(f"{item.prompt_sha}:{_sha_file(frame)}".encode()).hexdigest()[:24]
            if (folder / f"{job.key}.mp4").exists():
                job.state, job.file = "done", f"{job.key}.mp4"
        if job.reasons and job.state != "done":
            job.state = "blocked"
        jobs.append(job)
    return jobs


def _save(folder: Path, slug: str, part: int, jobs: list[Job]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / "queue.json.tmp"
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"story": slug, "part": part, "jobs": [asdict(j) for j in jobs]},
                           ensure_ascii=False, indent=2) + "\n")
    tmp.replace(folder / "queue.json")


def run(slug: str, part: int, out: Path, *, dry_run: bool = False, provider: VideoProvider | None = None,
        ledger: Ledger | None = None, only: str | None = None, force: bool = False, poll_s: float = 10.0,
        timeout_s: float = 1800.0, log=print, sleep=time.sleep) -> list[Job]:
    folder = out / slug / f"part{part}" / "video"
    jobs = plan(slug, part, out, only=only)
    todo = [j for j in jobs if j.state == "pending"]
    blocked = [j for j in jobs if j.state == "blocked"]
    log(f"Відео {slug} ч.{part}: {len(jobs)} шотів · готово {sum(j.state == 'done' for j in jobs)} · "
        f"до генерації {len(todo)} (≈ ${sum(j.estimate_usd for j in todo):.2f}) · заблоковано {len(blocked)}")
    for j in blocked[:10]:
        log(f"  ⛔ {j.shot_id}: {'; '.join(j.reasons)}")
    if len(blocked) > 10:
        log(f"  … ще {len(blocked) - 10} заблокованих (див. {folder / 'queue.json'})")
    _save(folder, slug, part, jobs)
    if dry_run or not todo:
        return jobs
    provider = provider or ReplicateProvider()
    items = {i.id: i for i in prompts_mod.build(slug, str(part), ["video"], out_root=out)}
    own_ledger = ledger is None
    ledger = ledger or Ledger(out / "fabrica.sqlite")
    try:
        for job in todo:
            item = items[job.item_id]
            lab_mod.require_golden(item.template)              # ще раз: шаблон міг змінитись після плану
            refs = [Path(job.first_frame)]
            with ledger.charge(slug, part, "video", provider.name, estimate_usd=job.estimate_usd,
                               units=job.duration_s, unit="second", input_hash=job.key or "", force=force,
                               note=job.shot_id) as c:
                for w in c.warnings:
                    log(f"  ⚠️ {w}")
                try:
                    job.provider_job = c.request_id = provider.submit(item.prompt, item.negative, item.params,
                                                                      Path(job.first_frame), refs)
                except ProviderError as e:
                    c.not_charged = not e.charged
                    job.state, job.error = "failed", str(e)
                    _save(folder, slug, part, jobs)
                    raise
                started = time.monotonic()
                while True:
                    state, info = provider.poll(job.provider_job)
                    if state == "succeeded":
                        break
                    if state == "failed":
                        job.state, job.error = "failed", info
                        _save(folder, slug, part, jobs)
                        raise ProviderError(f"{job.shot_id}: провайдер повернув помилку: {info}", charged=True)
                    if time.monotonic() - started > timeout_s:
                        job.state, job.error = "failed", "таймаут очікування"
                        _save(folder, slug, part, jobs)
                        raise ProviderError(f"{job.shot_id}: немає результату за {timeout_s:g} с", charged=True)
                    sleep(poll_s)
                dest = folder / f"{job.key}.mp4"
                tmp = dest.with_suffix(".part")
                provider.download(info, tmp)
                tmp.replace(dest)
                job.state, job.file = "done", dest.name
            _save(folder, slug, part, jobs)
            log(f"  ✓ {job.shot_id} → {job.file}")
    finally:
        if own_ledger:
            ledger.close()
    return jobs
