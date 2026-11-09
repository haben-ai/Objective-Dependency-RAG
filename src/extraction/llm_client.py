"""Gemini client returning schema-validated JSON. API key comes from GEMINI_API_KEY (or GOOGLE_API_KEY)."""

import os
import sys
import time
from dataclasses import dataclass, field
from typing import Protocol, TypeVar

from pydantic import BaseModel, ValidationError

from config import GEMINI_MODEL

T = TypeVar("T", bound=BaseModel)


@dataclass
class LLMCall:
    purpose: str
    model: str
    system: str
    prompt: str
    raw_response: str
    seconds: float
    attempts: int
    usage: dict = field(default_factory=dict)


class LLM(Protocol):
    model: str

    def generate(self, purpose: str, system: str, prompt: str, schema: type[T]) -> tuple[T, LLMCall]: ...


class LLMError(RuntimeError):
    pass


def log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


class GeminiLLM:
    def __init__(self, model: str | None = None, temperature: float = 0.0, seed: int = 42, max_attempts: int = 2):
        _load_env()
        if not (os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")):
            raise LLMError("GEMINI_API_KEY is not set. Put it in .env (see .env.example) or export it.")
        from google import genai

        self._genai_types = types = __import__("google.genai.types", fromlist=["types"])
        # Our own retry loop (below) handles overload errors visibly; the SDK's silent retries are disabled
        # and every request gets a hard timeout, so a congested model cannot hang a run indefinitely.
        self._client = genai.Client(
            http_options=types.HttpOptions(
                timeout=int(os.environ.get("GEMINI_TIMEOUT_S", "180")) * 1000,
                retry_options=types.HttpRetryOptions(attempts=1),
            )
        )
        self.model = model or GEMINI_MODEL
        self.temperature = temperature
        self.seed = seed
        self.max_attempts = max_attempts
        self.transient_retries = 3
        self.backoff_s = (10, 30, 60)

    def _request(self, contents, config, purpose: str):
        from google.genai import errors

        for i in range(self.transient_retries + 1):
            t = time.time()
            try:
                resp = self._client.models.generate_content(model=self.model, contents=contents, config=config)
                log(f"[{self.model}] {purpose}: ok in {time.time() - t:.1f}s")
                return resp
            except (errors.ServerError, errors.ClientError) as e:
                code = getattr(e, "code", None)
                transient = code in (429, 500, 503, 504)
                log(f"[{self.model}] {purpose}: HTTP {code} after {time.time() - t:.1f}s" + (" - retrying" if transient and i < self.transient_retries else ""))
                if not transient or i == self.transient_retries:
                    raise LLMError(f"Gemini request failed ({self.model}, HTTP {code}): {str(e)[:300]}") from e
                time.sleep(self.backoff_s[min(i, len(self.backoff_s) - 1)])
            except Exception as e:  # timeouts, network
                log(f"[{self.model}] {purpose}: {type(e).__name__} after {time.time() - t:.1f}s")
                if i == self.transient_retries:
                    raise LLMError(f"Gemini request failed ({self.model}): {e}") from e
                time.sleep(self.backoff_s[min(i, len(self.backoff_s) - 1)])

    def generate(self, purpose: str, system: str, prompt: str, schema: type[T]) -> tuple[T, LLMCall]:
        types = self._genai_types
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            seed=self.seed,
            response_mime_type="application/json",
            response_schema=schema,
        )
        contents, last_error, t0 = prompt, None, time.time()
        for attempt in range(1, self.max_attempts + 1):
            resp = self._request(contents, config, purpose)
            text = resp.text or ""
            try:
                parsed = schema.model_validate_json(text)
            except ValidationError as e:
                last_error = e
                contents = f"{prompt}\n\nYour previous answer did not match the JSON schema:\n{e}\nReturn corrected JSON only."
                continue
            usage = resp.usage_metadata.model_dump(exclude_none=True) if resp.usage_metadata else {}
            return parsed, LLMCall(purpose, self.model, system, prompt, text, time.time() - t0, attempt, usage)
        raise LLMError(f"Gemini output failed schema validation after {self.max_attempts} attempts: {last_error}")


def _load_env() -> None:
    """Load the project .env (never overrides variables already set in the environment)."""
    try:
        from dotenv import load_dotenv

        from config import ROOT

        load_dotenv(ROOT / ".env")
    except ImportError:
        pass


def default_llm(model: str | None = None) -> LLM:
    return GeminiLLM(model=model)
