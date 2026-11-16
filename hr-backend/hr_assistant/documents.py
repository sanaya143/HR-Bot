"""Document parsing + metadata. Matches the header convention of the HR files:

    Policy Category: Leave
    Country: India             (optional, default ALL; comma separated allowed)
    Employment Type: full_time (optional, default ALL)
    Role Level: manager        (optional, default ALL)
    Status / Effective Date / Version / Title (optional)

Header lines are read from the top of the file, then removed from the text.
If there is no Policy Category header, the category comes from the file name.
A sidecar file `<name>.meta.json` overrides anything."""
import io
import re
import uuid
from pathlib import Path

from .models import Chunk, norm_country, norm_token, to_list
from .splitter import split_text

SUPPORTED = {".txt", ".md", ".pdf", ".docx", ".pptx"}
FIELDS = {"policy category": "policy_category", "title": "title", "country": "country",
          "employment type": "employment_type", "role level": "role_level",
          "status": "status", "effective date": "effective_date", "version": "version"}
HEADER_RE = re.compile(r"^\s*(" + "|".join(FIELDS) + r")\s*:\s*(.+?)\s*$", re.I)


def parse_header(text: str) -> tuple[dict, str]:
    lines = text.splitlines()
    meta: dict = {}
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            if meta:
                break
            continue
        m = HEADER_RE.match(lines[i])
        if not m:
            break
        meta[FIELDS[m.group(1).lower()]] = m.group(2)
        i += 1
    return meta, "\n".join(lines[i:]).strip()


def infer_folder_metadata(filepath: str) -> dict:
    """Infer country, role level, or employment type from parent directory paths."""
    parts = Path(filepath).parts[:-1]
    meta = {}
    for part in parts:
        p = part.strip().lower().replace("-", "_").replace(" ", "_")
        if p in ("in", "india"):
            meta["country"] = "IN"
        elif p in ("us", "usa", "united_states"):
            meta["country"] = "US"
        elif p in ("uk", "gb", "united_kingdom"):
            meta["country"] = "GB"
        elif p in ("global", "all"):
            meta["country"] = "ALL"
        elif p in ("contractor", "contractors"):
            meta["employment_type"] = "contractor"
        elif p in ("full_time", "fulltime"):
            meta["employment_type"] = "full_time"
        elif p in ("intern", "interns"):
            meta["employment_type"] = "intern"
        elif p in ("manager", "managers"):
            meta["role_level"] = "manager"
    return meta


def category_from_filename(filename: str) -> str:
    """leave_policy.txt -> Leave, work_from_home_policy.txt -> Work From Home."""
    stem = re.sub(r"[_\-\s]*policy$", "", Path(filename).stem, flags=re.I)
    return stem.replace("_", " ").replace("-", " ").strip().title() or "Uncategorized"


def normalize_metadata(raw: dict, filename: str) -> dict:
    folder_meta = infer_folder_metadata(filename)
    default_country = folder_meta.get("country", "ALL")
    default_emp_type = folder_meta.get("employment_type", "ALL")
    default_role_level = folder_meta.get("role_level", "ALL")

    return {
        "policy_category": (raw.get("policy_category") or category_from_filename(filename)).strip(),
        "title": raw.get("title") or Path(filename).stem.replace("_", " ").replace("-", " ").title(),
        "country": to_list(raw.get("country", default_country), norm_country),
        "employment_type": to_list(raw.get("employment_type", default_emp_type), norm_token),
        "role_level": to_list(raw.get("role_level", default_role_level), norm_token),
        "status": str(raw.get("status", "active")).strip().lower(),
        "effective_date": str(raw.get("effective_date", "")),
        "version": str(raw.get("version", "1")),
    }


def extract_pages(filename: str, data: bytes) -> list[dict]:
    """Return [{'page': int|None, 'text': str}]; page numbers only where the format has them."""
    ext = Path(filename).suffix.lower()
    if ext in (".txt", ".md"):
        return [{"page": None, "text": data.decode("utf-8", errors="replace")}]
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        return [{"page": i, "text": p.extract_text() or ""} for i, p in enumerate(reader.pages, 1)]
    if ext == ".docx":
        from docx import Document
        doc = Document(io.BytesIO(data))
        return [{"page": None, "text": "\n".join(p.text for p in doc.paragraphs)}]
    if ext == ".pptx":
        from pptx import Presentation
        prs = Presentation(io.BytesIO(data))
        pages = []
        for i, slide in enumerate(prs.slides, 1):
            texts = [s.text_frame.text for s in slide.shapes if s.has_text_frame]
            pages.append({"page": i, "text": "\n".join(texts)})
        return pages
    raise ValueError(f"Unsupported file type: {ext}")


def process_file(filename: str, data: bytes, sidecar: dict | None = None) -> dict:
    """Raw file -> processed record (parsed text + normalized labels)."""
    pages = extract_pages(filename, data)
    raw_meta: dict = {}
    if pages:
        raw_meta, pages[0]["text"] = parse_header(pages[0]["text"])
    raw_meta.update({k.lower(): v for k, v in (sidecar or {}).items()})
    return {"source": filename, "metadata": normalize_metadata(raw_meta, filename), "pages": pages}


def chunk_processed(record: dict, size: int = 500, overlap: int = 60) -> list[Chunk]:
    meta, source = record["metadata"], record["source"]
    chunks = []
    for page in record["pages"]:
        for text in split_text(page["text"], size, overlap):
            cid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source}|{page['page']}|{text}"))
            chunks.append(Chunk(cid, text, source, meta["title"], page["page"], meta))
    return chunks
