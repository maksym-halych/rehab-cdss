"""Async service for running Module 2 (LLM reasoning pipeline) in the background."""

import asyncio
import json
import os
from pathlib import Path

from ..models.jobs import Module2Status, MODULE2_STEPS
from ..services.job_store import JobStore, _EXECUTOR

REPORTS_ROOT = Path("data/reports")

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
# Override in .env, e.g. GEMINI_MODEL=gemini-3-flash-preview on the free tier (Pro has 0 free quota).
LLM_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
LLM_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3-flash-preview")


async def run_module2_async(
    job_id: str,
    json_export_path: str,
    job_store: JobStore,
) -> None:
    """Run Module 2 pipeline asynchronously in a thread pool executor.

    Bridges sync LangGraph execution to async job status updates via
    ``asyncio.run_coroutine_threadsafe`` for per-node progress tracking.
    """
    api_key = os.getenv("DIPLOMA_API_KEY")
    if not api_key:
        await job_store.update(
            job_id,
            module2_status=Module2Status.FAILED,
            module2_error="DIPLOMA_API_KEY environment variable is not set",
        )
        return

    from module_2_reasoning.embeddings import embedding_key_env

    embed_key_env = embedding_key_env()
    if not os.getenv(embed_key_env):
        await job_store.update(
            job_id,
            module2_status=Module2Status.FAILED,
            module2_error=f"{embed_key_env} environment variable is not set (required for embeddings)",
        )
        return

    await job_store.update(job_id, module2_status=Module2Status.RUNNING)
    loop = asyncio.get_running_loop()

    # Step name -> (index, label) lookup
    step_lookup = {name: (i, label) for i, (name, label) in enumerate(MODULE2_STEPS)}

    def _on_step(step_name: str):
        """Callback invoked from the pipeline thread for each node start."""
        idx, label = step_lookup.get(step_name, (0, step_name))
        asyncio.run_coroutine_threadsafe(
            job_store.update(
                job_id,
                module2_step=step_name,
                module2_step_index=idx,
                module2_step_label=label,
            ),
            loop,
        )

    def _run():
        from langchain_openai import ChatOpenAI
        from module_2_reasoning.graph import build_pipeline

        with open(json_export_path, encoding="utf-8") as f:
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

        pipeline = build_pipeline(
            llm, fallback_llm=fallback_llm, on_step_start=_on_step
        )

        initial_state = {
            "module1_data": module1_data,
            "patient_info": patient_info,
            "filtered_results": [],
            "clinical_summary": None,
            "protocol_queries": [],
            "full_protocols": [],
            "draft_plan": None,
            "enriched_plan": None,
            "english_report": None,
            "retries": 0,
            "grader_feedback": [],
            "relevant_protocols": [],
            "final_report": None,
        }

        final_state = pipeline.invoke(initial_state)

        # Save markdown report
        job_dir = REPORTS_ROOT / job_id
        job_dir.mkdir(parents=True, exist_ok=True)

        md_path = None
        docx_path = None

        final_report = final_state.get("final_report")
        if final_report:
            md_path = str(job_dir / "rehabilitation_report.md")
            Path(md_path).write_text(final_report, encoding="utf-8")

            # Generate DOCX from the markdown report
            from module_2_reasoning.docx_export import markdown_to_docx

            docx_path = str(job_dir / "rehabilitation_report.docx")
            markdown_to_docx(final_report, docx_path)

        return md_path, docx_path

    try:
        md_path, docx_path = await loop.run_in_executor(_EXECUTOR, _run)
        await job_store.update(
            job_id,
            module2_status=Module2Status.COMPLETED,
            module2_step="report_formatter",
            module2_step_index=8,
            module2_step_label="Формування звіту",
            module2_report_md_path=md_path,
            module2_report_docx_path=docx_path,
        )
    except Exception as exc:
        await job_store.update(
            job_id,
            module2_status=Module2Status.FAILED,
            module2_error=str(exc),
        )
