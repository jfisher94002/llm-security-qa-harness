"""Model adapters used by the harness.

The default adapter is intentionally offline and deterministic so the repository
works immediately after clone.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


class ModelAdapter(Protocol):
    name: str
    model: str

    def generate(self, prompt: str) -> str:
        ...


@dataclass
class MockModelAdapter:
    name: str = "mock"
    model: str = "deterministic-safe-stub"

    def generate(self, prompt: str) -> str:
        del prompt
        return (
            "I cannot follow instructions that override higher-priority guidance, "
            "reveal hidden prompts, or disclose sensitive data. I can provide a "
            "brief safe summary or ask for sanitized input instead."
        )


@dataclass
class OllamaAdapter:
    model: str
    base_url: str = "http://localhost:11434"
    temperature: float = 0
    timeout_seconds: int = 60
    name: str = "ollama"

    def generate(self, prompt: str) -> str:
        url = self.base_url.rstrip("/") + "/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.temperature},
        }
        data = _post_json(url, payload, self.timeout_seconds)
        return str(data.get("response", ""))


@dataclass
class OpenAIChatAdapter:
    model: str
    api_key: str
    base_url: str = "https://api.openai.com/v1"
    temperature: float = 0
    timeout_seconds: int = 60
    name: str = "openai"

    def generate(self, prompt: str) -> str:
        url = self.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.model,
            "temperature": self.temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}
        data = _post_json(url, payload, self.timeout_seconds, headers=headers)
        choices = data.get("choices", [])
        if not choices:
            return ""
        message = choices[0].get("message", {})
        return str(message.get("content", ""))


def load_adapter(config_path: Path | None) -> ModelAdapter:
    if config_path is None:
        return MockModelAdapter()

    config = load_simple_yaml(config_path)
    adapter = str(config.get("adapter", "mock")).lower()

    if adapter == "mock":
        return MockModelAdapter()

    if adapter == "ollama":
        return OllamaAdapter(
            model=str(config.get("model", "llama3.1")),
            base_url=str(config.get("base_url", "http://localhost:11434")),
            temperature=float(config.get("temperature", 0)),
            timeout_seconds=int(config.get("timeout_seconds", 60)),
        )

    if adapter == "openai":
        api_key_env = str(config.get("api_key_env", "OPENAI_API_KEY"))
        api_key = os.environ.get(api_key_env)
        if not api_key:
            raise SystemExit(
                f"OpenAI adapter selected but environment variable {api_key_env} is not set"
            )
        return OpenAIChatAdapter(
            model=str(config.get("model", "replace-with-your-model")),
            api_key=api_key,
            base_url=str(config.get("base_url", "https://api.openai.com/v1")),
            temperature=float(config.get("temperature", 0)),
            timeout_seconds=int(config.get("timeout_seconds", 60)),
        )

    raise SystemExit(f"Unsupported adapter '{adapter}'. Use mock, ollama, or openai.")


def load_simple_yaml(path: Path) -> dict[str, Any]:
    """Parse the small key/value YAML files used by config examples."""
    config: dict[str, Any] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise SystemExit(f"{path}: could not read config ({exc})") from None

    for lineno, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise SystemExit(f"{path}: line {lineno} must be a 'key: value' pair")
        key, value = line.split(":", 1)
        key = key.strip()
        value = _strip_inline_comment(value.strip())
        if not key:
            raise SystemExit(f"{path}: line {lineno} has an empty key")
        config[key] = _parse_scalar(value)
    return config


def _strip_inline_comment(value: str) -> str:
    if " #" in value:
        value = value.split(" #", 1)[0]
    return value.strip().strip("\"'")


def _parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered in {"true", "false"}:
        return lowered == "true"
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def _post_json(
    url: str,
    payload: dict[str, Any],
    timeout_seconds: int,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise SystemExit(f"Model request failed: {exc}") from None
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Model returned invalid JSON: {exc}") from None
