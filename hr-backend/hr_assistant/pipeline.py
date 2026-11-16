"""One question -> one answer. Order:
input guard -> sensitive check -> rewrite follow-up using memory -> embed -> cache ->
filtered hybrid search -> rerank + score floor -> grounded generation -> citation check ->
output guard -> cache + memory."""
import json
import logging

from .guardrails import build_scope, needs_human
from .llm import parse_answer_json
from .memory import new_conversation_id
from .models import AskResult, Chunk, Citation, Profile
from .prompts import BLOCKED, CONDENSE_PROMPT, NOT_FOUND, SENSITIVE_REPLY, SYSTEM_PROMPT

audit = logging.getLogger("hr.audit")


def log_event(event: str, **fields) -> None:
    audit.info(json.dumps({"event": event, **fields}, default=str))


class Pipeline:
    def __init__(self, settings, embedder, reranker, index, llm, guard, cache, memory, url_for=None):
        self.s, self.embedder, self.reranker, self.index = settings, embedder, reranker, index
        self.llm, self.guard, self.cache, self.memory = llm, guard, cache, memory
        self.url_for = url_for or (lambda source, page: None)

    def _condense(self, question: str, history) -> str:
        """Turn a follow-up ("and for sick leave?") into a standalone question."""
        if not history:
            return question
        turns = history[-self.s.memory_prompt_turns:]
        convo = "\n".join(f"Employee: {t.question}\nAssistant: {t.answer}" for t in turns)
        try:
            out = self.llm.chat(
                [{"role": "system", "content": CONDENSE_PROMPT},
                 {"role": "user", "content": f"{convo}\n\nLatest message: {question}"}],
                model=self.s.llm_fast_model, max_tokens=120).strip().strip('"')
            return out if 3 <= len(out) <= 500 else question
        except Exception:      # noqa: BLE001 - rewriting is best-effort
            return question

    def _generate(self, standalone: str, profile: Profile, chunks: list[Chunk], history) -> dict | None:
        excerpts = "\n\n".join(
            f"[{i}] ({c.title}{f', page {c.page}' if c.page else ''})\n{c.text}" for i, c in enumerate(chunks, 1))
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for t in history[-self.s.memory_prompt_turns:]:
            messages += [{"role": "user", "content": t.question}, {"role": "assistant", "content": t.answer}]
        messages.append({"role": "user", "content": (
            f"Employee: {profile.country}, {profile.employment_type.replace('_', ' ')}\n\n"
            f"EXCERPTS:\n{excerpts}\n\nQUESTION: {standalone}")})
        for _ in range(2):      # one retry if the model returns malformed JSON
            parsed = parse_answer_json(self.llm.chat(messages, max_tokens=700))
            if parsed:
                return parsed
            messages.append({"role": "user", "content": "Reply with the JSON object only."})
        return None

    def _finish(self, profile, cid, question, result: AskResult, remember: bool = True) -> AskResult:
        if remember:
            self.memory.append(profile.email, cid, question, result.answer)
        log_event("ask", user=profile.email, country=profile.country, conversation=cid,
                  answered_from=result.answered_from, cited=[c.source for c in result.citations],
                  escalate=result.escalate)
        return result

    def ask(self, profile: Profile, question: str, conversation_id: str | None = None) -> AskResult:
        cid = conversation_id or new_conversation_id()
        history = self.memory.get(profile.email, cid)

        verdict = self.guard.check_input(question, [t.question for t in history])
        if not verdict.allowed:
            log_event("blocked", user=profile.email, reason=verdict.reason)
            return AskResult(cid, BLOCKED, "blocked")

        reason = needs_human(question)
        if reason:
            return self._finish(profile, cid, question, AskResult(
                cid, SENSITIVE_REPLY, "escalation", escalate=True, escalation_reason=reason))

        standalone = self._condense(question, history)
        vector = self.embedder.embed_query(standalone)
        scope = build_scope(profile, self.s.hr_policy_categories)

        hit = self.cache.get(profile.scope_key(), vector)
        if hit:
            return self._finish(profile, cid, question, AskResult(
                cid, hit["answer"], "cache", citations=list(hit["citations"]), cached=True))

        candidates = self.index.search(standalone, vector, scope, self.s.rerank_candidate_k)
        ranked = self.reranker.rerank(standalone, candidates, self.s.top_k)
        chunks = [c for c in ranked if c.score >= self.s.min_rerank_score]
        if not chunks:
            return self._finish(profile, cid, question, AskResult(
                cid, NOT_FOUND, "none", escalate=True, escalation_reason="No relevant policy found"))

        parsed = self._generate(standalone, profile, chunks, history)
        used = [i for i in dict.fromkeys(parsed["sources"] if parsed else []) if 1 <= i <= len(chunks)]
        if not parsed or not parsed["answerable"] or not parsed["answer"] or not used:
            return self._finish(profile, cid, question, AskResult(
                cid, NOT_FOUND, "none", escalate=True, escalation_reason="Answer not found in documents"))

        out_verdict = self.guard.check_output(parsed["answer"])
        if not out_verdict.allowed:
            log_event("output_blocked", user=profile.email, reason=out_verdict.reason)
            return self._finish(profile, cid, question, AskResult(cid, BLOCKED, "blocked"), remember=False)

        citations = [Citation(i, chunks[i - 1].source, chunks[i - 1].title, chunks[i - 1].page,
                              chunks[i - 1].text[:220], self.url_for(chunks[i - 1].source, chunks[i - 1].page))
                     for i in used]
        self.cache.put(profile.scope_key(), vector, {"answer": parsed["answer"], "citations": citations})
        return self._finish(profile, cid, question, AskResult(cid, parsed["answer"], "documents", citations))
