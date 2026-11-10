"""Tipos que cruzan todo el pipeline. El solicitante nunca sale de la fuente."""
from dataclasses import asdict, dataclass, field


@dataclass
class Ticket:
    id: str
    title: str
    description: str
    opened_at: str
    status: str = "abierto"
    closed_at: str | None = None
    solution: str | None = None
    attachments: list[str] = field(default_factory=list)


@dataclass
class KnownIssue:
    """Un issue del tracker de desarrollo (Jira, GitHub, Mantis…) que ya explica un problema."""
    key: str
    title: str
    description: str
    status: str
    url: str = ""

    @property
    def open(self):
        return self.status.lower() not in {"cerrado", "resuelto", "closed", "resolved", "done"}


@dataclass
class Triage:
    category: str          # incidente | consulta | operativo | requerimiento
    module: str
    severity: str          # alta | media | baja
    summary: str
    needs_code: bool


@dataclass
class Relation:
    kind: str              # known_issue | closed_ticket | none
    ref: str | None
    confidence: str        # alta | media | baja
    reason: str


@dataclass
class Diagnosis:
    hypothesis: str
    files: list[str]
    verify: list[str]
    needs_issue: bool
    reply: str


@dataclass
class Result:
    ticket_id: str
    triage: Triage
    relation: Relation
    diagnosis: Diagnosis | None
    action: str
    brain: str

    def to_dict(self):
        return asdict(self)
