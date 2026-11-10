"""Estado en SQLite: qué se procesó, con qué resultado, y la memoria de tickets cerrados.
Nunca guarda al solicitante; los textos entran ya redactados."""
import json
import sqlite3
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY, title TEXT, description TEXT, opened_at TEXT,
    status TEXT, closed_at TEXT, solution TEXT
);
CREATE TABLE IF NOT EXISTS results (
    ticket_id TEXT PRIMARY KEY REFERENCES tickets(id), processed_at TEXT, brain TEXT,
    category TEXT, module TEXT, severity TEXT, summary TEXT, needs_code INTEGER,
    relation_kind TEXT, relation_ref TEXT, relation_confidence TEXT, relation_reason TEXT,
    diagnosis TEXT, action TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def processed(self, ticket_id):
        return self.db.execute("SELECT 1 FROM results WHERE ticket_id = ?", (ticket_id,)).fetchone() is not None

    def save_ticket(self, t):
        self.db.execute(
            "INSERT INTO tickets VALUES (?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status, "
            "closed_at=excluded.closed_at, solution=COALESCE(excluded.solution, tickets.solution)",
            (t.id, t.title, t.description, t.opened_at, t.status, t.closed_at, t.solution))
        self.db.commit()

    def save_result(self, r, error=None):
        tr, rel = r.triage, r.relation
        self.db.execute(
            "INSERT OR REPLACE INTO results VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (r.ticket_id, now(), r.brain, tr.category, tr.module, tr.severity, tr.summary, int(tr.needs_code),
             rel.kind, rel.ref, rel.confidence, rel.reason,
             json.dumps(r.to_dict()["diagnosis"], ensure_ascii=False) if r.diagnosis else None, r.action, error))
        self.db.commit()

    def save_error(self, ticket_id, brain, error):
        self.db.execute("INSERT OR REPLACE INTO results (ticket_id, processed_at, brain, action, error) "
                        "VALUES (?,?,?,?,?)", (ticket_id, now(), brain, "revisión manual", error))
        self.db.commit()

    def closed_memory(self, since, limit):
        """Tickets cerrados con solución, los más recientes primero: la base para "esto ya pasó"."""
        return self.db.execute(
            "SELECT * FROM tickets WHERE status = 'cerrado' AND solution IS NOT NULL AND closed_at >= ? "
            "ORDER BY closed_at DESC LIMIT ?", (since, limit)).fetchall()

    def get_meta(self, key, default=None):
        row = self.db.execute("SELECT value FROM meta WHERE key = ?", (key,)).fetchone()
        return row["value"] if row else default

    def set_meta(self, key, value):
        self.db.execute("INSERT OR REPLACE INTO meta VALUES (?, ?)", (key, value))
        self.db.commit()

    def rows(self):
        return [dict(r) for r in self.db.execute(
            "SELECT t.*, r.processed_at, r.brain, r.category, r.module, r.severity, r.summary, r.needs_code, "
            "r.relation_kind, r.relation_ref, r.relation_confidence, r.relation_reason, r.diagnosis, r.action, "
            "r.error FROM tickets t LEFT JOIN results r ON r.ticket_id = t.id ORDER BY t.opened_at DESC")]
