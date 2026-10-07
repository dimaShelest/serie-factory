"""Пакет лабораторії промптів: prompts/out/<slug>/<набір>/ → <елемент>.md, index.html (переглядач), manifest.json.

HTML — один самодостатній файл для телевізора: великий шрифт, темна тема, кнопки «копіювати», параметри,
мініатюри референсів і результатів, нотатки (зберігаються в браузері) і готова команда `fabrica lab log …`.
"""

from __future__ import annotations

import html
import json
import os
from pathlib import Path

from fabrica import config
from fabrica import lab as lab_mod
from fabrica import prompts as prompts_mod

IMAGE = {".png", ".jpg", ".jpeg", ".webp"}
VIDEO = {".mp4", ".mov", ".webm"}
AUDIO = {".mp3", ".wav", ".m4a", ".ogg"}
KIND_UA = {"image": "фото", "video": "відео", "voice": "голос"}
TOOLS = ["gemini", "nano-banana", "syntx", "dreamina", "replicate", "elevenlabs", "other"]


def _rel(path: str, base: Path) -> str:
    target = Path(path) if Path(path).is_absolute() else config.ROOT / path
    return Path(os.path.relpath(target, base)).as_posix()


def _best(rows: list[dict]) -> dict | None:
    with_file = [r for r in rows if r.get("file")]
    return max(with_file, key=lambda r: (r["score"], r["id"])) if with_file else None


def _media(src: str, label: str) -> str:
    ext = Path(src).suffix.lower()
    s, lb = html.escape(src), html.escape(label)
    if ext in IMAGE:
        return f'<figure><a href="{s}" target="_blank"><img src="{s}" alt="{lb}" loading="lazy"></a><figcaption>{lb}</figcaption></figure>'
    if ext in VIDEO:
        return f'<figure><video src="{s}" controls muted preload="metadata"></video><figcaption>{lb}</figcaption></figure>'
    if ext in AUDIO:
        return f'<figure class="audio"><audio src="{s}" controls preload="none"></audio><figcaption>{lb}</figcaption></figure>'
    return f'<figure><a href="{s}">{lb}</a></figure>'


def _copy_block(label: str, text: str, key: str) -> str:
    return (f'<div class="block"><div class="block-head"><span>{html.escape(label)}</span>'
            f'<button class="copy" data-target="{key}">Копіювати</button></div>'
            f'<pre id="{key}">{html.escape(text)}</pre></div>')


