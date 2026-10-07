"""Етап video: черга генерації кліпів за golden-елементами лабораторії (Issue #5 / критичний шлях п.7).

Автомат надсилає РІВНО той маршрут і payload, що їх бачила лабораторія (`fabrica prompts <slug> <N>`, крок 6):
item.route («<провайдер>:<модель>», prompts/providers.yaml) + item.payload (тривалість, роздільність, сід …;
файли — «ref:<id>»). Golden-кліп лабораторії (затверджений для поточного prompt_sha, з файлом) черга не генерує
вдруге: кліп готовий (source "lab"), наступний стартує з його останнього кадру. Решта — ворота:
- шаблон кожного відео-елемента golden (lab.require_golden; шаблони різні за режимом: i2v / first_last / t2v);
- кожен «ref:» у payload — файл golden-елемента для ПОТОЧНОГО prompt_sha (lab.golden_file): змінили промпт кадру —
  старий golden-кадр автоматиці не годиться. «<produces>.last» (кліп k ≥ 2, handoff continue), коли кліп k-1 —
  у цій черзі: лише кадр самого кліпу k-1 (golden-кліпу лабораторії або зробленого чергою — video/<key>.last.png,
  ffmpeg); поки його немає — «чекає на кліп …» (кліп k не піде з чужого кадру, і за нього не заплатимо двічі);
- payload проходить providers.validate («API: …» блокує завжди); інші попередження елемента блокують, доки сам
  елемент не golden (людина бачила їх і затвердила);
- ціна виклику відома (costs.call_usd: каталог маршрутів → COSTS.md); немає — блок: резерв $0 обійшов би ліміти.

Черга — output/<slug>/part<N>/video/queue.json: стан кожного кліпу (blocked / pending / done / failed), причини,
маршрут, файли референсів, кошторис. --only лише обмежує, що запускаємо: у queue.json — уся черга; provider_job
готових кліпів (той самий key) переноситься з попереднього стану. Результат — video/<key>.<mp4|mov>,
key = sha(маршрут + payload + sha файлів референсів; кадр, витягнутий з кліпу, — sha самого кліпу, бо інший ffmpeg
дає інші байти PNG): той самий вхід вдруге не генеруємо (кеш). Після завантаження — останній кадр поруч (для
наступного кліпу) і перепланування черги. Кожен платний виклик — Ledger.charge() (резерв → факт): ліміти, режим
лабораторії (AUTOMATION_ENABLED) і незвірені резерви.

Провайдер — VideoProvider: submit(route, payload, files {ref_id: Path}). ReplicateProvider і CloudflareProvider —
заглушки: build_request() уже складає запит (перевірка payload, «ref:» → файли; без мережі), виклики — «не
підключено». Сухий режим (dry_run): без мережі й витрат — план, причини блокування, кошторис.
"""

from __future__ import annotations

import base64
import hashlib
import json
import mimetypes
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Protocol

from fabrica import config
from fabrica import costs as costs_mod
from fabrica import lab as lab_mod
from fabrica import prompts as prompts_mod
from fabrica import providers as providers_mod
from fabrica.ledger import Ledger

REF_RE = re.compile(r"ref:(\S+)")          # «ref:<id>» — увесь рядок; «ref: …» з пробілом — це текст
ROLE = {"image": "стартовий кадр", "last_frame_image": "кінцевий кадр"}     # решта «ref:» — референси


class VideoError(RuntimeError):
    """Етап не може працювати: немає провайдера, golden, стартового кадру тощо."""


class ProviderError(RuntimeError):
    def __init__(self, message: str, charged: bool) -> None:
        super().__init__(message)
        self.charged = charged          # False — гроші точно не списано (помилка до прийняття задачі)


class VideoProvider(Protocol):
    name: str

    def submit(self, route: str, payload: dict, files: dict[str, Path]) -> str:
        """Відправити payload як є («ref:<id>» → files[id]); повертає id задачі провайдера (для звірки з рахунком)."""

    def poll(self, job_id: str) -> tuple[str, str | None]:
        """("running" | "succeeded" | "failed", url результату або текст помилки)."""

    def download(self, url: str, dest: Path) -> None:
        """Зберегти результат у dest."""


# ---------------------------------------------------------------- референси payload


def ref_id(v) -> str | None:
    """«ref:<id>» → id; інше — None."""
    m = REF_RE.fullmatch(v) if isinstance(v, str) else None
    return m.group(1) if m else None


