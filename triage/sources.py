"""De dónde salen los tickets y los issues conocidos.

Para conectar SysAid, Zendesk, Jira Service Management, GLPI o GitHub Issues basta con otra clase
que cumpla TicketSource / IssueSource; el pipeline no sabe nada del sistema de origen.
"""
import json
from typing import Protocol

from triage.models import KnownIssue, Ticket


class TicketSource(Protocol):
    def open_tickets(self) -> list[Ticket]: ...
    def ticket(self, ticket_id: str) -> Ticket | None: ...
    def closed_since(self, iso_date: str) -> list[Ticket]: ...


class IssueSource(Protocol):
    def issues(self) -> list[KnownIssue]: ...


def _ticket(raw):
    # Los campos del solicitante (nombre, correo, oficina) se descartan aquí a propósito.
    return Ticket(id=str(raw["id"]), title=raw["title"], description=raw.get("description", ""),
                  opened_at=raw["opened_at"], status=raw.get("status", "abierto"),
                  closed_at=raw.get("closed_at"), solution=raw.get("solution"),
                  attachments=raw.get("attachments", []))


class JsonTicketSource:
    def __init__(self, path):
        self.path = path

    def _all(self):
        return [_ticket(t) for t in json.loads(self.path.read_text(encoding="utf-8"))]

    def open_tickets(self):
        return [t for t in self._all() if t.status == "abierto"]

    def ticket(self, ticket_id):
        return next((t for t in self._all() if t.id == ticket_id), None)

    def closed_since(self, iso_date):
        return [t for t in self._all() if t.status == "cerrado" and (t.closed_at or "") >= iso_date]


class JsonIssueSource:
    def __init__(self, path):
        self.path = path

    def issues(self):
        return [KnownIssue(**raw) for raw in json.loads(self.path.read_text(encoding="utf-8"))]


def build_sources(config):
    source = config["source"]
    if source.get("type", "json") != "json":
        raise ValueError(f"Fuente no soportada: {source['type']}. Implementa TicketSource para conectarla.")
    return JsonTicketSource(config.resolve(source["tickets"])), JsonIssueSource(config.resolve(source["issues"]))
