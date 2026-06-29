import logging

from google import genai
from google.genai import types

logger = logging.getLogger("llm.gemini")


class GeminiProvider:
    DEFAULT_MODEL = "gemini-2.5-pro"

    def __init__(self, api_key: str, model: str) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model or self.DEFAULT_MODEL
        # Real token usage of the most recent call_model(). 0 until first call,
        # and 0 whenever the response carries no usage_metadata (never crashes).
        self.last_usage_tokens: int = 0

    def call_model(self, prompt: str, *, system: str | None = None) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
        ) if system else None
        response = self._client.models.generate_content(
            model=self._model,
            contents=prompt,
            config=config,
        )
        self.last_usage_tokens = self._extract_usage_tokens(response)
        logger.info(
            "gemini.call model=%s tokens=%s", self._model, self.last_usage_tokens
        )
        return response.text

    @staticmethod
    def _extract_usage_tokens(response) -> int:
        """Read REAL total token usage from the google-genai response.

        Prefers ``total_token_count``; falls back to summing prompt + candidate
        counts. Returns 0 when ``usage_metadata`` is absent or unreadable — this
        never raises so a missing/odd usage field cannot break a model call.
        """
        try:
            usage = getattr(response, "usage_metadata", None)
            if usage is None:
                return 0
            total = getattr(usage, "total_token_count", None)
            if total is not None:
                return int(total)
            prompt_tokens = getattr(usage, "prompt_token_count", None) or 0
            candidate_tokens = getattr(usage, "candidates_token_count", None) or 0
            return int(prompt_tokens) + int(candidate_tokens)
        except (TypeError, ValueError):
            return 0
