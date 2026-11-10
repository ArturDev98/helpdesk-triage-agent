import json
import unittest
from pathlib import Path

from triage.brains import OfflineBrain
from triage.config import Config
from triage.pipeline import Pipeline
from triage.sources import build_sources
from triage.store import Store

ROOT = Path(__file__).resolve().parent.parent
PII = ["marta.diaz@correo.ejemplo", "310 555 0123", "1.098.765.432", "3005550199", "Felipe Mora", "jpena@"]


class ListNotifier:
    def __init__(self):
        self.sent = []

    def send(self, thread, text):
        self.sent.append((thread, text))


def run_demo(store=None, analyze=True):
    config = Config(ROOT / "config.toml")
    tickets, issues = build_sources(config)
    store = store or Store(":memory:")
    notifier = ListNotifier()
    pipeline = Pipeline(config, OfflineBrain(config.modules, config.categories), tickets, issues, store, notifier,
                        analyze=analyze, log=lambda *_: None)
    return {r.ticket_id: r for r in pipeline.run()}, store, notifier, pipeline


class PipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.results, cls.store, cls.notifier, cls.pipeline = run_demo()

    def test_known_issue_skips_code_analysis(self):
        r = self.results["T-1011"]
        self.assertEqual((r.relation.kind, r.relation.ref, r.relation.confidence), ("known_issue", "TIENDA-101", "alta"))
        self.assertIsNone(r.diagnosis)
        self.assertIn("TIENDA-101", r.action)

    def test_closed_ticket_reuses_its_solution(self):
        self.assertIn("T-1002", self.results["T-1012"].action)
        self.assertIn("spam", self.results["T-1018"].action)

    def test_incident_gets_diagnosis_pointing_to_the_module_code(self):
        d = self.results["T-1010"].diagnosis
        self.assertEqual(d.files[0], "tienda/envios.py")
        self.assertEqual(self.results["T-1016"].diagnosis.files[0], "tienda/inventario.py")

    def test_non_incidents_are_routed_without_code(self):
        expected = {"T-1013": "consulta", "T-1014": "requerimiento", "T-1015": "operativo"}
        for ticket, category in expected.items():
            self.assertEqual(self.results[ticket].triage.category, category, ticket)
            self.assertIsNone(self.results[ticket].diagnosis)

    def test_personal_data_never_leaves_the_source(self):
        stored = json.dumps(self.store.rows(), ensure_ascii=False)
        sent = "\n".join(text for _, text in self.notifier.sent)
        for value in PII:
            self.assertNotIn(value, stored)
            self.assertNotIn(value, sent)

    def test_second_cycle_does_not_repeat_tickets(self):
        self.assertEqual(self.pipeline.run(), [])

    def test_without_analysis_there_is_no_diagnosis(self):
        results, *_ = run_demo(analyze=False)
        self.assertTrue(all(r.diagnosis is None for r in results.values()))


if __name__ == "__main__":
    unittest.main()
