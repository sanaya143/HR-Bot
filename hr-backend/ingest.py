"""Ingestion: data/ -> raw zone -> parse -> processed zone -> chunk -> embed (local HF model) -> Pinecone.
Safe to re-run: chunk ids are stable, so unchanged text is overwritten, not duplicated.
Use --force to delete and rebuild the index (needed after removing documents or
changing the embedding model).

    python ingest.py --dry-run        # parse + show metadata, touches no cloud service
    python ingest.py                  # create the index if missing, upsert everything
    python ingest.py --force          # delete the index and rebuild
"""
import argparse
import json
from collections import Counter
from pathlib import Path

from hr_assistant.config import load_settings
from hr_assistant.documents import SUPPORTED, chunk_processed, process_file
from hr_assistant.storage import make_storage


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--data-dir")
    a = ap.parse_args()
    s = load_settings()
    data_dir = Path(a.data_dir or s.data_dir)
    storage = None if a.dry_run else make_storage(s)

    records = []
    for f in sorted(data_dir.rglob("*")):
        if not f.is_file() or f.suffix.lower() not in SUPPORTED:
            continue
        rel_path = f.relative_to(data_dir).as_posix()
        raw = f.read_bytes()
        side = Path(str(f) + ".meta.json")
        sidecar = json.loads(side.read_text()) if side.exists() else None
        rec = process_file(rel_path, raw, sidecar)
        records.append(rec)
        m = rec["metadata"]
        print(f"{rel_path:35} category={m['policy_category']!r} country={m['country']} "
              f"type={m['employment_type']} level={m['role_level']} status={m['status']}")
        if storage:
            storage.write("raw", rel_path, raw)
            storage.write("processed", rel_path + ".json", json.dumps(rec).encode())

    cats = Counter(r["metadata"]["policy_category"] for r in records)
    print("\nCategories found (use for HR_POLICY_CATEGORIES if needed):", dict(cats))
    if a.dry_run:
        return

    from hr_assistant.embeddings import LocalEmbedder
    from hr_assistant.vector_store import PineconeIndex
    index = PineconeIndex(s, LocalEmbedder(s.embedding_model))
    chunks = []
    for name in storage.list("processed"):      # chunk + embed read the PROCESSED zone only
        chunks += chunk_processed(json.loads(storage.read("processed", name)), s.chunk_size, s.chunk_overlap)
    index.create(recreate=a.force)
    print(f"Uploading {len(chunks)} chunks (embedding locally, this can take a minute)...")
    index.upsert(chunks)
    print(f"Indexed {len(chunks)} chunks from {len(records)} documents into Pinecone index '{s.pinecone_index}'.")


if __name__ == "__main__":
    main()
