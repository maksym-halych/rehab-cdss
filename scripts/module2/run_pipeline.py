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

sys.path.insert(0, str(_PROJECT_ROOT / "src"))
sys.path.insert(0, str(_PROJECT_ROOT / "scripts" / "ingest"))

load_dotenv(_PROJECT_ROOT / ".env", override=True)

from langchain_openai import ChatOpenAI  # noqa: E402
from module_2_reasoning.graph import build_pipeline  # noqa: E402

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
LLM_MODEL = "gemini-3.1-pro-preview"
LLM_FALLBACK_MODEL = "gemini-2.5-pro"

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
    print(f"Input: {input_path}")

    with input_path.open(encoding="utf-8") as f:
        module1_data = json.load(f)

    patient_info = module1_data.get("patient_info", {})
    print(f"Patient: {patient_info}")

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
    retrieved = final_state["retrieved_protocols"]
    protocol_queries = final_state["protocol_queries"]
    filtered_results = final_state["filtered_results"]
    enriched_plan = final_state.get("enriched_plan")

    state_to_dump = {
        # "module1_data_keys": list(module1_data.keys()) if module1_data else [],
        # "module1_test_count": len(module1_data.get("test_results", [])),
        "patient_info": patient_info,
        "filtered_results": [fr.model_dump() for fr in filtered_results],
        "clinical_summary": summary.model_dump() if summary else None,
        "protocol_queries": [q.model_dump() for q in protocol_queries],
        "retrieved_protocols": retrieved,
        "enriched_plan": enriched_plan,
    }

    print("\n" + "=" * 60)
    print("--- FULL PIPELINE STATE ---")
    print("=" * 60)
    print(json.dumps(state_to_dump, ensure_ascii=False, indent=2))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%d.%m.%Y_%H-%M-%S")

    summary_path = OUTPUT_DIR / f"{timestamp}_clinical_summary.json"
    summary_path.write_text(
        json.dumps(summary.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nSaved clinical_summary → {summary_path}")

    protocols_path = OUTPUT_DIR / f"{timestamp}_retrieved_protocols.json"
    protocols_path.write_text(
        json.dumps(retrieved, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"Saved retrieved_protocols → {protocols_path}")

    if enriched_plan:
        plan_path = OUTPUT_DIR / f"{timestamp}_treatment_plan.json"
        plan_path.write_text(
            json.dumps(enriched_plan, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"Saved treatment_plan → {plan_path}")

    final_report = final_state.get("final_report")
    if final_report:
        reports_dir = _PROJECT_ROOT / "data" / "reports"
        reports_dir.mkdir(parents=True, exist_ok=True)
        report_path = reports_dir / f"{timestamp}_rehabilitation_report.md"
        report_path.write_text(final_report, encoding="utf-8")
        print(f"Saved rehabilitation report → {report_path}")


if __name__ == "__main__":
    main()
