"""Minimal standard-library client for OpenAI-compatible chat APIs."""

from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from llm_client.config import LLMConfig


class LLMClientError(RuntimeError):
    """Base error for model transport or response failures."""


class LLMJSONParseError(LLMClientError):
    """Raised when a model response is not strict JSON."""


class InsufficientEvidenceError(LLMClientError):
    """Raised when a Prompt Package returns its stop signal."""


class OpenAICompatibleClient:
    """Send Prompt Packages to an OpenAI-compatible chat completions API."""

    def __init__(self, config: LLMConfig, timeout_seconds: int = 60):
        config.validate()
        if config.mock_mode:
            raise LLMClientError("LLM client cannot be created in Mock mode")
        self._config = config
        self._timeout_seconds = timeout_seconds

    def generate_json(self, prompt_package: dict[str, Any]) -> Any:
        """Call the model and parse its message content as strict JSON."""
        request_body = {
            "model": self._config.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": prompt_package["system_prompt"],
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "input_data": prompt_package["input_data"],
                            "output_schema": prompt_package["output_schema"],
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
        }
        response = self._post_json(request_body)
        content = self._extract_content(response)

        stop_signal = prompt_package.get(
            "insufficient_evidence_signal", "insufficient_evidence"
        )
        if content.strip() == stop_signal:
            raise InsufficientEvidenceError(
                f"{prompt_package.get('stage', 'LLM stage')}: "
                "insufficient evidence"
            )

        try:
            return json.loads(content)
        except json.JSONDecodeError as error:
            raise LLMJSONParseError(
                f"{prompt_package.get('stage', 'LLM stage')}: model output "
                f"is not valid JSON ({error.msg} at position {error.pos})"
            ) from error

    def _post_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = _chat_completions_endpoint(self._config.base_url or "")
        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._config.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self._timeout_seconds) as response:
                raw_response = response.read().decode("utf-8")
        except HTTPError as error:
            raise LLMClientError(
                f"LLM API returned HTTP {error.code}"
            ) from error
        except (URLError, TimeoutError) as error:
            raise LLMClientError(f"LLM API request failed: {error}") from error

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as error:
            raise LLMClientError("LLM API response envelope is not JSON") from error
        if not isinstance(parsed, dict):
            raise LLMClientError("LLM API response envelope must be an object")
        return parsed

    @staticmethod
    def _extract_content(response: dict[str, Any]) -> str:
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as error:
            raise LLMClientError(
                "LLM API response is missing choices[0].message.content"
            ) from error
        if not isinstance(content, str) or not content.strip():
            raise LLMClientError("LLM API returned empty message content")
        return content


def _chat_completions_endpoint(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    return normalized + "/chat/completions"
