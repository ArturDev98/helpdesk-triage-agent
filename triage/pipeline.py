"""Un ciclo: memoria de cerrados -> triage -> relación con lo conocido -> diagnóstico en el código -> chat."""
from dataclasses import replace
from datetime import date, timedelta

from triage import codesearch
from triage.brains import BrainError
from triage.models import Result
from triage.notify import format_result
from triage.redact import redact
from triage.similarity import Index

NEXT_STEP = {
    "consulta": "Responder con la guía de uso del módulo",
    "operativo": "Asignar al equipo de infraestructura",
    "requerimiento": "Pasar al backlog de producto",
    "incidente": "Revisión manual en la mesa",
}


class Pipeline:
    def __init__(self, config, brain, tickets, issues, store, notifier, analyze=True, log=print):
        self.config, self.brain, self.tickets, self.issue_source = config, brain, tickets, issues
        self.store, self.notifier, self.analyze, self.log = store, notifier, analyze, log
        self.code_paths = [config.resolve(p) for p in config.get("project", {}).get("code_paths", [])]
        memory = config.get("memory", {})
        self.closed_days, self.max_closed = memory.get("closed_days", 90), memory.get("max_closed", 60)
        # Solo la demo fija "hoy": así sus tickets ficticios no salen de la ventana con el tiempo.
        self.today = date.fromisoformat(memory["today"]) if memory.get("today") else date.today()

    def run(self, only=None):
        self.sync_closed()
        self.issues = {i.key: i for i in self.issue_source.issues()}
        pending = [self.tickets.ticket(only)] if only else self.tickets.open_tickets()
        pending = [t for t in pending if t and (only or not self.store.processed(t.id))]
        self.log(f"[ciclo] {len(pending)} tickets por procesar")
        results = []
        for ticket in pending:
            try:
                results.append(self.process(ticket))
            except BrainError as e:
                self.store.save_error(ticket.id, self.brain.name, str(e))
                self.notifier.send(ticket.id, f"⚠️ {ticket.id}: no se pudo analizar ({e}). Queda para revisión manual.")
        return results

    def sync_closed(self):
        """Guarda los cerrados recientes con su solución: alimentan la detección de "esto ya pasó"."""
        since = self.store.get_meta("closed_sync") or (self.today - timedelta(days=self.closed_days)).isoformat()
        closed = self.tickets.closed_since(since)
        for t in closed:
            self.store.save_ticket(self._clean(t))
        self.store.set_meta("closed_sync", self.today.isoformat())
        if closed:
            self.log(f"[memoria] {len(closed)} tickets cerrados desde {since}")

    def process(self, ticket):
        clean = self._clean(ticket)
        self.store.save_ticket(clean)
        text = f"{clean.title}\n{clean.description}"
        triage = self.brain.triage(text)

        relation = self.brain.relate(text, self._candidates(clean.id, text))
        diagnosis, action = None, None
        if relation.kind == "known_issue" and relation.confidence == "alta":
            issue = self.issues.get(relation.ref)
            if issue and issue.open:
                action = f"Vincular al issue {issue.key} y avisar al usuario que ya está en desarrollo"
        elif relation.kind == "closed_ticket" and relation.confidence == "alta":
            previous = next((r for r in self.store.closed_memory("", 10_000) if r["id"] == relation.ref), None)
            if previous:
                action = f"Aplicar la solución del ticket {previous['id']}: {previous['solution']}"

        if action is None and triage.needs_code and self.analyze:
            keywords = self.config.modules.get(triage.module, {}).get("keywords", [])
            snippets = codesearch.candidates(self.code_paths, text, keywords)
            diagnosis = self.brain.diagnose(text, triage, snippets)
            action = "Crear issue de desarrollo con la hipótesis" if diagnosis.needs_issue \
                else "Resolver en la mesa con los pasos sugeridos"
        action = action or NEXT_STEP[triage.category]

        result = Result(clean.id, triage, relation, diagnosis, action, self.brain.name)
        self.store.save_result(result)
        urls = {k: i.url for k, i in self.issues.items() if i.url}
        self.notifier.send(clean.id, format_result(clean, result, urls))
        return result

    def _candidates(self, ticket_id, text, k=5):
        docs, info = [], {}
        for issue in self.issues.values():
            docs.append((issue.key, f"{issue.title}\n{issue.description}"))
            info[issue.key] = {"kind": "known_issue", "id": issue.key, "title": issue.title,
                               "status": issue.status, "text": issue.description}
        since = (self.today - timedelta(days=self.closed_days)).isoformat()
        for row in self.store.closed_memory(since, self.max_closed):
            if row["id"] == ticket_id:
                continue
            docs.append((row["id"], f"{row['title']}\n{row['description']}"))
            info[row["id"]] = {"kind": "closed_ticket", "id": row["id"], "title": row["title"], "status": "cerrado",
                               "text": f"{row['description']}\nSolución aplicada: {row['solution']}"}
        if not docs:
            return []
        return [{**info[doc_id], "score": round(score, 3)} for doc_id, score in Index(docs).search(text, k)]

    @staticmethod
    def _clean(ticket):
        return replace(ticket, title=redact(ticket.title), description=redact(ticket.description),
                       solution=redact(ticket.solution) if ticket.solution else None)
