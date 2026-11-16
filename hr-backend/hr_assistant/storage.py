"""raw/ (originals) and processed/ (parsed JSON) zones.
Local disk for now; an Azure Blob implementation with the same four methods
(write, read, list, signed_url) can replace it later without touching anything else."""
from pathlib import Path


class LocalStorage:
    def __init__(self, root: str):
        self.root = Path(root)

    def write(self, zone: str, name: str, data: bytes) -> None:
        p = self.root / zone / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def read(self, zone: str, name: str) -> bytes:
        return (self.root / zone / name).read_bytes()

    def list(self, zone: str) -> list[str]:
        d = self.root / zone
        if not d.exists():
            return []
        return sorted(p.relative_to(d).as_posix() for p in d.rglob("*") if p.is_file())

    def signed_url(self, zone: str, name: str, page: int | None = None) -> str | None:
        url = f"/api/documents/{name}"
        return f"{url}#page={page}" if page else url


def make_storage(settings):
    return LocalStorage(settings.local_storage_dir)
