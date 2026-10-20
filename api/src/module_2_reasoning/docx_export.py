"""Convert rehabilitation report markdown to DOCX format.

The input markdown has a predictable structure produced by ``render_markdown()``
in ``report_formatter.py``.  This module parses that structure and maps it to
Word document elements using python-docx.
"""

from __future__ import annotations

import re

from docx import Document
from docx.shared import Cm, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH


# Bold prefixes used in exercise bullet items (Ukrainian)
_BOLD_PREFIXES = frozenset(
    {
        "Інструкції:",
        "Дозування:",
        "Обґрунтування:",
    }
)


def markdown_to_docx(markdown: str, output_path: str) -> None:
    """Parse the structured rehabilitation report markdown and produce a Word document.

    Handles the heading hierarchy (H1-H4), bold lines, bullet lists, and regular
    paragraphs emitted by ``render_markdown()``.
    """
    doc = Document()

    # ---- Page setup (A4) ----
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2)
    section.bottom_margin = Cm(2)
    section.left_margin = Cm(2.5)
    section.right_margin = Cm(2.5)

    # ---- Default font ----
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(12)

    # Also set heading fonts for consistency
    for level in range(1, 5):
        heading_style_name = f"Heading {level}"
        if heading_style_name in doc.styles:
            doc.styles[heading_style_name].font.name = "Times New Roman"

    lines = markdown.split("\n")
    i = 0

    while i < len(lines):
        line = lines[i]

        # H1 - document title
        if line.startswith("# "):
            p = doc.add_heading(line[2:].strip(), level=1)
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            i += 1
            continue

        # H4 - subsection (check before H3/H2 due to prefix overlap)
        if line.startswith("#### "):
            doc.add_heading(line[5:].strip(), level=4)
            i += 1
            continue

        # H3 - phase title
        if line.startswith("### "):
            doc.add_heading(line[4:].strip(), level=3)
            i += 1
            continue

        # H2 - section heading
        if line.startswith("## "):
            doc.add_heading(line[3:].strip(), level=2)
            i += 1
            continue

        # Markdown table block: collect consecutive | ... | lines
        if line.startswith("|") and line.endswith("|"):
            table_lines: list[str] = []
            while i < len(lines) and lines[i].startswith("|") and lines[i].endswith("|"):
                row = lines[i]
                # Skip separator rows like |---|----------|--------|
                if not re.match(r'^\|[\s\-:|]+\|$', row):
                    table_lines.append(row)
                i += 1

            if table_lines:
                # Parse cells from each row
                parsed_rows = []
                for tl in table_lines:
                    cells = [c.strip() for c in tl.split("|")[1:-1]]
                    parsed_rows.append(cells)

                n_cols = len(parsed_rows[0]) if parsed_rows else 0
                n_rows = len(parsed_rows)

                if n_cols > 0 and n_rows > 0:
                    table = doc.add_table(rows=n_rows, cols=n_cols)
                    table.style = "Light List Accent 1"

                    for row_idx, cells in enumerate(parsed_rows):
                        for col_idx, cell_text in enumerate(cells):
                            if col_idx < n_cols:
                                cell = table.rows[row_idx].cells[col_idx]
                                cell.text = cell_text
                                # Bold the header row
                                if row_idx == 0:
                                    for paragraph in cell.paragraphs:
                                        for run in paragraph.runs:
                                            run.bold = True
            continue

        # Bold line with optional citation suffix: **some text** or **some text** [1]
        bold_line_match = re.match(r'^\*\*(.+?)\*\*(\s*\[\d+\])?\s*$', line)
        if bold_line_match and not line.startswith("**-"):
            bold_text = bold_line_match.group(1).strip()
            citation = bold_line_match.group(2)
            p = doc.add_paragraph()
            run = p.add_run(bold_text)
            run.bold = True
            run.font.size = Pt(12)
            if citation:
                p.add_run(citation)
            i += 1
            continue

        # Numbered list item (e.g., "1. Some text")
        numbered_match = re.match(r'^(\d+)\.\s+(.*)', line)
        if numbered_match:
            p = doc.add_paragraph(style="List Number")
            p.add_run(line.strip())
            i += 1
            continue

        # Bullet item
        if line.startswith("- "):
            text = line[2:].strip()
            p = doc.add_paragraph(style="List Bullet")

            # Check for known bold prefix pattern like "Інструкції: ..."
            bold_match = re.match(r"^(\S+:)\s*(.*)", text)
            if bold_match and bold_match.group(1) in _BOLD_PREFIXES:
                run = p.add_run(bold_match.group(1) + " ")
                run.bold = True
                p.add_run(bold_match.group(2))
            else:
                p.add_run(text)
            i += 1
            continue

        # Regular paragraph (skip blank lines)
        stripped = line.strip()
        if stripped:
            doc.add_paragraph(stripped)
        i += 1

    doc.save(output_path)
