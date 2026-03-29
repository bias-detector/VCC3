import json
import re
from typing import Tuple

import requests

from .config import settings

TOXIC_KEYWORDS = {
    "idiot",
    "stupid",
    "hate",
    "kill",
    "trash",
    "shut up",
    "moron",
    "dumb",
}


class LocalLLMClassifier:
    def __init__(self) -> None:
        self.endpoint = f"{settings.ollama_url}/api/generate"

    def classify(self, text: str) -> Tuple[bool, float, str]:
        prompt = (
            "You are a toxicity classifier. Return strict JSON with keys: "
            "toxic (boolean), confidence (0 to 1 float), reason (short string). "
            "No markdown, no extra text. Text to classify: "
            f"{text}"
        )
        payload = {
            "model": settings.ollama_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                timeout=settings.ollama_timeout_seconds,
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            parsed = self._parse_json(raw)
            toxic = bool(parsed.get("toxic", False))
            confidence = float(parsed.get("confidence", 0.6))
            confidence = max(0.0, min(1.0, confidence))
            reason = str(parsed.get("reason", "Classified by local model"))
            return toxic, confidence, reason
        except Exception:
            return self._heuristic_fallback(text)

    @staticmethod
    def _parse_json(raw: str) -> dict:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group(0))
                except json.JSONDecodeError:
                    return {}
            return {}

    @staticmethod
    def _heuristic_fallback(text: str) -> Tuple[bool, float, str]:
        normalized = text.lower()
        hit = any(keyword in normalized for keyword in TOXIC_KEYWORDS)
        if hit:
            return True, 0.72, "Keyword match: toxic"
        return False, 0.65, "Keyword match: clean"
