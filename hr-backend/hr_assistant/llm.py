"""All model calls go through OpenRouter. Fallback models use OpenRouter's native
`models` routing, so a provider outage fails over without extra code here."""
import json
import re
import time

from .models import PipelineError


class OpenRouterLLM:
    URL = "https://openrouter.ai/api/v1/chat/completions"

    def __init__(self, settings):
        import httpx
        self.s = settings
        self._http = httpx.Client(timeout=60, headers={
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "X-Title": "HR Policy Assistant"})

    def chat(self, messages: list[dict], model: str | None = None,
             temperature: float = 0.0, max_tokens: int = 700) -> str:
        primary = model or self.s.llm_model
        models = [primary] + ([] if model else self.s.llm_fallback_models)
        body = {"models": models, "messages": messages, "temperature": temperature, "max_tokens": max_tokens}
        last = None
        for attempt in range(3):
            try:
                r = self._http.post(self.URL, json=body)
                if r.status_code >= 400:
                    last = f"HTTP {r.status_code}: {r.text[:300]}"
                    if r.status_code in (429, 500, 502, 503, 504):
                        time.sleep(1.0 * (attempt + 1))
                        continue
                    break      # bad key, no credit, unknown model: retrying cannot help
                data = r.json()
                if "choices" not in data:
                    last = f"OpenRouter returned no answer: {str(data.get('error', data))[:300]}"
                    time.sleep(1.0 * (attempt + 1))
                    continue
                return data["choices"][0]["message"]["content"] or ""
            except Exception as e:      # noqa: BLE001
                last = f"{type(e).__name__}: {e}"
                time.sleep(1.0 * (attempt + 1))
        raise PipelineError(f"LLM request failed ({last})")


def parse_answer_json(text: str) -> dict | None:
    """Pull the JSON object out of a model reply; None if malformed."""
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(d, dict):
        return None
    return {"answerable": bool(d.get("answerable", False)),
            "answer": str(d.get("answer", "")).strip(),
            "sources": [int(s) for s in d.get("sources", []) if str(s).isdigit()]}
