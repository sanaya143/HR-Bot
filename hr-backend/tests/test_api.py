"""Needs: pip install fastapi httpx. Skipped automatically if missing."""
import unittest

try:
    from fastapi.testclient import TestClient
    HAVE = True
except Exception:      # noqa: BLE001
    HAVE = False

from hr_assistant.config import Settings
from tests.fakes import build


@unittest.skipUnless(HAVE, "fastapi/httpx not installed")
class ApiTests(unittest.TestCase):
    def setUp(self):
        from hr_assistant.api import create_app
        from hr_assistant.hris import JsonHRIS
        from hr_assistant.tickets import TicketStore
        self.pipe, self.llm, _ = build()
        self.app = create_app(Settings(rate_limit_per_minute=100), self.pipe,
                              JsonHRIS("employees.json"), TicketStore(":memory:"))
        self.c = TestClient(self.app)

    def h(self, user):
        return {"X-Dev-User": user}

    def test_auth(self):
        self.assertEqual(self.c.get("/me").status_code, 401)
        self.assertEqual(self.c.get("/me", headers=self.h("stranger@evil.com")).status_code, 403)
        me = self.c.get("/me", headers=self.h("priya@acme.com")).json()
        self.assertEqual(me["country"], "IN")

    def test_ask_with_memory_and_escalation_flow(self):
        r = self.c.post("/ask", json={"question": "How many casual leave days do I get per year?"},
                        headers=self.h("priya@acme.com")).json()
        self.assertEqual(r["answered_from"], "documents")
        cid = r["conversation_id"]
        hist = self.c.get(f"/conversations/{cid}", headers=self.h("priya@acme.com")).json()
        self.assertEqual(len(hist["turns"]), 1)
        t = self.c.post("/escalate", json={"conversation_id": cid, "note": "please call me"},
                        headers=self.h("priya@acme.com")).json()
        self.assertEqual(t["status"], "open")

    def test_hr_endpoints_are_hr_only(self):
        self.c.post("/escalate", json={"question": "help", "note": "n"}, headers=self.h("priya@acme.com"))
        self.assertEqual(self.c.get("/hr/tickets", headers=self.h("priya@acme.com")).status_code, 403)
        tickets = self.c.get("/hr/tickets", headers=self.h("hr@acme.com")).json()["tickets"]
        self.assertEqual(len(tickets), 1)
        upd = self.c.patch(f"/hr/tickets/{tickets[0]['id']}", json={"status": "resolved"},
                           headers=self.h("hr@acme.com"))
        self.assertEqual(upd.json()["status"], "resolved")
        bad = self.c.patch(f"/hr/tickets/{tickets[0]['id']}", json={"status": "nope"}, headers=self.h("hr@acme.com"))
        self.assertEqual(bad.status_code, 400)

    def test_rate_limit(self):
        from hr_assistant.api import create_app
        from hr_assistant.hris import JsonHRIS
        from hr_assistant.tickets import TicketStore
        c = TestClient(create_app(Settings(rate_limit_per_minute=2), self.pipe,
                                  JsonHRIS("employees.json"), TicketStore(":memory:")))
        codes = [c.post("/ask", json={"question": "How many casual leave days?"},
                        headers=self.h("priya@acme.com")).status_code for _ in range(3)]
        self.assertEqual(codes, [200, 200, 429])


if __name__ == "__main__":
    unittest.main()