def _card(slug: str, item: prompts_mod.Item, base: Path, rows: list[dict], ref_files: dict[str, dict],
          g: dict) -> str:
    golden_item = lab_mod.is_golden_item(slug, item, g)
    state = lab_mod.golden_state(item.template, g)
    mine = [r for r in rows if r["item"] == item.id]
    current = [r for r in mine if r["prompt_sha"] == item.prompt_sha]
    best = max((r["score"] for r in current), default=None)
    kid = item.id.replace(".", "_")
    badges = [f'<span class="badge kind-{item.kind}">{KIND_UA[item.kind]}</span>',
              f'<span class="badge tpl">{html.escape(item.template.ref)} · {html.escape(state)}</span>',
              f'<span class="badge sha">промпт {item.prompt_sha}</span>']
    if golden_item:
        badges.append('<span class="badge golden">★ golden</span>')
    if best is not None:
        badges.append(f'<span class="badge score s{best}">найкраще: {best}/5</span>')
    parts = [f'<article class="card" data-kind="{item.kind}" data-tested="{int(bool(current))}" '
             f'data-golden="{int(golden_item)}" data-search="{html.escape((item.id + " " + item.title).lower())}">',
             f'<header><h2><code>{html.escape(item.id)}</code> {html.escape(item.title)}</h2>{"".join(badges)}</header>']
    for w in item.warnings:
        parts.append(f'<p class="warn">⚠️ {html.escape(w)}</p>')
    if item.kind == "voice" and item.template.id == "voice.line":
        parts.append(_copy_block("Текст репліки (іспанською)", item.prompt, f"p-{kid}"))
    else:
        parts.append(_copy_block("Промпт", item.prompt, f"p-{kid}"))
    if item.negative:
        parts.append(_copy_block("Negative prompt", item.negative, f"n-{kid}"))
    if item.extra.get("preview_es"):
        parts.append(_copy_block("Текст прев'ю голосу (іспанською)", item.extra["preview_es"], f"v-{kid}"))
    rows_html = "".join(f"<tr><th>{html.escape(str(k))}</th><td>{html.escape(json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else str(v))}</td></tr>"
                        for k, v in item.params.items() if v not in (None, ""))
    parts.append(f'<table class="params">{rows_html}</table>')
    if item.refs:
        thumbs = []
        for ref in item.refs:
            r = ref_files.get(ref)
            thumbs.append(_media(_rel(r["file"], base), f"{ref} · {r['score']}/5") if r
                          else f'<span class="chip">{html.escape(ref)} — ще немає</span>')
        parts.append(f'<div class="refs"><h3>Референси (прикріпити до запиту)</h3>{"".join(thumbs)}</div>')
    if item.extra.get("success"):
        li = "".join(f"<li>{html.escape(s)}</li>" for s in item.extra["success"])
        parts.append(f'<div class="success"><h3>Успіх, якщо</h3><ul>{li}</ul></div>')
    if mine:
        res = []
        for r in sorted(mine, key=lambda r: r["id"], reverse=True)[:6]:
            old = "" if r["prompt_sha"] == item.prompt_sha else " (стара версія)"
            label = f"#{r['id']} {r['tool']} · {r['score']}/5{old} — {r.get('notes') or ''}"
            res.append(_media(_rel(r["file"], base), label) if r.get("file")
                       else f'<span class="chip">{html.escape(label)}</span>')
        parts.append(f'<div class="results"><h3>Результати тестів</h3>{"".join(res)}</div>')
    opts = "".join(f"<option>{t}</option>" for t in TOOLS)
    parts.append(
        f'<div class="lab" data-item="{html.escape(item.id)}" data-sha="{item.prompt_sha}" data-story="{html.escape(slug)}">'
        f'<h3>Нотатки й запис результату</h3>'
        f'<textarea placeholder="Що вийшло, що виправити в шаблоні…"></textarea>'
        f'<div class="row"><label>Інструмент <select class="tool">{opts}</select></label>'
        f'<label>Оцінка <select class="score"><option>5</option><option selected>4</option><option>3</option>'
        f'<option>2</option><option>1</option></select></label>'
        f'<label class="grow">Файл <input class="file" placeholder="~/Downloads/результат.png"></label></div>'
        f'<button class="copy-cmd">Копіювати команду журналу</button><pre class="cmd"></pre></div>')
    parts.append("</article>")
    return "".join(parts)


CSS = """
:root{--bg:#0f1115;--card:#171a21;--line:#2a2f3a;--text:#e8e8ea;--muted:#9aa0aa;--accent:#e8a33d;--ok:#3fb27f;--bad:#e5534b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:20px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
.top{position:sticky;top:0;z-index:5;background:#0f1115ee;backdrop-filter:blur(6px);border-bottom:1px solid var(--line);padding:14px 24px}
.top h1{margin:0 0 8px;font-size:26px}.top .sub{color:var(--muted);font-size:16px}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin-top:10px}.filters button,.filters input{font:inherit;font-size:17px}
.filters button{background:var(--card);color:var(--text);border:1px solid var(--line);border-radius:999px;padding:6px 14px;cursor:pointer}
.filters button.on{background:var(--accent);color:#111;border-color:var(--accent)}
.filters input{flex:1;min-width:200px;background:var(--card);color:var(--text);border:1px solid var(--line);border-radius:10px;padding:6px 12px}
main{max-width:1200px;margin:0 auto;padding:20px 24px 80px}
.card{background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px;margin:0 0 22px}
.card h2{font-size:22px;margin:0 0 8px}.card h2 code{color:var(--accent)}
.badge{display:inline-block;font-size:14px;border:1px solid var(--line);border-radius:999px;padding:2px 10px;margin:0 6px 6px 0;color:var(--muted)}
.badge.golden{color:#111;background:var(--accent);border-color:var(--accent)}.badge.s5,.badge.s4{color:var(--ok);border-color:var(--ok)}
.badge.s1,.badge.s2{color:var(--bad);border-color:var(--bad)}
.block{margin:14px 0}.block-head{display:flex;justify-content:space-between;align-items:center;color:var(--muted);font-size:16px}
pre{white-space:pre-wrap;word-break:break-word;background:#0b0d11;border:1px solid var(--line);border-radius:10px;padding:14px;margin:6px 0 0;font:18px/1.55 ui-monospace,Menlo,Consolas,monospace}
button.copy,button.copy-cmd{font:inherit;font-size:16px;background:var(--accent);color:#111;border:0;border-radius:10px;padding:6px 16px;cursor:pointer}
button.done{background:var(--ok)}
.params{border-collapse:collapse;margin:10px 0;font-size:17px}.params th{color:var(--muted);text-align:left;padding:2px 16px 2px 0;font-weight:500}
h3{font-size:17px;color:var(--muted);margin:14px 0 6px;font-weight:600}
.refs,.results{display:flex;flex-wrap:wrap;gap:12px;align-items:flex-start}.refs h3,.results h3{width:100%}
figure{margin:0;width:220px}figure img,figure video{width:220px;border-radius:10px;border:1px solid var(--line);display:block}
figure.audio{width:320px}figure audio{width:320px}figcaption{font-size:14px;color:var(--muted);margin-top:4px}
.chip{display:inline-block;font-size:15px;color:var(--muted);border:1px dashed var(--line);border-radius:10px;padding:6px 10px}
.warn{color:var(--accent);margin:6px 0}.success ul{margin:4px 0 0 22px;color:var(--muted)}
.lab textarea{width:100%;min-height:80px;background:#0b0d11;color:var(--text);border:1px solid var(--line);border-radius:10px;padding:10px;font:inherit;font-size:17px}
.lab .row{display:flex;flex-wrap:wrap;gap:12px;margin:8px 0}.lab label{font-size:16px;color:var(--muted)}.lab .grow{flex:1}
.lab select,.lab input{font:inherit;font-size:16px;background:#0b0d11;color:var(--text);border:1px solid var(--line);border-radius:8px;padding:4px 8px}
.lab input{width:100%}.cmd:empty{display:none}.hidden{display:none}
"""

