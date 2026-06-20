"""Shared model catalog for CLI, interactive mode, and the app.

The harness still accepts any provider/model string. This file only defines
known-good local options that should be easy to discover from the UI.
"""

from __future__ import annotations

DEFAULT_MODEL = "openrouter/openrouter/free"
GPT_OSS_20B_MODEL = "ollama/gpt-oss:20b"
OPENROUTER_FREE_MODEL = "openrouter/openrouter/free"
OPENROUTER_CLAUDE_MODEL = "openrouter/anthropic/claude-3.5-sonnet"
OPENROUTER_GEMINI_MODEL = "openrouter/google/gemini-2.0-flash-001"
OPENROUTER_LLAMA_MODEL = "openrouter/meta-llama/llama-3.3-70b-instruct"
NVIDIA_GEMMA_MODEL = "nvidia/google/gemma-4-31b-it"
NVIDIA_QWEN_MODEL = "nvidia/qwen/qwen3.5-122b-a10b"
NVIDIA_QWEN_NEXT_MODEL = "nvidia/qwen/qwen3-next-80b-a3b-instruct"
NVIDIA_KIMI_MODEL = "nvidia/moonshotai/kimi-k2.6"
MISTRAL_SMALL_MODEL = "mistral/mistral-small-2603"

RECOMMENDED_MODELS = (
    DEFAULT_MODEL,
    OPENROUTER_CLAUDE_MODEL,
    OPENROUTER_GEMINI_MODEL,
    OPENROUTER_LLAMA_MODEL,
    GPT_OSS_20B_MODEL,
    MISTRAL_SMALL_MODEL,
    NVIDIA_GEMMA_MODEL,
    NVIDIA_QWEN_MODEL,
    NVIDIA_QWEN_NEXT_MODEL,
    NVIDIA_KIMI_MODEL,
)

API_MODELS = (
    OPENROUTER_FREE_MODEL,
    OPENROUTER_CLAUDE_MODEL,
    OPENROUTER_GEMINI_MODEL,
    OPENROUTER_LLAMA_MODEL,
    MISTRAL_SMALL_MODEL,
    NVIDIA_GEMMA_MODEL,
    NVIDIA_QWEN_MODEL,
    NVIDIA_QWEN_NEXT_MODEL,
    NVIDIA_KIMI_MODEL,
)


def ollama_model_id(name: str) -> str:
    return f"ollama/{name}"


def model_options(installed_ollama_models: list[str] | tuple[str, ...] = ()) -> list[str]:
    """Installed Ollama models first, then recommended fallbacks."""
    options: list[str] = []
    seen: set[str] = set()
    for name in installed_ollama_models:
        model = ollama_model_id(name)
        if model not in seen:
            options.append(model)
            seen.add(model)
    for model in RECOMMENDED_MODELS:
        if model not in seen:
            options.append(model)
            seen.add(model)
    return options


def api_model_options() -> list[str]:
    return list(API_MODELS)
