import os
from dataclasses import dataclass, field

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # dotenv is optional
    pass


def _list(name: str, default: str = "") -> list[str]:
    return [x.strip() for x in os.getenv(name, default).split(",") if x.strip()]


@dataclass
class Settings:
    # LLM via OpenRouter
    openrouter_api_key: str = ""
    llm_model: str = "google/gemini-2.5-flash"
    llm_fallback_models: list[str] = field(default_factory=lambda: ["openai/gpt-4o-mini"])
    llm_fast_model: str = "openai/gpt-4o-mini"
    # local Hugging Face models (fastembed)
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    reranker_model: str = "BAAI/bge-reranker-base"
    # Pinecone
    pinecone_api_key: str = ""
    pinecone_index: str = "hr-policies"
    pinecone_namespace: str = "hr"
    pinecone_cloud: str = "aws"
    pinecone_region: str = "us-east-1"
    hr_policy_categories: list[str] = field(default_factory=list)
    # retrieval
    rerank_candidate_k: int = 12
    top_k: int = 5
    min_rerank_score: float = 0.3
    chunk_size: int = 500
    chunk_overlap: int = 60
    # cache + memory
    cache_threshold: float = 0.93
    cache_ttl_seconds: int = 3600
    cache_max_entries: int = 500
    memory_max_turns: int = 10        # turns kept per conversation
    memory_prompt_turns: int = 6      # turns sent to the LLM
    conversation_ttl_seconds: int = 8 * 3600
    max_conversations: int = 5000
    # guardrails
    guardrail_provider: str = "heuristic"   # heuristic | llm | none
    guardrail_history_turns: int = 3
    guardrail_fail_open_input: bool = False
    guardrail_fail_open_output: bool = True
    auto_escalate_sensitive: bool = False
    # documents
    data_dir: str = "data"
    local_storage_dir: str = "storage"
    # auth / app
    auth_mode: str = "dev"                  # dev | google
    hris_file: str = "employees.json"
    tickets_db: str = "tickets.db"
    escalation_webhook_url: str = ""
    allowed_origins: list[str] = field(default_factory=lambda: ["http://localhost:5173"])
    rate_limit_per_minute: int = 20


def load_settings() -> Settings:
    e = os.getenv
    d = Settings()
    return Settings(
        openrouter_api_key=e("OPENROUTER_API_KEY", ""),
        llm_model=e("LLM_MODEL", d.llm_model),
        llm_fallback_models=_list("LLM_FALLBACK_MODELS", ",".join(d.llm_fallback_models)),
        llm_fast_model=e("LLM_FAST_MODEL", d.llm_fast_model),
        embedding_model=e("EMBEDDING_MODEL", d.embedding_model),
        embedding_dim=int(e("EMBEDDING_DIM", d.embedding_dim)),
        reranker_model=e("RERANKER_MODEL", d.reranker_model),
        pinecone_api_key=e("PINECONE_API_KEY", ""),
        pinecone_index=e("PINECONE_INDEX", d.pinecone_index),
        pinecone_namespace=e("PINECONE_NAMESPACE", d.pinecone_namespace),
        pinecone_cloud=e("PINECONE_CLOUD", d.pinecone_cloud),
        pinecone_region=e("PINECONE_REGION", d.pinecone_region),
        hr_policy_categories=_list("HR_POLICY_CATEGORIES"),
        min_rerank_score=float(e("MIN_RERANK_SCORE", d.min_rerank_score)),
        guardrail_provider=e("GUARDRAIL_PROVIDER", d.guardrail_provider),
        auto_escalate_sensitive=e("AUTO_ESCALATE_SENSITIVE", "false").lower() == "true",
        data_dir=e("DATA_DIR", d.data_dir),
        local_storage_dir=e("LOCAL_STORAGE_DIR", d.local_storage_dir),
        auth_mode=e("AUTH_MODE", d.auth_mode),
        hris_file=e("HRIS_FILE", d.hris_file),
        tickets_db=e("TICKETS_DB", d.tickets_db),
        escalation_webhook_url=e("ESCALATION_WEBHOOK_URL", d.escalation_webhook_url),
        allowed_origins=_list("ALLOWED_ORIGINS", ",".join(d.allowed_origins)),
        rate_limit_per_minute=int(e("RATE_LIMIT_PER_MINUTE", d.rate_limit_per_minute)),
    )
