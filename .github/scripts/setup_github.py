#!/usr/bin/env python3
"""Налаштування GitHub для serie-factory: мітки + Project «Producción» з колонками + Issues у Project.

Ідемпотентний: повторний запуск нічого не дублює. Працює на macOS і Windows.

    uv run --no-project .github/scripts/setup_github.py            # мітки + Project
    uv run --no-project .github/scripts/setup_github.py --labels   # лише мітки

Для Project потрібен scope: gh auth refresh -h github.com -s project
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

OWNER = "seriefactory-studio"
REPO = f"{OWNER}/serie-factory"
PROJECT_TITLE = "Producción"
STATUSES = [  # назва, колір, опис
    ("Backlog", "GRAY", "Ідея або задача на потім"),
    ("Ready", "BLUE", "Можна брати в роботу: зрозуміло, що робити"),
    ("In progress", "YELLOW", "Хтось із Claude працює зараз"),
    ("Review", "PURPLE", "PR чекає рев'ю партнера"),
    ("Done", "GREEN", "Змерджено / зроблено"),
]
LABELS = [
    ("area:script", "1D76DB", "Сценарій, біблія, промпти тексту"),
    ("area:video", "D93F0B", "Кадри, референси, голос, відео, QC, монтаж"),
    ("area:publish", "0E8A16", "Нарізка тизерів, публікація, метадані"),
    ("area:infra", "5319E7", "Каркас, CLI, БД, облік витрат, хуки, CI"),
    ("owner:A", "FBCA04", "Claude A — dimaShelest (Mac, контент)"),
    ("owner:B", "C2E0C6", "Claude B — nuchay69-max (Windows, код)"),
]


def gh(*args: str, stdin: str | None = None, check: bool = True) -> str:
    r = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        sys.exit(f"gh {' '.join(args[:3])}… → помилка:\n{r.stderr.strip()}")
    return r.stdout


def gh_json(*args: str) -> dict:
    return json.loads(gh(*args) or "{}")


def graphql(query: str, **variables) -> dict:
    out = json.loads(gh("api", "graphql", "--input", "-",
                        stdin=json.dumps({"query": query, "variables": variables})))
    if out.get("errors"):
        sys.exit(f"GraphQL: {out['errors']}")
    return out["data"]


def setup_labels() -> None:
    existing = {item["name"] for item in json.loads(gh("label", "list", "-R", REPO, "--json", "name", "-L", "200"))}
    for name, color, desc in LABELS:
        verb = "edit" if name in existing else "create"
        flags = ["--color", color, "--description", desc]
        gh("label", verb, name, "-R", REPO, *flags)
        print(f"мітка {name}: {'оновлено' if verb == 'edit' else 'створено'}")


def setup_project(default_status: str) -> None:
    projects = gh_json("project", "list", "--owner", OWNER, "--format", "json").get("projects", [])
    project = next((p for p in projects if p["title"] == PROJECT_TITLE), None)
    if not project:
        project = gh_json("project", "create", "--owner", OWNER, "--title", PROJECT_TITLE, "--format", "json")
        print(f"Project створено: {project.get('url')}")
    num, pid = str(project["number"]), project["id"]
    gh("project", "link", num, "--owner", OWNER, "--repo", REPO, check=False)  # уже прив'язаний — не страшно

    fields = gh_json("project", "field-list", num, "--owner", OWNER, "--format", "json")["fields"]
    status = next(f for f in fields if f["name"] == "Status")
    if [o["name"] for o in status.get("options", [])] != [s[0] for s in STATUSES]:
        data = graphql(
            """mutation($id: ID!, $opts: [ProjectV2SingleSelectFieldOptionInput!]) {
                 updateProjectV2Field(input: {fieldId: $id, singleSelectOptions: $opts}) {
                   projectV2Field { ... on ProjectV2SingleSelectField { options { id name } } } } }""",
            id=status["id"], opts=[{"name": n, "color": c, "description": d} for n, c, d in STATUSES])
        status["options"] = data["updateProjectV2Field"]["projectV2Field"]["options"]
        print("Колонки Status: " + " / ".join(s[0] for s in STATUSES))
    option = {o["name"]: o["id"] for o in status["options"]}[default_status]

    items = gh_json("project", "item-list", num, "--owner", OWNER, "--format", "json", "-L", "500")["items"]
    in_project = {(i.get("content") or {}).get("url") for i in items}
    issues = json.loads(gh("issue", "list", "-R", REPO, "--state", "open", "--json", "url,number,title", "-L", "200"))
    for issue in issues:
        if issue["url"] in in_project:
            continue
        item = gh_json("project", "item-add", num, "--owner", OWNER, "--url", issue["url"], "--format", "json")
        gh("project", "item-edit", "--id", item["id"], "--project-id", pid,
           "--field-id", status["id"], "--single-select-option-id", option)
        print(f"#{issue['number']} {issue['title']} → {default_status}")
    print(f"Готово: https://github.com/orgs/{OWNER}/projects/{num}")


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--labels", action="store_true", help="лише мітки")
    ap.add_argument("--status", default="Ready", choices=[s[0] for s in STATUSES],
                    help="колонка для нових Issues у Project (за замовчуванням Ready)")
    args = ap.parse_args()
    setup_labels()
    if not args.labels:
        setup_project(args.status)
    return 0


if __name__ == "__main__":
    sys.exit(main())
