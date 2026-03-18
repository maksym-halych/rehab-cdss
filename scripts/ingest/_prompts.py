"""Load prompt templates from prompts/ and substitute placeholders."""

from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"


def load_prompt(name: str, **kwargs: str) -> str:
    """
    Load a prompt from prompts/{name}.txt and substitute {{PLACEHOLDER}} with kwargs.

    Placeholders use UPPER_SNAKE_CASE (e.g., {{RAW_TEXT}}, {{RAW_NAME}}).
    If a placeholder is missing from kwargs, it is left unchanged.
    """
    path = _PROMPTS_DIR / f"{name}.txt"
    text = path.read_text(encoding="utf-8")

    for key, value in kwargs.items():
        placeholder = f"{{{{{key}}}}}"
        text = text.replace(placeholder, str(value))

    return text
