"""Embedding function shared by the ingest scripts and retrieval.

Ingest and retrieval MUST use the same provider and model: vectors from different
models are not comparable (and usually differ in dimension). After changing
EMBEDDING_PROVIDER or EMBEDDING_MODEL, delete data/chromadb/ and re-run
scripts/ingest/2..4.

Environment:
    EMBEDDING_PROVIDER  "openai" (default, uses OPENAI_API_KEY) or
                        "gemini" (uses DIPLOMA_API_KEY via Gemini's OpenAI-compatible API)
    EMBEDDING_MODEL     optional override of the provider's default model
"""

from __future__ import annotations

import os

from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

_PROVIDERS = {
    # provider: (api key env var, default model, api base)
    "openai": ("OPENAI_API_KEY", "text-embedding-3-small", None),
    "gemini": ("DIPLOMA_API_KEY", "gemini-embedding-001", GEMINI_BASE_URL),
}


def embedding_provider() -> str:
    provider = os.getenv("EMBEDDING_PROVIDER", "openai").strip().lower()
    if provider not in _PROVIDERS:
        raise ValueError(
            f"EMBEDDING_PROVIDER must be one of {sorted(_PROVIDERS)}, got {provider!r}"
        )
    return provider


def embedding_key_env() -> str:
    """Name of the env var holding the API key for the configured provider."""
    return _PROVIDERS[embedding_provider()][0]


def make_embedding_function() -> OpenAIEmbeddingFunction:
    provider = embedding_provider()
    key_env, default_model, api_base = _PROVIDERS[provider]
    api_key = os.getenv(key_env)
    if not api_key:
        raise ValueError(
            f"{key_env} environment variable is required for embeddings "
            f"(EMBEDDING_PROVIDER={provider})"
        )
    model = os.getenv("EMBEDDING_MODEL") or default_model
    return OpenAIEmbeddingFunction(api_key=api_key, model_name=model, api_base=api_base)
