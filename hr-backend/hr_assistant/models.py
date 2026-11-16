from dataclasses import dataclass, field

_COUNTRY = {"india": "IN", "in": "IN", "united states": "US", "usa": "US", "us": "US",
            "united kingdom": "GB", "uk": "GB", "gb": "GB", "all": "ALL", "global": "ALL"}


def norm_country(v: str) -> str:
    v = v.strip()
    return _COUNTRY.get(v.lower(), v.upper())


def norm_token(v: str) -> str:
    v = v.strip().lower().replace("-", "_").replace(" ", "_")
    return "ALL" if v == "all" else v


def to_list(value, normalizer) -> list[str]:
    if isinstance(value, str):
        value = value.split(",")
    out = [normalizer(str(x)) for x in value if str(x).strip()]
    return out or ["ALL"]


@dataclass
class Profile:
    email: str
    name: str
    country: str
    employment_type: str
    role_level: str = "employee"
    department: str = ""
    is_hr: bool = False

    def __post_init__(self):
        self.country = norm_country(self.country)
        self.employment_type = norm_token(self.employment_type)
        self.role_level = norm_token(self.role_level)

    def scope_key(self) -> str:
        return f"{self.country}|{self.employment_type}|{self.role_level}"


@dataclass
class Chunk:
    id: str
    text: str
    source: str
    title: str
    page: int | None
    metadata: dict
    score: float = 0.0


@dataclass
class Citation:
    id: int
    source: str
    title: str
    page: int | None
    snippet: str
    url: str | None = None


@dataclass
class AskResult:
    conversation_id: str
    answer: str
    answered_from: str            # documents | cache | none | escalation | blocked
    citations: list[Citation] = field(default_factory=list)
    escalate: bool = False
    escalation_reason: str | None = None
    cached: bool = False


class PipelineError(Exception):
    """A dependency (LLM, vector DB, embeddings) failed."""
