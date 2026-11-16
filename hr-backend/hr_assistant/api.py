import logging
import time
from collections import defaultdict, deque

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .auth import AuthError, resolve_email
from .config import Settings, load_settings
from .hris import JsonHRIS
from .models import PipelineError, Profile
from .pipeline import log_event
from .tickets import STATUSES, TicketStore

from fastapi.responses import FileResponse
from pathlib import Path


log = logging.getLogger("hr.api")


class AskRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)
    conversation_id: str | None = Field(default=None, max_length=64)


class EscalateRequest(BaseModel):
    conversation_id: str | None = Field(default=None, max_length=64)
    question: str = Field(default="", max_length=1000)
    note: str = Field(default="", max_length=2000)


class FeedbackRequest(BaseModel):
    conversation_id: str
    helpful: bool
    comment: str = Field(default="", max_length=1000)


class TicketUpdate(BaseModel):
    status: str | None = None
    assigned_to: str | None = None


def create_app(settings: Settings | None = None, pipeline=None, hris=None, tickets=None) -> FastAPI:
    logging.basicConfig(level=logging.INFO)
    s = settings or load_settings()
    if pipeline is None:
        from .factory import build_pipeline
        pipeline = build_pipeline(s)
    hris = hris or JsonHRIS(s.hris_file)
    tickets = tickets or TicketStore(s.tickets_db, s.escalation_webhook_url)

    app = FastAPI(title="HR Policy Assistant")
    app.add_middleware(CORSMiddleware, allow_origins=s.allowed_origins,
                       allow_methods=["*"], allow_headers=["*"])

    def profile_dep(authorization: str | None = Header(default=None),
                    x_dev_user: str | None = Header(default=None)) -> Profile:
        try:
            email = resolve_email(s, authorization, x_dev_user)
        except AuthError as e:
            raise HTTPException(401, str(e))
        profile = hris.get_profile(email)
        if not profile:      # the HRIS record doubles as the employee allow-list
            raise HTTPException(403, "No employee record for this account")
        return profile

    def hr_dep(profile: Profile = Depends(profile_dep)) -> Profile:
        if not profile.is_hr:
            raise HTTPException(403, "HR access only")
        return profile

    hits: dict[str, deque] = defaultdict(deque)

    def rate_limit(profile: Profile = Depends(profile_dep)) -> Profile:
        now, q = time.time(), hits[profile.email]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= s.rate_limit_per_minute:
            raise HTTPException(429, "Too many questions. Please wait a minute.")
        q.append(now)
        return profile

    def transcript(profile: Profile, cid: str | None) -> list[dict]:
        if not cid:
            return []
        return [{"question": t.question, "answer": t.answer} for t in pipeline.memory.get(profile.email, cid)]

    def open_ticket(profile, cid, question, reason, note) -> int:
        convo = transcript(profile, cid)
        question = question or (convo[-1]["question"] if convo else "")
        return tickets.create(profile, question, reason, note, convo)

    @app.get("/health")
    def health():
        return {"status": "ok"}

    @app.get("/me")
    def me(profile: Profile = Depends(profile_dep)):
        return {"email": profile.email, "name": profile.name, "country": profile.country,
                "employment_type": profile.employment_type, "role_level": profile.role_level,
                "department": profile.department, "is_hr": profile.is_hr}

    @app.post("/ask")
    def ask(req: AskRequest, profile: Profile = Depends(rate_limit)):
        try:
            r = pipeline.ask(profile, req.question.strip(), req.conversation_id)
        except PipelineError as e:
            log.error("pipeline failure: %s", e)
            # dev mode shows the real cause; production shows a generic message
            detail = (f"Dependency failed: {e}" if s.auth_mode == "dev"
                      else "The assistant is temporarily unavailable. Please try again.")
            raise HTTPException(503, detail)
        ticket_id = None
        if r.answered_from == "escalation" and s.auto_escalate_sensitive:
            ticket_id = open_ticket(profile, r.conversation_id, req.question, r.escalation_reason or "", "")
        return {
            "conversation_id": r.conversation_id, "answer": r.answer, "answered_from": r.answered_from,
            "cached": r.cached, "escalate": r.escalate, "escalation_reason": r.escalation_reason,
            "ticket_id": ticket_id, "citations": [c.__dict__ for c in r.citations]}

    @app.get("/conversations/{cid}")
    def history(cid: str, profile: Profile = Depends(profile_dep)):
        return {"conversation_id": cid, "turns": transcript(profile, cid)}

    @app.delete("/conversations/{cid}")
    def clear(cid: str, profile: Profile = Depends(profile_dep)):
        pipeline.memory.clear(profile.email, cid)
        return {"status": "cleared"}

    @app.post("/escalate")
    def escalate(req: EscalateRequest, profile: Profile = Depends(rate_limit)):
        tid = open_ticket(profile, req.conversation_id, req.question, "Employee asked for HR", req.note)
        return {"ticket_id": tid, "status": "open"}

    @app.post("/feedback")
    def feedback(req: FeedbackRequest, profile: Profile = Depends(profile_dep)):
        log_event("feedback", user=profile.email, conversation=req.conversation_id,
                  helpful=req.helpful, comment=req.comment)
        return {"status": "recorded"}

    @app.get("/hr/tickets")
    def list_tickets(status: str | None = None, _: Profile = Depends(hr_dep)):
        if status and status not in STATUSES:
            raise HTTPException(400, f"status must be one of {STATUSES}")
        return {"tickets": tickets.list(status)}




    @app.get("/documents/{filename:path}")
    def serve_document(filename: str, profile: Profile = Depends(profile_dep)):
        raw_base = (Path(s.local_storage_dir) / "raw").resolve()
        data_base = Path(s.data_dir).resolve()

        target = (raw_base / filename).resolve()
        if not target.exists() or not target.is_file():
            target = (data_base / filename).resolve()

        if not target.exists() or not target.is_file():
            raise HTTPException(404, "Document not found")

        # Security: Prevent directory traversal
        if not (target.is_relative_to(raw_base) or target.is_relative_to(data_base)):
            raise HTTPException(403, "Access denied")

        return FileResponse(target)
    

    @app.get("/hr/tickets/{ticket_id}")
    def get_ticket(ticket_id: int, _: Profile = Depends(hr_dep)):
        t = tickets.get(ticket_id)
        if not t:
            raise HTTPException(404, "Ticket not found")
        return t

    @app.patch("/hr/tickets/{ticket_id}")
    def update_ticket(ticket_id: int, body: TicketUpdate, _: Profile = Depends(hr_dep)):
        if not tickets.get(ticket_id):
            raise HTTPException(404, "Ticket not found")
        try:
            return tickets.update(ticket_id, body.status, body.assigned_to)
        except ValueError as e:
            raise HTTPException(400, str(e))

    return app