def refs_in(payload) -> list[str]:
    """Id референсів payload у порядку появи: «ref:<id>» у рядках, списках і вкладених словниках."""
    out: list[str] = []

    def walk(v) -> None:
        if rid := ref_id(v):
            out.append(rid)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)

    walk(payload)
    return list(dict.fromkeys(out))


def resolve_refs(payload, files: dict[str, Path], to: Callable[[Path], str] = lambda p: p.as_posix()):
    """Копія payload: кожне «ref:<id>» → to(files[id]). Файлу для референсу немає — VideoError."""
    if rid := ref_id(payload):
        if rid not in files:
            raise VideoError(f"немає файлу для «{payload}» (files[«{rid}»])")
        return to(Path(files[rid]))
    if isinstance(payload, (list, tuple)):
        return [resolve_refs(x, files, to) for x in payload]
    if isinstance(payload, dict):
        return {k: resolve_refs(v, files, to) for k, v in payload.items()}
    return payload


def data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode('ascii')}"


# ---------------------------------------------------------------- провайдери (заглушки)


class _Stub:
    """Спільне для заглушок: запит будуємо й перевіряємо вже зараз, відправку підключимо після golden."""

    name = ""
    title = ""
    token_env = ""
    connected = False

    def _route(self, route: str, payload: dict) -> providers_mod.Route:
        r = providers_mod.route(route)
        if r.provider != self.name or r.kind != "video":
            raise VideoError(f"маршрут {route} — не відео {self.title}")
        if errors := providers_mod.validate(route, payload):
            raise VideoError(f"payload {route} не пройде API: " + "; ".join(errors))
        return r

    def build_request(self, route: str, payload: dict, files: dict[str, Path]) -> dict:
        """{method, url, auth_env, json}: тіло рівно з payload, «ref:» → файли. Ключа немає — лише ім'я змінної."""
        raise NotImplementedError

    def _off(self):
        raise VideoError(f"Клієнт {self.title} ще не підключено: спершу golden-промпти відео (`fabrica lab approve`), "
                         f"потім підключимо клієнт і {self.token_env} у .env.")

    def submit(self, route: str, payload: dict, files: dict[str, Path]) -> str:
        self._off()

    def poll(self, job_id: str) -> tuple[str, str | None]:
        self._off()

    def download(self, url: str, dest: Path) -> None:
        self._off()


class ReplicateProvider(_Stub):
    """Seedance через Replicate: POST /v1/models/<модель>/predictions, тіло {"input": payload}. Локальні файли клієнт
    завантажує сам (Replicate приймає URL, upload або data URI < 1 МБ) — тут вони лишаються шляхами."""

    name, title, token_env = "replicate", "Replicate", "REPLICATE_API_TOKEN"
    API = "https://api.replicate.com/v1"

    def build_request(self, route: str, payload: dict, files: dict[str, Path]) -> dict:
        r = self._route(route, payload)
        return {"method": "POST", "url": f"{self.API}/models/{r.model}/predictions", "auth_env": self.token_env,
                "json": {"input": resolve_refs(payload, files)}}


class CloudflareProvider(_Stub):
    """Seedance через Cloudflare Workers AI: тіло = payload. UNVERIFIED: REST-шлях (офіційно — Worker env.AI.run) і
    base64 data URI замість публічного https-URL файлу."""

    name, title, token_env = "cloudflare", "Cloudflare Workers AI", "CLOUDFLARE_API_TOKEN"

    def __init__(self, account_id: str | None = None) -> None:
        self.account_id = account_id or config.get("CLOUDFLARE_ACCOUNT_ID") or "$CLOUDFLARE_ACCOUNT_ID"

    def build_request(self, route: str, payload: dict, files: dict[str, Path]) -> dict:
        r = self._route(route, payload)
        return {"method": "POST", "url": f"https://api.cloudflare.com/client/v4/accounts/{self.account_id}/ai/run/"
                f"{r.model}", "auth_env": self.token_env, "json": resolve_refs(payload, files, data_uri)}


PROVIDERS: dict[str, type[_Stub]] = {"replicate": ReplicateProvider, "cloudflare": CloudflareProvider}


# ---------------------------------------------------------------- план


