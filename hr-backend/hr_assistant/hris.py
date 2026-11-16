"""Employee profile lookup. JSON file for v1; implement the same get_profile()
against your real HRIS (Workday, Darwinbox, Keka, ...) later."""
import json

from .models import Profile


class JsonHRIS:
    def __init__(self, path: str):
        with open(path, encoding="utf-8") as f:
            self._data = {k.lower(): v for k, v in json.load(f).items()}

    def get_profile(self, email: str) -> Profile | None:
        d = self._data.get(email.lower())
        return Profile(email=email.lower(), **d) if d else None
