"""Entry point for launching the rehab CDSS app."""

import unicodedata

import gradio_client.utils as _gc_utils

_orig_strip = _gc_utils.strip_invalid_filename_characters


def _nfc_strip_invalid_filename_characters(filename: str, max_bytes: int = 200) -> str:
    return _orig_strip(unicodedata.normalize("NFC", filename), max_bytes)


_gc_utils.strip_invalid_filename_characters = _nfc_strip_invalid_filename_characters

from .layout import build_app


def launch_app() -> None:
    """Launch the Gradio app."""
    build_app().queue().launch(
        server_name="0.0.0.0", server_port=7860, show_error=False
    )
