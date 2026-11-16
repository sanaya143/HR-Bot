import re
from dataclasses import dataclass

from .models import Profile
from .prompts import CLASSIFIER_PROMPT

# Sensitive topics go to a human, not the model.
SENSITIVE = re.compile(
    r"\b(harass\w*|discriminat\w*|assault\w*|abus\w*|bully\w*|retaliat\w*|whistle\w*|"
    r"terminat\w*|fired|layoff\w*|grievance\w*|complaint\w*|pregnan\w*|disabilit\w*|"
    r"mental health|suicid\w*|legal action|lawsuit\w*|salary dispute|unfair treatment)\b", re.I)


def needs_human(question: str) -> str | None:
    m = SENSITIVE.search(question)
    return f"Sensitive topic ({m.group(0).lower()})" if m else None


INJECTION = re.compile(
    r"(ignore|disregard|forget)\s+(all\s+|any\s+|your\s+|the\s+)?(previous\s+|prior\s+|above\s+|earlier\s+|system\s+)?(instructions|rules|prompt)|"
    r"(reveal|show|print|repeat|leak)\s+(me\s+)?(your\s+|the\s+)?(system\s+)?(prompt|instructions)|"
    r"\bdeveloper mode\b|\bjailbreak\w*|(?-i:\bDAN\b)|do anything now|"
    r"\byou are now (a|an|the|called|named)\b|pretend (to be|you are)", re.I)


@dataclass
class Verdict:
    allowed: bool
    reason: str = ""
    error: bool = False


class Guard:
    def __init__(self, settings, llm=None):
        self.s = settings
        self.llm = llm

    def _classify(self, text: str) -> bool:
        """True if SAFE. Raises on provider failure."""
        out = self.llm.chat([{"role": "system", "content": CLASSIFIER_PROMPT},
                             {"role": "user", "content": text[:4000]}],
                            model=self.s.llm_fast_model, max_tokens=5)
        return not out.strip().upper().startswith("UNSAFE")

    def check_input(self, question: str, history: list[str] | None = None) -> Verdict:
        p = self.s.guardrail_provider
        if p == "none":
            return Verdict(True)
        # screen the current turn plus recent turns so slow multi-turn attacks are seen
        recent = (history or [])[-self.s.guardrail_history_turns:]
        combined = "\n".join(recent + [question])
        try:
            if INJECTION.search(combined):
                return Verdict(False, "prompt injection pattern")
            if p == "llm" and not self._classify(combined):
                return Verdict(False, "flagged unsafe")
            return Verdict(True)
        except Exception as e:      # noqa: BLE001
            # provider failed: input fails CLOSED unless explicitly overridden
            return Verdict(self.s.guardrail_fail_open_input, f"guardrail error: {e}", error=True)

    def check_output(self, answer: str) -> Verdict:
        p = self.s.guardrail_provider
        if p == "none":
            return Verdict(True)
        try:
            if "EXCERPTS" in answer or '"answerable"' in answer or "identity is fixed" in answer:
                return Verdict(False, "possible prompt leak")
            if p == "llm" and not self._classify(answer):
                return Verdict(False, "flagged unsafe")
            return Verdict(True)
        except Exception as e:      # noqa: BLE001
            # output check fails OPEN: don't discard a valid answer over a screening error
            return Verdict(self.s.guardrail_fail_open_output, f"guardrail error: {e}", error=True)


def build_scope(profile: Profile, categories: list[str]) -> dict[str, list[str]]:
    """Hard retrieval filter, built only from the verified profile, never from user text.
    Documents tagged ALL apply to everybody."""
    scope = {
        "country": [profile.country, "ALL"],
        "employment_type": [profile.employment_type, "ALL"],
        "role_level": [profile.role_level, "ALL"],
        "status": ["active"],
    }
    if categories:
        scope["policy_category"] = list(categories)
    return scope
