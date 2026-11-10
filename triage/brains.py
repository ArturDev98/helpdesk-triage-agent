"""Quién decide: Claude (por la API) u Offline (reglas y similitud, para demos y pruebas sin llave)."""
import json
import re

from triage.models import Diagnosis, Relation, Triage
from triage.prompts import render
from triage.similarity import tokens

CATEGORIES = ["incidente", "consulta", "operativo", "requerimiento"]
LEVELS = ["alta", "media", "baja"]


class BrainError(Exception):
    """El modelo no dio una respuesta usable (rechazo, corte por longitud, JSON inválido)."""


def _schema(properties):
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


TRIAGE_SCHEMA = _schema({
    "category": {"type": "string", "enum": CATEGORIES},
    "module": {"type": "string"},
    "severity": {"type": "string", "enum": LEVELS},
    "summary": {"type": "string"},
    "needs_code": {"type": "boolean"},
})
RELATION_SCHEMA = _schema({
    "kind": {"type": "string", "enum": ["known_issue", "closed_ticket", "none"]},
    "ref": {"anyOf": [{"type": "string"}, {"type": "null"}]},
    "confidence": {"type": "string", "enum": LEVELS},
    "reason": {"type": "string"},
})
DIAGNOSIS_SCHEMA = _schema({
    "hypothesis": {"type": "string"},
    "files": {"type": "array", "items": {"type": "string"}},
    "verify": {"type": "array", "items": {"type": "string"}},
    "needs_issue": {"type": "boolean"},
    "reply": {"type": "string"},
})


class ClaudeBrain:
    name = "claude"

    def __init__(self, profile_text, modules, model="claude-opus-5-5", client=None):
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        self.client = client
        self.model = model
        self.modules = list(modules)
        self.system = {step: render(step, profile_text) for step in ("triage", "relation", "diagnosis")}

    def triage(self, text):
        modules = f"Módulos válidos: {', '.join(self.modules)} u 'otro'.\n\n"
        return Triage(**self._ask("triage", modules + text, TRIAGE_SCHEMA, effort="low"))

    def relate(self, text, candidates):
        listing = "\n\n".join(f"[{c['kind']} {c['id']}] ({c['status']}) {c['title']}\n{c['text']}" for c in candidates)
        data = self._ask("relation", f"TICKET NUEVO\n{text}\n\nCANDIDATOS\n{listing}", RELATION_SCHEMA, effort="low")
        valid = {c["id"] for c in candidates}
        if data["kind"] != "none" and data["ref"] not in valid:
            data = {"kind": "none", "ref": None, "confidence": "baja", "reason": "El modelo citó un candidato inexistente."}
        return Relation(**data)

    def diagnose(self, text, triage, snippets):
        code = "\n\n".join(f"### {path}\n```\n{snippet}\n```" for path, _, snippet in snippets) or "(sin coincidencias)"
        prompt = f"INCIDENTE ({triage.module}, severidad {triage.severity})\n{text}\n\nCÓDIGO\n{code}"
        return Diagnosis(**self._ask("diagnosis", prompt, DIAGNOSIS_SCHEMA, effort="high"))

    def _ask(self, step, content, schema, effort):
        # El system va primero y no cambia entre tickets, así la caché del prompt se reutiliza.
        response = self.client.beta.messages.create(
            model=self.model,
            max_tokens=16000,
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
            cache_control={"type": "ephemeral"},
            system=self.system[step],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            messages=[{"role": "user", "content": content}],
        )
        if response.stop_reason == "refusal":
            raise BrainError(f"{step}: el modelo declinó la solicitud")
        if response.stop_reason == "max_tokens":
            raise BrainError(f"{step}: la respuesta se cortó por longitud")
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise BrainError(f"{step}: JSON inválido ({e})") from e


class OfflineBrain:
    """Reglas por palabras clave y umbrales de similitud. Determinista: sirve para la demo y las pruebas."""
    name = "offline"
    _HIGH_IMPACT = re.compile(r"\b(todos|ningun|ninguno|nadie|caid|no pueden|bloquead|urgente)", re.I)

    def __init__(self, modules, categories):
        self.modules = {name: set(tokens(" ".join(m.get("keywords", [])))) for name, m in modules.items()}
        self.categories = {name: [tokens(k) for k in words] for name, words in categories.items()}

    def triage(self, text):
        words = tokens(text)
        bag = set(words)
        module = max(self.modules, key=lambda m: len(self.modules[m] & bag), default="otro")
        if not self.modules or not self.modules[module] & bag:
            module = "otro"
        category = next((c for c, phrases in self.categories.items()
                         if any(self._contains(words, p) for p in phrases)), "incidente")
        if category == "operativo":
            module = "infraestructura"
        if category in ("consulta", "requerimiento"):
            severity = "baja"
        else:
            severity = "alta" if self._HIGH_IMPACT.search(_ascii(text)) else "media"
        summary = text.split("\n", 1)[0][:140]
        return Triage(category, module, severity, summary, category == "incidente" and module != "otro")

    def relate(self, text, candidates):
        if not candidates:
            return Relation("none", None, "baja", "Sin candidatos parecidos.")
        best = max(candidates, key=lambda c: c["score"])
        # Umbrales calibrados con la demo: por debajo de 0.4 solo comparten vocabulario del dominio.
        if best["score"] < 0.4:
            return Relation("none", None, "baja", f"El más parecido ({best['id']}) apenas comparte palabras.")
        confidence = "alta" if best["score"] >= 0.6 else "media"
        return Relation(best["kind"], best["id"], confidence,
                        f"Similitud {best['score']:.2f} con «{best['title']}».")

    def diagnose(self, text, triage, snippets):
        if not snippets:
            return Diagnosis("No hay código del módulo que coincida; revisar datos o configuración.", [],
                             ["Reproducir el caso con los datos del ticket."], False,
                             "Estamos revisando tu caso y te contamos en cuanto tengamos novedades.")
        files = [path for path, _, _ in snippets[:2]]
        return Diagnosis(
            f"Revisar la lógica de {triage.module} en {files[0]}: es el archivo con más coincidencias con el síntoma.",
            files,
            [f"Leer {files[0]} en las líneas resaltadas.", "Reproducir el caso en pruebas con los mismos datos.",
             "Consultar el pedido afectado en la base (solo lectura)."],
            True,
            "Gracias por reportarlo. Identificamos dónde puede estar la falla y el equipo técnico la está revisando.")

    @staticmethod
    def _contains(words, phrase):
        n = len(phrase)
        return n > 0 and any(words[i:i + n] == phrase for i in range(len(words) - n + 1))


def _ascii(text):
    import unicodedata
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()


def build_brain(config, profile_text):
    brain = config.get("brain", {})
    if brain.get("type", "offline") == "claude":
        return ClaudeBrain(profile_text, config.modules, model=brain.get("model", "claude-opus-5-5"))
    return OfflineBrain(config.modules, config.categories)
