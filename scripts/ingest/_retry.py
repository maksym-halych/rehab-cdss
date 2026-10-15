"""LLM retry logic for the ingest pipeline."""

import time
from typing import Callable, TypeVar

import openai

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
    If fallback fails, re-raise. If not provided, keep backoff + retry behavior.

    Args:
        invoke_fn: Callable with no args that returns the LLM result.
        fallback_invoke_fn: Optional callable to use on RateLimitError (single attempt).
        attempts: Number of retry attempts (default 5).
        base_delay: Base delay in seconds for exponential backoff (default 4.0).

    Returns:
        The result of invoke_fn() or fallback_invoke_fn().

    Raises:
        The last exception if all attempts fail.
    """
    last_err: BaseException | None = None
    for attempt in range(attempts):
        try:
            return invoke_fn()
        except openai.RateLimitError as e:
            last_err = e
            if fallback_invoke_fn is not None:
                print("  Rate limit hit. Trying fallback model once...")
                try:
                    return fallback_invoke_fn()
                except Exception as fallback_err:
                    raise fallback_err
            delay = base_delay * (2**attempt)
            print(
                f"  API error (attempt {attempt + 1}/{attempts}): {e}. Retrying in {delay}s..."
            )
            time.sleep(delay)
        except openai.InternalServerError as e:
            last_err = e
            delay = base_delay * (2**attempt)
            print(
                f"  API error (attempt {attempt + 1}/{attempts}): {e}. Retrying in {delay}s..."
            )
            time.sleep(delay)
    raise last_err
