"""Environment-only configuration for the MarketFlow LLM client."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from urllib.parse import urlparse


class LLMConfigError(ValueError):
    """Raised when real-LLM configuration is incomplete or invalid."""


@dataclass(frozen=True)
class LLMConfig:
    """Runtime configuration loaded without reading or writing secret files."""

    mock_mode: bool = True
    api_key: str | None = field(default=None, repr=False)
    base_url: str | None = None
    model: str | None = None

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """Read supported settings from process environment variables."""
        mock_mode = _parse_bool(os.getenv("MOCK_MODE", "true"), "MOCK_MODE")
        config = cls(
            mock_mode=mock_mode,
            api_key=_clean(os.getenv("LLM_API_KEY")),
            base_url=_clean(os.getenv("LLM_BASE_URL")),
            model=_clean(os.getenv("LLM_MODEL")),
        )
        config.validate()
        return config

    def validate(self) -> None:
        """Require API settings only when a real model call is enabled."""
        if self.mock_mode:
            return

        missing = [
            name
            for name, value in (
                ("LLM_API_KEY", self.api_key),
                ("LLM_BASE_URL", self.base_url),
                ("LLM_MODEL", self.model),
            )
            if not value
        ]
        if missing:
            raise LLMConfigError(
                "Real LLM mode requires environment variables: "
                + ", ".join(missing)
            )

        parsed = urlparse(self.base_url or "")
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise LLMConfigError(
                "LLM_BASE_URL must be an absolute http(s) URL"
            )


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise LLMConfigError(
        f"{name} must be true/false, 1/0, yes/no, or on/off"
    )


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