JS = r"""
function copyText(t,btn){const done=()=>{const o=btn.textContent;btn.textContent='Скопійовано';btn.classList.add('done');setTimeout(()=>{btn.textContent=o;btn.classList.remove('done')},1400)};
 if(navigator.clipboard&&window.isSecureContext){navigator.clipboard.writeText(t).then(done,()=>fallback(t,done))}else{fallback(t,done)}}
function fallback(t,done){const a=document.createElement('textarea');a.value=t;document.body.appendChild(a);a.select();try{document.execCommand('copy')}catch(e){}a.remove();done()}
document.querySelectorAll('button.copy').forEach(b=>b.onclick=()=>copyText(document.getElementById(b.dataset.target).textContent,b));
function q(s){return '"'+s.replace(/\\/g,'\\\\').replace(/"/g,'\\"')+'"'}
document.querySelectorAll('.lab').forEach(box=>{const key='lab:'+box.dataset.item+':'+box.dataset.sha;const ta=box.querySelector('textarea');
 try{ta.value=localStorage.getItem(key)||''}catch(e){}ta.oninput=()=>{try{localStorage.setItem(key,ta.value)}catch(e){}};
 box.querySelector('.copy-cmd').onclick=(ev)=>{const tool=box.querySelector('.tool').value,score=box.querySelector('.score').value,file=box.querySelector('.file').value.trim();
  let c='uv run fabrica lab log '+box.dataset.item+' --story '+box.dataset.story+' --tool '+tool+' --score '+score;if(file)c+=' --file '+q(file);if(ta.value.trim())c+=' --notes '+q(ta.value.trim());
  box.querySelector('.cmd').textContent=c;copyText(c,ev.target)}});
let kind='all',flag='all';const search=document.getElementById('search');
function apply(){const s=search.value.trim().toLowerCase();document.querySelectorAll('.card').forEach(c=>{let ok=(kind==='all'||c.dataset.kind===kind);
 if(flag==='untested')ok=ok&&c.dataset.tested==='0';if(flag==='golden')ok=ok&&c.dataset.golden==='1';if(s)ok=ok&&c.dataset.search.includes(s);c.classList.toggle('hidden',!ok)})}
document.querySelectorAll('[data-kind-filter]').forEach(b=>b.onclick=()=>{kind=b.dataset.kindFilter;document.querySelectorAll('[data-kind-filter]').forEach(x=>x.classList.toggle('on',x===b));apply()});
document.querySelectorAll('[data-flag]').forEach(b=>b.onclick=()=>{flag=flag===b.dataset.flag?'all':b.dataset.flag;document.querySelectorAll('[data-flag]').forEach(x=>x.classList.toggle('on',x.dataset.flag===flag));apply()});
search.oninput=apply;
"""


