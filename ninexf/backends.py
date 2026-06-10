"""Model backends: ollama (local, default), anthropic (API), mock (harness testing).

All backends expose one method: complete(system, user) -> str.
Stdlib-only — HTTP via urllib so the harness has zero pip dependencies.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

from ninexf.config import Config


class BackendError(Exception):
    pass


class Backend:
    def complete(self, system: str, user: str) -> str:
        raise NotImplementedError


def _post_json(url: str, payload: dict, headers: dict, timeout: float = 300) -> dict:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:500]
        raise BackendError(f"HTTP {e.code} from {url}: {body}") from e
    except urllib.error.URLError as e:
        raise BackendError(f"cannot reach {url}: {e.reason}") from e


class OllamaBackend(Backend):
    def __init__(self, config: Config):
        self.model = config.model_name
        self.endpoint = config.endpoint.rstrip("/")

    def complete(self, system: str, user: str) -> str:
        data = _post_json(
            f"{self.endpoint}/api/chat",
            {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "stream": False,
                "options": {"temperature": 0.4, "num_ctx": 16384},
            },
            headers={},
        )
        content = data.get("message", {}).get("content", "")
        if not content:
            raise BackendError(f"empty response from ollama: {json.dumps(data)[:300]}")
        return content


class AnthropicBackend(Backend):
    def __init__(self, config: Config):
        self.model = config.model_name
        self.api_key = os.environ.get(config.api_key_env, "")
        if not self.api_key:
            raise BackendError(
                f"API mode requires {config.api_key_env} to be set in the environment"
            )

    def complete(self, system: str, user: str) -> str:
        data = _post_json(
            "https://api.anthropic.com/v1/messages",
            {
                "model": self.model,
                "max_tokens": 8192,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            headers={"x-api-key": self.api_key, "anthropic-version": "2023-06-01"},
        )
        blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        if not text:
            raise BackendError(f"empty response from anthropic: {json.dumps(data)[:300]}")
        return text


class MockBackend(Backend):
    """Deterministic scripted backend so the loop harness can be tested end-to-end
    without any inference. Alternates between planning and executing a tiny
    hello-world progression keyed off the iteration breadcrumb in the prompt."""

    def complete(self, system: str, user: str) -> str:
        if "single most useful next step" in user:
            if "src/main.py" not in user:
                return "Create src/main.py with a main() function that prints a greeting."
            return "Add a unit test for main() in tests/test_main.py."
        # Execution call: produce FILE blocks.
        if "tests/test_main.py" in user:
            return (
                "SUMMARY: Added a unit test for main().\n"
                "FILE: tests/test_main.py\n"
                "```python\n"
                "from pathlib import Path\n"
                "import subprocess, sys\n\n"
                "def test_main_runs():\n"
                "    out = subprocess.run([sys.executable, 'src/main.py'], capture_output=True, text=True)\n"
                "    assert out.returncode == 0\n"
                "```\n"
            )
        return (
            "SUMMARY: Created src/main.py with a greeting.\n"
            "FILE: src/main.py\n"
            "```python\n"
            "def main():\n"
            "    print('hello from 9xf')\n\n"
            "if __name__ == '__main__':\n"
            "    main()\n"
            "```\n"
        )


def make_backend(config: Config) -> Backend:
    provider = config.provider
    if provider == "ollama":
        return OllamaBackend(config)
    if provider == "anthropic":
        return AnthropicBackend(config)
    if provider == "mock":
        return MockBackend()
    raise BackendError(f"unknown provider {provider!r} (use ollama/<model>, anthropic/<model>, or mock)")