@dataclass
class Job:
    shot_id: str
    item_id: str
    prompt_sha: str
    resolution: str
    duration_s: float
    estimate_usd: float                     # 0.0 і причина в reasons — ціни немає
    route: str = ""
    clip: int = 1
    state: str = "pending"                  # blocked | pending | done | failed
    reasons: list[str] = field(default_factory=list)
    first_frame: str | None = None          # стартовий файл (payload.image)
    files: dict[str, str] = field(default_factory=dict)    # id референсу → файл
    key: str | None = None
    file: str | None = None                 # queue: ім'я у теці черги (<key>.mp4); lab: шлях golden-кліпу
    last_frame: str | None = None           # queue: <key>.last.png; lab: шлях кадру — старт наступного кліпу
    provider_job: str | None = None
    error: str | None = None
    source: str = "queue"                   # queue — генерує черга; lab — golden-кліп лабораторії (не генеруємо)


_SHA: dict[tuple[str, int, int], str] = {}


def _sha_file(path: Path) -> str:
    """sha256 файлу (кеш за шляхом, розміром і часом зміни: кліпи хешуються при кожному переплануванні)."""
    st = Path(path).stat()
    k = (str(path), st.st_size, st.st_mtime_ns)
    if k not in _SHA:
        h = hashlib.sha256()
        with Path(path).open("rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _SHA[k] = h.hexdigest()
    return _SHA[k]


def cache_key(route: str, payload: dict, files: dict[str, Path], ident: dict[str, str] | None = None) -> str:
    """sha(маршрут + payload + sha кожного файлу референсу): інший кадр чи будь-яке поле — новий кліп.
    ident — готовий відбиток замість sha файлу (кадр, витягнутий з кліпу → «clip:<sha кліпу>»)."""
    h = hashlib.sha256(json.dumps({"route": route, "payload": payload}, ensure_ascii=False, sort_keys=True).encode())
    for rid in sorted(files):
        h.update(f"\n{rid}:{(ident or {}).get(rid) or _sha_file(Path(files[rid]))}".encode())
    return h.hexdigest()[:24]


def _shot(item: prompts_mod.Item, part: int) -> str:
    return item.extra.get("shot") or re.sub(r"-video(-\d+)?$", "", item.id.removeprefix(f"p{part}-"))


def _clip_no(item: prompts_mod.Item) -> int:
    c = item.extra.get("clip")
    if isinstance(c, dict) and isinstance(c.get("index"), int):
        return c["index"]
    m = re.search(r"-video-(\d+)$", item.id)
    return int(m.group(1)) if m else 1


def _items(slug: str, part: int, out: Path) -> tuple[list[prompts_mod.Item], dict[str, prompts_mod.Item]]:
    """Відео-елементи частини (у порядку виробництва) + хто створює кожен референс (частина; кастинг — якщо треба)."""
    items = prompts_mod.build(slug, str(part), out_root=out)
    producers = {i.produces: i for i in reversed(items) if i.produces}
    videos = [i for i in items if i.kind == "video"]
    wanted = {r for v in videos for r in refs_in(v.payload)}
    if any(r not in producers and r.removesuffix(".last") not in producers for r in wanted):
        try:
            producers = {**{i.produces: i for i in reversed(prompts_mod.build(slug, "casting")) if i.produces},
                         **producers}
        except prompts_mod.PromptError:
            pass
    return videos, producers


@dataclass
class _Own:
    """Кліп цієї черги, що дає «<produces>.last»: golden-кліп лабораторії або зроблений чергою."""
    clip: Path
    frame: Path
    job: Job
    derived: bool = True        # кадр витягнуто з кліпу (ffmpeg); False — записаний руками «<кліп>-last»


class _Planner:
    """Файли референсів для автоматики: лише golden для поточного промпту; «.last» кліпу цієї черги — лише кадр
    самого кліпу (golden лабораторії або зробленого чергою), а не будь-який кадр з журналу."""

    def __init__(self, slug: str, producers: dict[str, prompts_mod.Item], queue: set[str]) -> None:
        self.slug, self.producers, self.queue = slug, producers, queue
        self.g, self.rows = lab_mod.golden(), lab_mod.results(slug)
        self.own: dict[str, _Own] = {}
        self.ident: dict[str, str] = {}                     # референс → відбиток для ключа кешу (кадр із кліпу)
        self.templates: dict[str, str | None] = {}

    def template(self, t: prompts_mod.Template) -> str | None:
        if t.id not in self.templates:
            try:
                lab_mod.require_golden(t)
                self.templates[t.id] = None
            except lab_mod.GoldenError:
                self.templates[t.id] = f"шаблон {t.ref} не golden ({lab_mod.golden_state(t, self.g)})"
        return self.templates[t.id]

    def lab_clip(self, item: prompts_mod.Item) -> tuple[Path, Path | None, bool] | str | None:
        """Golden-кліп лабораторії для поточного prompt_sha: (кліп, його кадр або None, кадр витягнуто з кліпу).
        Рядок — golden є, а кліпу на диску немає / це не відео (блок: за затверджене вдруге не платимо);
        None — golden-кліпу з файлом немає (--force без результату, результат без файлу) — генерує черга."""
        row = lab_mod.golden_result(self.slug, item, g=self.g, rows=self.rows)
        if not row or not row.get("file"):
            return None
        clip = lab_mod.stored_path(row["file"])
        if clip.suffix.lower() not in lab_mod.VIDEO:
            return f"golden-результат {item.id} (#{row.get('id')}) — не відео ({clip.name}): залогуй кліп і затверди"
        if not clip.is_file():
            return (f"golden-кліп {item.id} (#{row.get('id')}) є, але файлу {row['file']} на диску немає — поверни "
                    "його в media/lab/ або затверди інший результат (затверджене вдруге не генеруємо)")
        frame = lab_mod.golden_file(self.slug, item, last=True, g=self.g, rows=self.rows)
        auto = lab_mod.stored_path(row["last_frame"]) if row.get("last_frame") else None
        return clip, frame, frame is None or frame == auto

    def file(self, ref: str) -> tuple[Path | None, str | None]:
        """(файл, None) або (None, причина блокування)."""
        if (o := self.own.get(ref)) is not None:            # кліп k-1 цієї черги готовий — кадр із нього
            if not o.frame.is_file():
                found, warn = lab_mod.extract_last_frame(o.clip, o.frame, item_id=o.job.item_id)
                if not found:
                    return None, warn
                o.job.last_frame = found.name if o.job.source == "queue" else found.as_posix()
            if o.derived:
                self.ident[ref] = f"clip:{_sha_file(o.clip)}"
            return o.frame, None
        last = ref not in self.producers and ref.endswith(".last")
        src = self.producers.get(ref.removesuffix(".last") if last else ref)
        if src is None:
            return None, "немає елемента, що його створює"
        if last and src.id in self.queue:
            return None, (f"чекає на кліп {src.id} цієї черги (його ще немає, golden-кліпу з файлом у лабораторії "
                          "теж) — кліп стартує лише з кадру саме того кліпу")
        if found := lab_mod.golden_file(self.slug, src, last=last, g=self.g, rows=self.rows):
            return found, None
        old = (self.g["items"].get(self.slug) or {}).get(src.id)
        if old and old.get("prompt_sha") != src.prompt_sha:
            return None, (f"{src.id} golden для старої версії промпту {old.get('prompt_sha')}, зараз "
                          f"{src.prompt_sha} — протестуй і затверди знову (`fabrica lab approve {src.id}`)")
        if not old:
            return None, f"{src.id} не golden (лабораторія: `fabrica lab log …` → `fabrica lab approve {src.id}`)"
        if last:
            return None, (f"у golden-кліпу {src.id} немає останнього кадру — "
                          f"`fabrica lab log {src.id}{lab_mod.LAST} --file …`")
        return None, f"у golden-результату {src.id} немає файлу на диску"


def _plan(slug: str, part: int, out: Path) -> tuple[list[Job], dict[str, prompts_mod.Item]]:
    """Уся черга частини (--only фільтрують викликачі: кліп k залежить від k-1, тож плануємо все)."""
    videos, producers = _items(slug, part, out)
    pl = _Planner(slug, producers, {i.id for i in videos})
    folder = out / slug / f"part{part}" / "video"
    jobs: list[Job] = []
    for item in videos:
        route, payload = item.route, item.payload
        usd = costs_mod.call_usd(route, payload) if route and payload else None
        job = Job(_shot(item, part), item.id, item.prompt_sha,
                  str(costs_mod.field_value(route, payload, "resolution") or ""),
                  float(costs_mod.field_value(route, payload, "duration") or 0), usd or 0.0, route, _clip_no(item))
        jobs.append(job)
        lab = pl.lab_clip(item)
        if isinstance(lab, tuple):                          # затверджений кліп лабораторії — не генеруємо
            clip, frame, derived = lab
            frame = frame or folder / f"{item.id}.last.png"
            job.state, job.source, job.file = "done", "lab", clip.as_posix()
            job.last_frame = frame.as_posix() if frame.is_file() else None
            if item.produces:
                pl.own[f"{item.produces}.last"] = _Own(clip, frame, job, derived)
            continue
        if lab:
            job.reasons.append(lab)
        if not route or not payload:
            job.state = "blocked"
            job.reasons.append("елемент без маршруту / payload (старий формат пакета) — перезбери промпти")
            continue
        if why := pl.template(item.template):
            job.reasons.append(why)
        try:
            job.reasons += providers_mod.validate(route, payload)
        except providers_mod.ProviderError as e:
            job.reasons.append(f"{providers_mod.PREFIX}{e}")
        if usd is None:
            job.reasons.append(f"немає ціни для {route} @ {job.resolution or '?'} — впиши ставку в docs/COSTS.md "
                               "або price у prompts/providers.yaml (резерв $0 обійшов би ліміти бюджету)")
        other = [w for w in item.warnings if not w.startswith(providers_mod.PREFIX)]
        if other and not lab_mod.is_golden_item(slug, item, pl.g):
            job.reasons += other + ["попередження вище блокують, доки елемент не golden (`fabrica lab approve`)"]
        files: dict[str, Path] = {}
        roles = {ref_id(v): ROLE.get(k, "референс") for k, v in payload.items() if ref_id(v)}
        for ref in refs_in(payload):
            found, why = pl.file(ref)
            if found:
                files[ref] = found
            else:
                job.reasons.append(f"{roles.get(ref, 'референс')} «{ref}»: {why}")
        job.files = {k: v.as_posix() for k, v in files.items()}
        job.first_frame = job.files.get(ref_id(payload.get("image")) or "")
        if len(files) == len(refs_in(payload)):
            job.key = cache_key(route, payload, files, {r: pl.ident[r] for r in files if r in pl.ident})
            dest = folder / f"{job.key}.{payload.get('output_format') or 'mp4'}"
            frame = folder / f"{job.key}.last.png"
            if dest.exists():
                job.state, job.file = "done", dest.name
                job.last_frame = frame.name if frame.is_file() else None
                if item.produces:
                    pl.own[f"{item.produces}.last"] = _Own(dest, frame, job)
        if job.reasons and job.state != "done":
            job.state = "blocked"
    return jobs, {i.id: i for i in videos}


def _only(jobs: list[Job], only: str | None) -> list[Job]:
    return [j for j in jobs if not only or only in (j.shot_id, j.item_id)]


def plan(slug: str, part: int, out: Path, *, only: str | None = None) -> list[Job]:
    return _only(_plan(slug, part, out)[0], only)


def _previous(folder: Path) -> dict[str, dict]:
    """Попередній стан queue.json: item_id → кліп (для provider_job). Немає / зіпсований — порожньо."""
    try:
        data = json.loads((folder / "queue.json").read_text(encoding="utf-8-sig"))
        return {j["item_id"]: j for j in data.get("jobs", []) if isinstance(j, dict) and j.get("item_id")}
    except (OSError, ValueError, AttributeError, TypeError):
        return {}


def _carry(jobs: list[Job], prev: dict[str, dict]) -> list[Job]:
    """provider_job готових кліпів із попереднього стану (той самий key): id задачі — для звірки з рахунком."""
    for j in jobs:
        p = prev.get(j.item_id) or {}
        if j.state == "done" and j.key and p.get("key") == j.key and not j.provider_job:
            j.provider_job = p.get("provider_job")
    return jobs


def _save(folder: Path, slug: str, part: int, jobs: list[Job]) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / "queue.json.tmp"
    with tmp.open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"story": slug, "part": part, "jobs": [asdict(j) for j in jobs]},
                           ensure_ascii=False, indent=2) + "\n")
    config.replace_atomic(tmp, folder / "queue.json")


