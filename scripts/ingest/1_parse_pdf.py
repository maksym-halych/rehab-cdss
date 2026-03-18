#!/usr/bin/env python3
"""Extract plain text from PDFs in 0_raw_pdfs and save to 1_extracted_raw."""

import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PyPdfError

# Resolve project root (directory containing data/ and scripts/)
_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent

INPUT_DIR = _PROJECT_ROOT / "data" / "knowledge_base" / "protocols" / "0_raw_pdfs"
OUTPUT_DIR = _PROJECT_ROOT / "data" / "knowledge_base" / "protocols" / "1_extracted_raw"

BATCH_SIZE = 10

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def extract_text_from_pdf(pdf_path: Path) -> str:
    """Extract plain text from all pages of a PDF."""
    reader = PdfReader(str(pdf_path))
    chunks: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            chunks.append(text)
    return "\n\n".join(chunks)


def _process_one(pdf_path: Path) -> tuple[str, bool]:
    """Extract a single PDF. Returns (filename, success)."""
    out_path = OUTPUT_DIR / (pdf_path.stem + ".txt")
    try:
        text = extract_text_from_pdf(pdf_path)
        out_path.write_text(text, encoding="utf-8")
        logger.info("Extracted: %s -> %s", pdf_path.name, out_path.name)
        return pdf_path.name, True
    except (OSError, PyPdfError) as e:
        logger.warning("Skipped %s: %s", pdf_path.name, e)
        return pdf_path.name, False


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT_DIR.exists():
        logger.error("Input directory does not exist: %s", INPUT_DIR)
        sys.exit(1)

    pdf_files = sorted(INPUT_DIR.glob("*.pdf"))
    if not pdf_files:
        logger.warning("No PDF files found in %s", INPUT_DIR)
        return

    logger.info(
        "Found %d PDF(s) in %s — processing with batch_size=%d",
        len(pdf_files),
        INPUT_DIR,
        BATCH_SIZE,
    )

    with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
        results = list(executor.map(_process_one, pdf_files))

    success_count = sum(1 for _, ok in results if ok)
    logger.info(
        "Done. %d/%d PDFs extracted successfully.", success_count, len(pdf_files)
    )


if __name__ == "__main__":
    main()
