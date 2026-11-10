import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlparse

from triage.brains import BrainError, ClaudeBrain
from triage.models import Triage
from triage.notify import WebhookNotifier
from triage.prompts import render
from triage.redact import redact
from triage.similarity import Index

PROFILE = (Path(__file__).resolve().parent.parent / "profiles" / "tienda.md").read_text(encoding="utf-8")


class RedactTest(unittest.TestCase):
    def test_personal_data(self):
        cases = {
            "correo a.b@x.co": "correo [correo]",
            "cel 310 555 0123": "cel [teléfono]",
            "+57 3005550199": "[teléfono]",
            "CC 1.098.765.432": "CC [documento]",
            "cédula: 1098765432": "cédula: [documento]",
            "tarjeta 4111 1111 1111 1111": "tarjeta [tarjeta]",
        }
        for raw, expected in cases.items():
            self.assertEqual(redact(raw), expected)

    def test_amounts_survive(self):
        self.assertEqual(redact("pagó 1.250.000 y 150.000"), "pagó 1.250.000 y 150.000")


class SimilarityTest(unittest.TestCase):
    def test_ranks_the_same_problem_first(self):
        index = Index([("a", "Pago PSE pendiente, el banco debitó"), ("b", "Cupón no descuenta"),
                       ("c", "El correo de recuperación no llega")])
        self.assertEqual(index.search("pagué por PSE y sigue pendiente")[0][0], "a")
        self.assertEqual(index.search("nada que ver con esto"), [])


class PromptsTest(unittest.TestCase):
    def test_every_prompt_renders_with_the_demo_profile(self):
        for step in ("triage", "relation", "diagnosis"):
            text = render(step, PROFILE)
            self.assertNotIn("{{", text)
            self.assertIn("Tienda Demo", text)

    def test_missing_section_is_reported(self):
        with self.assertRaisesRegex(ValueError, "# @REGLAS"):
            render("diagnosis", "# @NOMBRE\nx\n# @DOMINIO\ny")


class FakeClient:
    """Imita client.beta.messages.create y guarda lo que se le pidió."""

    def __init__(self, payload, stop_reason="end_turn"):
        self.calls = []
        self.payload, self.stop_reason = payload, stop_reason
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(stop_reason=self.stop_reason,
                               content=[SimpleNamespace(type="text", text=json.dumps(self.payload))])


class ClaudeBrainTest(unittest.TestCase):
    def test_request_uses_structured_output_and_fallbacks(self):
        client = FakeClient({"category": "incidente", "module": "envios", "severity": "media",
                             "summary": "Cobra envío en pedido gratis", "needs_code": True})
        brain = ClaudeBrain(PROFILE, ["envios"], client=client)
        self.assertEqual(brain.triage("texto").module, "envios")
        call = client.calls[0]
        self.assertEqual(call["model"], "claude-opus-5-5")
        self.assertEqual(call["fallbacks"], "default")
        self.assertEqual(call["output_config"]["format"]["type"], "json_schema")
        self.assertIn("Tienda Demo", call["system"])

    def test_refusal_becomes_brain_error(self):
        brain = ClaudeBrain(PROFILE, [], client=FakeClient({}, stop_reason="refusal"))
        with self.assertRaises(BrainError):
            brain.triage("texto")

    def test_invented_reference_is_discarded(self):
        client = FakeClient({"kind": "known_issue", "ref": "NO-EXISTE", "confidence": "alta", "reason": "x"})
        relation = ClaudeBrain(PROFILE, [], client=client).relate("t", [
            {"kind": "known_issue", "id": "TIENDA-1", "status": "Abierto", "title": "a", "text": "b"}])
        self.assertEqual(relation.kind, "none")

    def test_diagnosis_receives_the_code(self):
        client = FakeClient({"hypothesis": "h", "files": ["a.py"], "verify": ["v"], "needs_issue": True, "reply": "r"})
        triage = Triage("incidente", "envios", "media", "s", True)
        ClaudeBrain(PROFILE, [], client=client).diagnose("t", triage, [("tienda/envios.py", 3, "  7 if x > y:")])
        self.assertIn("tienda/envios.py", client.calls[0]["messages"][0]["content"])


class WebhookTest(unittest.TestCase):
    def test_google_chat_threads_by_ticket(self):
        received = []

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body = self.rfile.read(int(self.headers["Content-Length"]))
                received.append((self.path, json.loads(body)))
                self.send_response(200)
                self.end_headers()

            def log_message(self, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=server.handle_request, daemon=True).start()
        WebhookNotifier(f"http://127.0.0.1:{server.server_port}/hook?key=x", "google-chat").send("T-1", "hola")
        server.server_close()
        path, body = received[0]
        query = parse_qs(urlparse(path).query)
        self.assertEqual(query["threadKey"], ["T-1"])
        self.assertEqual(query["key"], ["x"])
        self.assertEqual(body, {"text": "hola"})


if __name__ == "__main__":
    unittest.main()
