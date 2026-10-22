"""
Module 2 entry point — LangGraph pipeline (Steps 1–6).

Usage:
    uv run python scripts/module2/run_pipeline.py [--file PATH]

If --file not provided, picks the most recent JSON in data/json_exports/.
Output:
    data/module2_output/{timestamp}_clinical_summary.json
    data/module2_output/{timestamp}_retrieved_protocols.json
    data/module2_output/{timestamp}_treatment_plan.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent

sys.path.insert(0, str(_PROJECT_ROOT / "api" / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts" / "ingest"))

load_dotenv(_PROJECT_ROOT / "api" / ".env", override=True)

from langchain_openai import ChatOpenAI  # noqa: E402
from module_2_reasoning.graph import build_pipeline  # noqa: E402

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# Override in .env, e.g. GEMINI_MODEL=gemini-3-flash-preview on the free tier (Pro has 0 free quota).
LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
LLM_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3-flash-preview")

JSON_EXPORTS_DIR = _PROJECT_ROOT / "data" / "json_exports"
OUTPUT_DIR = _PROJECT_ROOT / "data" / "module2_output"


def pick_latest_export() -> Path:
    exports = sorted(JSON_EXPORTS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime)
    if not exports:
        raise FileNotFoundError(f"No JSON files found in {JSON_EXPORTS_DIR}")
    return exports[-1]


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run Module 2 Clinical Reasoning pipeline."
    )
    parser.add_argument(
        "--file", type=Path, default=None, help="Path to Module 1 JSON export."
    )
    args = parser.parse_args()

    api_key = os.getenv("DIPLOMA_API_KEY")
    if not api_key:
        raise ValueError("DIPLOMA_API_KEY environment variable is required")

    input_path: Path = args.file or pick_latest_export()
    print("Loading input for de-identified processing.")

    with input_path.open(encoding="utf-8") as f:
        module1_data = json.load(f)

    patient_info = module1_data.get("patient_info", {})

    llm = ChatOpenAI(
        model=LLM_MODEL,
        base_url=GEMINI_BASE_URL,
        api_key=api_key,
        temperature=0,
    )
    fallback_llm = ChatOpenAI(
        model=LLM_FALLBACK_MODEL,
        base_url=GEMINI_BASE_URL,
        api_key=api_key,
        temperature=0,
    )

    pipeline = build_pipeline(llm, fallback_llm=fallback_llm)

    initial_state = {
        "module1_data": module1_data,
        "patient_info": patient_info,
        "filtered_results": [],
        "clinical_summary": None,
        "protocol_queries": [],
        "retrieved_protocols": [],
        "full_protocols": [],
        "draft_plan": None,
        "enriched_plan": None,
        "retries": 0,
        "grader_feedback": [],
        "relevant_protocols": [],
        "final_report": None,
    }

    final_state = pipeline.invoke(initial_state)

    summary = final_state["clinical_summary"]
    retrieved = final_state["full_protocols"]
    enriched_plan = final_state.get("enriched_plan")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%d.%m.%Y_%H-%M-%S")

    summary_path = OUTPUT_DIR / f"{timestamp}_clinical_summary.json"
    summary_path.write_text(
        json.dumps(summary.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Saved de-identified clinical summary.")

    protocols_path = OUTPUT_DIR / f"{timestamp}_retrieved_protocols.json"
    protocols_path.write_text(
        json.dumps(retrieved, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("Saved retrieved protocols.")

    if enriched_plan:
        plan_path = OUTPUT_DIR / f"{timestamp}_treatment_plan.json"
        plan_path.write_text(
            json.dumps(enriched_plan, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print("Saved de-identified treatment plan.")

    final_report = final_state.get("final_report")
    if final_report:
        reports_dir = _PROJECT_ROOT / "data" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"{timestamp}_rehabilitation_report.md"
        report_path.write_text(final_report, encoding="utf-8")
        print("Saved de-identified rehabilitation report.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "Module 2 failed. Check the input format and provider configuration.",
            file=sys.stderr,
        )
        sys.exit(1)
