"""Pinecone Documents API (Python SDK 10+, API version 2026-07).

The index has a schema: a dense vector field `embedding` and a full-text field `text`
(kept so keyword/BM25 search can be added later without rebuilding). Everything else
we upsert (source, country, policy_category, ...) is stored as filterable metadata."""
from .models import Chunk, PipelineError

FILTER_FIELDS = ["policy_category", "country", "employment_type", "role_level", "status"]
RETURN_FIELDS = ["text", "source", "title", "page", "effective_date", "version"] + FILTER_FIELDS


# ---- pure helpers (unit tested without Pinecone) ----
def build_filter(scope: dict[str, list[str]]) -> dict:
    """Every field must match (AND). A list-valued field matches if ANY of its values
    is in the allowed list, so a document tagged ["IN", "US"] is visible to both."""
    return {"$and": [{field: {"$in": list(vals)}} for field, vals in scope.items()]}


def to_document(c: Chunk, vector: list[float]) -> dict:
    doc = {**c.metadata, "_id": c.id, "embedding": vector,
           "text": c.text, "source": c.source, "title": c.title}
    if c.page is not None:
        doc["page"] = c.page
    return {k: v for k, v in doc.items() if v is not None}      # Pinecone rejects null


def field_value(match, name: str, default=None):
    """Read a field from a search match whether the SDK returns an object or a dict."""
    if isinstance(match, dict):
        return match.get(name, default)
    v = getattr(match, name, None)
    if v is not None:
        return v
    for container in ("fields", "metadata"):
        d = getattr(match, container, None)
        if isinstance(d, dict) and name in d:
            return d[name]
    return default


def chunk_from_match(m) -> Chunk:
    id_ = field_value(m, "_id") or field_value(m, "id") or ""
    score = field_value(m, "_score")
    if score is None:
        score = field_value(m, "score", 0.0)
    meta = {f: field_value(m, f) for f in FILTER_FIELDS + ["effective_date", "version"]}
    source = field_value(m, "source", "")
    page = field_value(m, "page")
    return Chunk(str(id_), field_value(m, "text", ""), source, field_value(m, "title", source),
                 int(page) if page is not None else None, meta, float(score))


def check_schema(info, dimension: int) -> None:
    """Fail early, with a clear message, if an existing index has the wrong shape
    (for example one created by hand in the Pinecone console)."""
    try:
        fields = info.schema.fields
    except Exception:      # noqa: BLE001 - can't introspect: let the first upsert tell us
        return
    emb = fields.get("embedding") if hasattr(fields, "get") else getattr(fields, "embedding", None)
    if emb is None:
        raise RuntimeError("The existing Pinecone index has no 'embedding' vector field. "
                           "Delete it (Pinecone console) or run: python ingest.py --force")
    dim = emb.get("dimension") if isinstance(emb, dict) else getattr(emb, "dimension", None)
    if dim and int(dim) != dimension:
        raise RuntimeError(f"The existing index uses dimension {dim} but the embedding model "
                           f"produces {dimension}. Run: python ingest.py --force")


def batches(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


class PineconeIndex:
    def __init__(self, settings, embedder):
        from pinecone import Pinecone
        self.s, self.embedder = settings, embedder
        self.pc = Pinecone(api_key=settings.pinecone_api_key)
        self.ns = settings.pinecone_namespace
        self._idx = None

    @property
    def idx(self):
        if self._idx is None:
            self._idx = self.pc.index(self.s.pinecone_index)
        return self._idx

    def _describe(self):
        """Index info, or None if the index does not exist."""
        try:
            return self.pc.indexes.describe(self.s.pinecone_index)
        except Exception as e:      # noqa: BLE001
            if "404" in str(e) or "not found" in str(e).lower():
                return None
            raise

    def create(self, recreate: bool = False) -> None:
        """Create the index if missing. With recreate=True, delete and rebuild it."""
        from pinecone import SchemaBuilder
        name = self.s.pinecone_index
        info = self._describe()
        if info is not None and recreate:
            self.pc.indexes.delete(name)
            self._idx, info = None, None
        if info is not None:
            check_schema(info, self.s.embedding_dim)
            return
        schema = (SchemaBuilder()
                  .add_dense_vector_field("embedding", dimension=self.s.embedding_dim, metric="cosine")
                  .add_string_field("text", full_text_search={"language": "en"})
                  .build())
        self.pc.indexes.create(          # blocks until the index is ready
            name=name, schema=schema,
            deployment={"deployment_type": "managed", "cloud": self.s.pinecone_cloud,
                        "region": self.s.pinecone_region})

    def upsert(self, chunks: list[Chunk]) -> None:
        vectors = self.embedder.embed_documents([c.text for c in chunks])
        docs = [to_document(c, v) for c, v in zip(chunks, vectors)]
        for batch in batches(docs, 100):
            self.idx.documents.upsert(namespace=self.ns, documents=batch)

    def search(self, query: str, query_vector: list[float], scope: dict[str, list[str]], k: int) -> list[Chunk]:
        from pinecone import DenseVectorQuery
        try:
            res = self.idx.documents.search(
                namespace=self.ns, top_k=k,
                score_by=[DenseVectorQuery(field="embedding", values=query_vector)],
                filter=build_filter(scope), include_fields=RETURN_FIELDS)
        except Exception as e:      # noqa: BLE001
            raise PipelineError(f"Vector search failed: {e}") from e
        return [chunk_from_match(m) for m in res.matches]