def _report(jobs: list[Job], folder: Path, slug: str, part: int, log) -> None:
    todo = [j for j in jobs if j.state == "pending"]
    blocked = [j for j in jobs if j.state == "blocked"]
    log(f"Відео {slug} ч.{part}: {len(jobs)} кліпів · готово {sum(j.state == 'done' for j in jobs)} · "
        f"до генерації {len(todo)} (≈ ${sum(j.estimate_usd for j in todo):.2f}) · заблоковано {len(blocked)}")
    for j in blocked[:10]:
        log(f"  ⛔ {j.item_id}: {'; '.join(j.reasons)}")
    if len(blocked) > 10:
        log(f"  … ще {len(blocked) - 10} заблокованих (див. {folder / 'queue.json'})")


# ---------------------------------------------------------------- запуск


def run(slug: str, part: int, out: Path, *, dry_run: bool = False, provider: VideoProvider | None = None,
        ledger: Ledger | None = None, only: str | None = None, force: bool = False, poll_s: float = 10.0,
        timeout_s: float = 1800.0, log=print, sleep=time.sleep) -> list[Job]:
    folder = out / slug / f"part{part}" / "video"
    every, items = _plan(slug, part, out)
    jobs = _only(_carry(every, _previous(folder)), only)
    _report(jobs, folder, slug, part, log)
    _save(folder, slug, part, every)
    todo = [j for j in jobs if j.state == "pending"]
    if dry_run or not todo:
        return jobs
    clients: dict[str, VideoProvider] = {}

    def client(route: str) -> VideoProvider:
        if provider is not None:
            return provider
        name = route.partition(":")[0]
        if name not in clients:
            if name not in PROVIDERS:
                raise VideoError(f"маршрут {route}: відео-провайдера «{name}» немає ({', '.join(PROVIDERS)})")
            clients[name] = PROVIDERS[name]()
        return clients[name]

    for j in todo:                                    # заглушки зупиняють до будь-якого резерву в журналі витрат
        if not getattr(c := client(j.route), "connected", True):
            c._off()
    own_ledger = ledger is None
    ledger = ledger or Ledger(out / "fabrica.sqlite")
    tried: set[str] = set()
    try:
        while job := next((j for j in jobs if j.state == "pending" and j.item_id not in tried), None):
            tried.add(job.item_id)
            item, prov = items[job.item_id], client(job.route)
            lab_mod.require_golden(item.template)              # ще раз: шаблон міг змінитись після плану
            files = {k: Path(v) for k, v in job.files.items()}
            with ledger.charge(slug, part, "video", prov.name, estimate_usd=job.estimate_usd,
                               units=job.duration_s, unit="second", input_hash=job.key or "", force=force,
                               note=job.item_id) as c:
                for w in c.warnings:
                    log(f"  ⚠️ {w}")
                try:
                    job.provider_job = c.request_id = prov.submit(item.route, item.payload, files)
                except ProviderError as e:
                    c.not_charged = not e.charged
                    job.state, job.error = "failed", str(e)
                    _save(folder, slug, part, every)
                    raise
                started = time.monotonic()
                while True:
                    state, info = prov.poll(job.provider_job)
                    if state == "succeeded":
                        break
                    if state == "failed":
                        job.state, job.error = "failed", info
                        _save(folder, slug, part, every)
                        raise ProviderError(f"{job.item_id}: провайдер повернув помилку: {info}", charged=True)
                    if time.monotonic() - started > timeout_s:
                        job.state, job.error = "failed", "таймаут очікування"
                        _save(folder, slug, part, every)
                        raise ProviderError(f"{job.item_id}: немає результату за {timeout_s:g} с", charged=True)
                    sleep(poll_s)
                dest = folder / f"{job.key}.{item.payload.get('output_format') or 'mp4'}"
                tmp = dest.with_suffix(".part")
                prov.download(info, tmp)
                config.replace_atomic(tmp, dest)
                job.state, job.file = "done", dest.name
            frame, warn = lab_mod.extract_last_frame(dest, folder / f"{job.key}.last.png", item_id=job.item_id)
            job.last_frame = frame.name if frame else None
            if warn:
                log(f"  ⚠️ {warn}")
            _save(folder, slug, part, every)
            log(f"  ✓ {job.item_id} → {job.file}")
            prev = {j.item_id: asdict(j) for j in every}
            every, items = _plan(slug, part, out)               # наступний кліп стартує з кадру щойно зробленого
            jobs = _only(_carry(every, prev), only)
            _save(folder, slug, part, every)
    finally:
        if own_ledger:
            ledger.close()
    return jobs
