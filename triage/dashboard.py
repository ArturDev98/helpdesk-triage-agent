"""Dashboard de un solo archivo: los datos van embebidos en el HTML, sin servidor ni dependencias."""
import json
from pathlib import Path

from triage.store import now

TEMPLATE = Path(__file__).with_name("dashboard.html")


def payload(store, issues):
    rows = []
    for r in store.rows():
        if r["diagnosis"]:
            r["diagnosis"] = json.loads(r["diagnosis"])
        rows.append(r)
    return {"generatedAt": now(), "tickets": rows,
            "issues": {i.key: {"title": i.title, "status": i.status, "url": i.url} for i in issues.issues()}}


def write_dashboard(store, issues, config):
    out = config.resolve(config.get("dashboard", {}).get("path", "data/dashboard.html"))
    data = json.dumps(payload(store, issues), ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", data)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    return out
