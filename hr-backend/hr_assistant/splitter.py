"""Recursive character splitter: ~size chars per chunk with overlap."""


def _pieces(text: str, size: int, seps: list[str]) -> list[str]:
    if len(text) <= size:
        return [text]
    if not seps:
        return [text[i:i + size] for i in range(0, len(text), size)]
    out: list[str] = []
    for part in text.split(seps[0]):
        part = part.strip()
        if not part:
            continue
        out.extend(_pieces(part, size, seps[1:]) if len(part) > size else [part])
    return out


def split_text(text: str, size: int = 500, overlap: int = 60) -> list[str]:
    text = text.strip()
    if not text:
        return []
    chunks: list[str] = []
    cur = ""
    for piece in _pieces(text, size, ["\n\n", "\n", ". ", " "]):
        if cur and len(cur) + 1 + len(piece) > size:
            chunks.append(cur)
            tail = cur[-overlap:] if overlap else ""
            sp = tail.find(" ")
            tail = tail[sp + 1:] if sp != -1 else tail
            cur = f"{tail} {piece}".strip() if tail else piece
        else:
            cur = f"{cur}\n{piece}" if cur else piece
    if cur:
        chunks.append(cur)
    return chunks
