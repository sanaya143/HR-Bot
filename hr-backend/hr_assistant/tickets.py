"""HR escalation tickets (SQLite). The React app creates them via /escalate and HR
staff work them via /hr/tickets. SQLite is a local file: on Cloud Run use a mounted
volume or move this class to Cloud SQL / Firestore."""
import json
import sqlite3
import threading
import time

STATUSES = ("open", "in_progress", "resolved")


def send_webhook(webhook_url: str, ticket_id: int, profile, question: str, reason: str, note: str) -> None:
    if not webhook_url:
        return
    import httpx
    payload = {
        "text": f"🚨 HR Ticket #{ticket_id}: {profile.name} ({profile.country})",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"🚨 New HR Ticket #{ticket_id}"}
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Employee:*\n{profile.name} ({profile.email})"},
                    {"type": "mrkdwn", "text": f"*Region / Dept:*\n{profile.country} / {getattr(profile, 'department', 'N/A')}"},
                    {"type": "mrkdwn", "text": f"*Trigger:*\n{reason}"},
                    {"type": "mrkdwn", "text": f"*Note:*\n{note or 'No extra note'}"}
                ]
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Question asked:*\n>{question}"}
            }
        ]
    }
    try:
        httpx.post(webhook_url, json=payload, timeout=4.0)
    except Exception:
        pass


class TicketStore:
    def __init__(self, path: str, webhook_url: str = ""):
        self.webhook_url = webhook_url
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._db.execute("""CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT, created_at REAL, employee_email TEXT,
                employee_name TEXT, country TEXT, question TEXT, reason TEXT, note TEXT,
                transcript TEXT, status TEXT DEFAULT 'open', assigned_to TEXT, updated_at REAL)""")
            self._db.commit()

    def create(self, profile, question: str, reason: str, note: str, transcript: list[dict]) -> int:
        now = time.time()
        with self._lock:
            cur = self._db.execute(
                "INSERT INTO tickets (created_at, employee_email, employee_name, country, question, reason, note, transcript, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?)",
                (now, profile.email, profile.name, profile.country, question, reason, note,
                 json.dumps(transcript), now))
            self._db.commit()
            tid = cur.lastrowid
        if self.webhook_url:
            threading.Thread(target=send_webhook, args=(self.webhook_url, tid, profile, question, reason, note), daemon=True).start()
        return tid

    @staticmethod
    def _row(r) -> dict:
        d = dict(r)
        d["transcript"] = json.loads(d["transcript"] or "[]")
        return d

    def list(self, status: str | None = None) -> list[dict]:
        with self._lock:
            q, args = "SELECT * FROM tickets", ()
            if status:
                q, args = q + " WHERE status = ?", (status,)
            rows = self._db.execute(q + " ORDER BY created_at DESC", args).fetchall()
        return [self._row(r) for r in rows]

    def get(self, ticket_id: int) -> dict | None:
        with self._lock:
            r = self._db.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()
        return self._row(r) if r else None

    def update(self, ticket_id: int, status: str | None, assigned_to: str | None) -> dict | None:
        if status is not None and status not in STATUSES:
            raise ValueError(f"status must be one of {STATUSES}")
        with self._lock:
            if status is not None:
                self._db.execute("UPDATE tickets SET status=?, updated_at=? WHERE id=?", (status, time.time(), ticket_id))
            if assigned_to is not None:
                self._db.execute("UPDATE tickets SET assigned_to=?, updated_at=? WHERE id=?", (assigned_to, time.time(), ticket_id))
            self._db.commit()
        return self.get(ticket_id)
