import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

from ..models.jobs import JobStatus
from ..services.job_store import JobStore, _EXECUTOR

REPORTS_ROOT = Path("data/reports")


async def run_pipeline_async(
    job_id: str,
    file_paths: list[Path],
    age: int | None,
    gender: str | None,
    activity_level: str,
    pushup_type_overrides: dict,
    manual_test_overrides: dict,
    selected_person_key: str | None,
    manual_person_name: str | None,
    patient_code: str | None,
    job_store: JobStore,
) -> None:
    await job_store.update(job_id, status=JobStatus.RUNNING)
    loop = asyncio.get_running_loop()

    # Per-job output dir for JSON + DOCX (API jobs get their own folder)
    job_export_dir = str(REPORTS_ROOT / job_id)
    os.makedirs(job_export_dir, exist_ok=True)

    def _run():
        from module_1_aggregation.processing.pipeline import run_pipeline_core

        return run_pipeline_core(
            file_paths=[str(p) for p in file_paths],
            age=age,
            gender=gender,
            activity_level=activity_level,
            pushup_type_overrides=pushup_type_overrides,
            manual_test_overrides=manual_test_overrides,
            selected_person_key=selected_person_key,
            manual_person_name=manual_person_name,
            patient_code=patient_code,
            output_export_dir=job_export_dir,
        )

    try:
        result = await loop.run_in_executor(_EXECUTOR, _run)

        if result.error:
            await job_store.update(
                job_id,
                status=JobStatus.FAILED,
                completed_at=datetime.now(timezone.utc),
                error=result.error,
            )
        else:
            # Move DOCX into job reports dir if it's not already there
            docx_path = result.docx_path
            if docx_path and Path(docx_path).exists():
                target_docx = Path(job_export_dir) / Path(docx_path).name
                if str(Path(docx_path).resolve()) != str(target_docx.resolve()):
                    import shutil

                    shutil.copy2(docx_path, target_docx)
                    docx_path = str(target_docx)

            await job_store.update(
                job_id,
                status=JobStatus.COMPLETED,
                completed_at=datetime.now(timezone.utc),
                docx_path=docx_path,
                json_export_path=result.json_export_path,
                warnings=result.warnings,
            )

            # Auto-start Module 2 if JSON export exists
            if result.json_export_path and Path(result.json_export_path).exists():
                from .module2_service import run_module2_async

                asyncio.get_running_loop().create_task(
                    run_module2_async(job_id, result.json_export_path, job_store)
                )
    except Exception as exc:
        await job_store.update(
            job_id,
            status=JobStatus.FAILED,
            completed_at=datetime.now(timezone.utc),
            error=str(exc),
        )
    finally:
        from .file_service import cleanup_run_dir

        await cleanup_run_dir(job_id)
