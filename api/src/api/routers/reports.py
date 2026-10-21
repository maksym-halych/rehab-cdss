import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from ..dependencies import get_current_user, get_job_store
from ..models.jobs import JobStatus, Module2Status
from ..services.job_store import JobStore

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/reports/{job_id}/json")
async def get_report_json(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
):
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} does not exist"},
        )
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "JOB_NOT_COMPLETED",
                "message": f"Job is {job.status.value}",
            },
        )
    if not job.json_export_path or not Path(job.json_export_path).exists():
        raise HTTPException(
            status_code=500,
            detail={
                "code": "JSON_NOT_FOUND",
                "message": "JSON export was not produced",
            },
        )
    with open(job.json_export_path, encoding="utf-8") as f:
        data = json.load(f)
    return data


@router.get("/reports/{job_id}/docx")
async def get_report_docx(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
):
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} does not exist"},
        )
    if job.status != JobStatus.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "JOB_NOT_COMPLETED",
                "message": f"Job is {job.status.value}",
            },
        )
    if not job.docx_path or not Path(job.docx_path).exists():
        raise HTTPException(
            status_code=404,
            detail={"code": "DOCX_NOT_FOUND", "message": "DOCX was not produced"},
        )
    return FileResponse(
        path=job.docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"report_{job_id[:8]}.docx",
    )


@router.get("/reports/{job_id}/rehab-report")
async def get_rehab_report_md(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
):
    """Return the Module 2 rehabilitation report as plain text markdown."""
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} does not exist"},
        )
    if job.module2_status != Module2Status.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MODULE2_NOT_COMPLETED",
                "message": f"Module 2 is {job.module2_status.value}",
            },
        )
    if not job.module2_report_md_path or not Path(job.module2_report_md_path).exists():
        raise HTTPException(
            status_code=404,
            detail={
                "code": "REPORT_NOT_FOUND",
                "message": "Rehabilitation report was not produced",
            },
        )
    content = Path(job.module2_report_md_path).read_text(encoding="utf-8")
    return PlainTextResponse(content, media_type="text/plain; charset=utf-8")


@router.get("/reports/{job_id}/rehab-report/docx")
async def get_rehab_report_docx(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
):
    """Download the Module 2 rehabilitation report as DOCX."""
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} does not exist"},
        )
    if job.module2_status != Module2Status.COMPLETED:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "MODULE2_NOT_COMPLETED",
                "message": f"Module 2 is {job.module2_status.value}",
            },
        )
    if (
        not job.module2_report_docx_path
        or not Path(job.module2_report_docx_path).exists()
    ):
        raise HTTPException(
            status_code=404,
            detail={
                "code": "DOCX_NOT_FOUND",
                "message": "DOCX report was not produced",
            },
        )
    return FileResponse(
        path=job.module2_report_docx_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=f"rehabilitation_report_{job_id[:8]}.docx",
    )
