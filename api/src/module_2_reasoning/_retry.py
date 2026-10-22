"""LLM retry logic with exponential backoff and fallback model support."""

import time
from typing import Any, Callable, TypeVar

import openai
from langchain_core.globals import get_debug, get_verbose

from .privacy import PrivacyError, active_guard

T = TypeVar("T")


def invoke_with_retry(
    invoke_fn: Callable[[], T],
    *,
    fallback_invoke_fn: Callable[[], T] | None = None,
    attempts: int = 5,
    base_delay: float = 4.0,
) -> T:
    """Retry LLM invoke on transient API errors with exponential backoff.

    On RateLimitError: if fallback_invoke_fn is provided, call it once (no retry).
    If fallback fails, raise a safe error. Otherwise keep backoff + retry behavior.

    Args:
        invoke_fn: Callable with no args that returns the LLM result.
        fallback_invoke_fn: Optional callable to use on RateLimitError (single attempt).
        attempts: Number of retry attempts (default 5).
        base_delay: Base delay in seconds for exponential backoff (default 4.0).

    Returns:
        The result of invoke_fn() or fallback_invoke_fn().

    Raises:
        PrivacyError with a static message if all attempts fail.
    """
    for attempt in range(attempts):
        try:
            return invoke_fn()
        except openai.RateLimitError:
            if fallback_invoke_fn is not None:
                print("  Rate limit hit. Trying fallback model once...")
                try:
                    return fallback_invoke_fn()
                except Exception:
                    raise PrivacyError("The fallback model request failed.") from None
            delay = base_delay * (2**attempt)
            print(
                f"  Rate limit (attempt {attempt + 1}/{attempts}); retry in {delay}s."
            )
            time.sleep(delay)
        except openai.InternalServerError:
            delay = base_delay * (2**attempt)
            print(
                f"  Provider unavailable (attempt {attempt + 1}/{attempts}); retry in {delay}s."
            )
            time.sleep(delay)
    raise PrivacyError("The model request failed after retries.") from None


def invoke_structured(
    llm: Any,
    schema: type[T],
    prompt: str,
    fallback_llm: Any | None = None,
) -> T:
    """Bind schema to LLM, invoke with retry/fallback, and return structured output."""
    guard = active_guard()
    if (
        get_debug()
        or get_verbose()
        or any(
            getattr(client, "callbacks", None) or getattr(client, "verbose", False)
            for client in (llm, fallback_llm)
            if client is not None
        )
    ):
        raise PrivacyError(
            "Patient processing does not permit debug output or model callbacks."
        )
    # Give the SDK a JSON schema, not a Pydantic class. Its automatic parsed-model
    # serialization can issue warnings containing the unsanitized response.
    # Validate locally, after removing identities from the returned JSON.
    # Use the SDK's public strict-schema converter to preserve the previous
    # Pydantic request format, including required fields and nullable defaults.
    function = openai.pydantic_function_tool(schema)["function"]
    output_schema = {
        "name": function["name"],
        "strict": True,
        "schema": function["parameters"],
    }
    structured_llm = llm.with_structured_output(output_schema)

    def _invoke() -> T:
        return schema.model_validate(
            guard.clean(structured_llm.invoke(guard.text(prompt)))
        )

    fallback_invoke_fn = None
    if fallback_llm is not None:
        fallback_structured = fallback_llm.with_structured_output(output_schema)

        def _fallback() -> T:
            return schema.model_validate(
                guard.clean(fallback_structured.invoke(guard.text(prompt)))
            )

        fallback_invoke_fn = _fallback

    try:
        return invoke_with_retry(_invoke, fallback_invoke_fn=fallback_invoke_fn)
    except PrivacyError:
        raise
    except Exception:
        raise PrivacyError("The model request failed.") from None