def ref_files(slug: str, rows: list[dict], producers: list[prompts_mod.Item]) -> dict[str, dict]:
    """id референсу → найкращий результат тесту елемента, що його створює (файл + оцінка)."""
    by_item = {}
    for r in rows:
        by_item.setdefault(r["item"], []).append(r)
    out = {}
    for it in producers:
        if it.produces and (best := _best(by_item.get(it.id, []))):
            out[it.produces] = best
    return out


def build_html(slug: str, set_name: str, items: list[prompts_mod.Item], base: Path,
               producers: list[prompts_mod.Item] | None = None) -> str:
    rows, g = lab_mod.results(slug), lab_mod.golden()
    refs = ref_files(slug, rows, (producers or []) + items)
    counts = {k: sum(1 for i in items if i.kind == k) for k in KIND_UA}
    tested = sum(1 for i in items if any(r["item"] == i.id and r["prompt_sha"] == i.prompt_sha for r in rows))
    cards = "".join(_card(slug, i, base, rows, refs, g) for i in items)
    kinds = "".join(f'<button data-kind-filter="{k}">{v} ({counts[k]})</button>' for k, v in KIND_UA.items() if counts[k])
    title = f"{slug} · {set_name} · лабораторія промптів"
    return (f'<!doctype html><html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>{html.escape(title)}</title><style>{CSS}</style></head><body>'
            f'<div class="top"><h1>{html.escape(slug.upper())} · {html.escape(set_name)}</h1>'
            f'<div class="sub">{len(items)} промптів · протестовано {tested} · режим лабораторії: автоматика вимкнена, '
            f'тестуємо руками → <code>fabrica lab log</code> → <code>fabrica lab approve</code></div>'
            f'<div class="filters"><button data-kind-filter="all" class="on">усі ({len(items)})</button>{kinds}'
            f'<button data-flag="untested">без результату</button><button data-flag="golden">★ golden</button>'
            f'<input id="search" placeholder="пошук: mateo, T1, dawn…"></div></div>'
            f'<main>{cards}</main><script>{JS}</script></body></html>')


def item_md(slug: str, item: prompts_mod.Item) -> str:
    lines = [f"# {item.id} — {item.title}", "",
             f"- Шаблон: `{item.template.ref}` (sha {item.template.sha}) · промпт `{item.prompt_sha}`",
             f"- Тип: {KIND_UA[item.kind]} · референси: {', '.join(item.refs) or '—'}", ""]
    lines += [f"> ⚠️ {w}" for w in item.warnings]
    lines += ["## Промпт", "", "```text", item.prompt, "```", ""]
    if item.negative:
        lines += ["## Negative", "", "```text", item.negative, "```", ""]
    if item.extra.get("preview_es"):
        lines += ["## Прев'ю голосу", "", "```text", item.extra["preview_es"], "```", ""]
    lines += ["## Параметри", "", "```json", json.dumps(item.params, ensure_ascii=False, indent=2), "```", ""]
    if item.extra.get("success"):
        lines += ["## Успіх, якщо", ""] + [f"- {s}" for s in item.extra["success"]] + [""]
    lines += ["## Записати результат", "", "```text",
              f'uv run fabrica lab log {item.id} --story {slug} --tool <інструмент> --score <1-5> --file "<шлях>" --notes "<що вийшло>"',
              "```", ""]
    return "\n".join(lines)


def write_package(slug: str, set_name: str, items: list[prompts_mod.Item], out: Path = prompts_mod.OUT,
                  producers: list[prompts_mod.Item] | None = None) -> Path:
    folder = out / slug / set_name
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("*.md"):
        old.unlink()
    for it in items:
        with (folder / f"{it.id}.md").open("w", encoding="utf-8", newline="\n") as f:
            f.write(item_md(slug, it))
    manifest = [{"id": i.id, "kind": i.kind, "template": i.template.ref, "template_sha": i.template.sha,
                 "prompt_sha": i.prompt_sha, "refs": i.refs, "produces": i.produces, "params": i.params,
                 "prompt": i.prompt, "negative": i.negative, "warnings": i.warnings} for i in items]
    with (folder / "manifest.json").open("w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"story": slug, "set": set_name, "items": manifest}, ensure_ascii=False, indent=2) + "\n")
    index = folder / "index.html"
    with index.open("w", encoding="utf-8", newline="\n") as f:
        f.write(build_html(slug, set_name, items, folder, producers))
    return index
