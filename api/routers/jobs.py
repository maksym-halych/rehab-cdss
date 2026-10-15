import json
from typing import Literal, Optional

import asyncio
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from ..dependencies import get_job_store, verify_api_key
from ..services.file_service import save_uploads
from ..models.jobs import Job, JobStatus, Module2Status
from ..services.job_store import JobStore
from ..services.pipeline_service import run_pipeline_async

router = APIRouter(dependencies=[Depends(verify_api_key)])

ALLOWED_ACTIVITY_LEVELS = {"elite", "recreational", "low"}


class JobCreatedResponse(BaseModel):
    job_id: str
    status: Literal["pending"]
    status_url: str
    created_at: str


class JobResultLinks(BaseModel):
    report_json_url: str
    report_docx_url: str
    rehab_report_md_url: Optional[str] = None
    rehab_report_docx_url: Optional[str] = None


class JobStatusResponse(BaseModel):
    job_id: str
    status: Literal["pending", "running", "completed", "failed"]
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None
    warnings: list[str] = []
    result: Optional[JobResultLinks] = None
    # Module 2 progress fields
    module2_status: Literal["idle", "running", "completed", "failed"] = "idle"
    module2_step: Optional[str] = None
    module2_step_index: int = 0
    module2_total_steps: int = 9
    module2_step_label: Optional[str] = None
    module2_error: Optional[str] = None


class JobSummary(BaseModel):
    job_id: str
    status: str
    created_at: str
    completed_at: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: list[JobSummary]
    total: int


def _job_to_status_response(job: Job) -> JobStatusResponse:
    result = None
    if job.status == JobStatus.COMPLETED:
        links = {
            "report_json_url": f"/api/v1/reports/{job.job_id}/json",
            "report_docx_url": f"/api/v1/reports/{job.job_id}/docx",
        }
        if job.module2_status == Module2Status.COMPLETED:
            links["rehab_report_md_url"] = f"/api/v1/reports/{job.job_id}/rehab-report"
            links["rehab_report_docx_url"] = (
                f"/api/v1/reports/{job.job_id}/rehab-report/docx"
            )
        result = JobResultLinks(**links)
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status.value,
        created_at=job.created_at.isoformat(),
        completed_at=job.completed_at.isoformat() if job.completed_at else None,
        error=job.error,
        warnings=job.warnings,
        result=result,
        module2_status=job.module2_status.value,
        module2_step=job.module2_step,
        module2_step_index=job.module2_step_index,
        module2_total_steps=job.module2_total_steps,
        module2_step_label=job.module2_step_label,
        module2_error=job.module2_error,
    )


@router.post(
    "/jobs", status_code=status.HTTP_202_ACCEPTED, response_model=JobCreatedResponse
)
async def create_job(
    files: list[UploadFile] = File(...),
    age: Optional[int] = Form(default=None),
    gender: Optional[str] = Form(default=None),
    activity_level: str = Form(...),
    manual_person_name: str = Form(default=""),
    selected_person_key: str = Form(default=""),
    patient_code: str = Form(default=""),
    pushup_type_overrides: str = Form(default="{}"),
    manual_test_overrides: str = Form(default="{}"),
    job_store: JobStore = Depends(get_job_store),
) -> JobCreatedResponse:
    # Validate activity level
    if activity_level not in ALLOWED_ACTIVITY_LEVELS:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_ACTIVITY_LEVEL",
                "message": f"activity_level must be one of: {sorted(ALLOWED_ACTIVITY_LEVELS)}",
            },
        )
    # Validate age
    if age is not None and not (0 <= age <= 120):
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_AGE", "message": "age must be between 0 and 120"},
        )
    # Parse JSON overrides
    try:
        pushup_overrides_dict: dict = json.loads(pushup_type_overrides)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_JSON",
                "message": "pushup_type_overrides must be valid JSON",
            },
        )
    try:
        manual_overrides_dict: dict = json.loads(manual_test_overrides)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "INVALID_JSON",
                "message": "manual_test_overrides must be valid JSON",
            },
        )
    if not files:
        raise HTTPException(
            status_code=400,
            detail={"code": "NO_FILES", "message": "No files provided"},
        )

    # Create job
    job = await job_store.create()

    # Save uploads to disk
    try:
        file_paths = await save_uploads(job.job_id, files)
    except ValueError as e:
        await job_store.update(job.job_id, status=JobStatus.FAILED, error=str(e))
        code = "FILE_TOO_LARGE" if "too large" in str(e).lower() else "INVALID_FILE"
        http_status = (
            413
            if "too large" in str(e).lower() or "too many" in str(e).lower()
            else 400
        )
        raise HTTPException(
            status_code=http_status, detail={"code": code, "message": str(e)}
        )

    # Map basename keys from the frontend to full server-side paths
    path_by_basename = {p.name: str(p) for p in file_paths}
    pushup_mapped = {
        path_by_basename.get(k, k): v for k, v in pushup_overrides_dict.items()
    }
    manual_mapped = {
        path_by_basename.get(k, k): v for k, v in manual_overrides_dict.items()
    }

    # Dispatch pipeline to thread pool (non-blocking)
    asyncio.get_running_loop().create_task(
        run_pipeline_async(
            job_id=job.job_id,
            file_paths=file_paths,
            age=age,
            gender=gender or None,
            activity_level=activity_level,
            pushup_type_overrides=pushup_mapped,
            manual_test_overrides=manual_mapped,
            selected_person_key=selected_person_key or None,
            manual_person_name=manual_person_name or None,
            patient_code=patient_code or None,
            job_store=job_store,
        )
    )

    return JobCreatedResponse(
        job_id=job.job_id,
        status="pending",
        status_url=f"/api/v1/jobs/{job.job_id}",
        created_at=job.created_at.isoformat(),
    )


@router.get("/jobs", response_model=JobListResponse)
async def list_jobs(
    status: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    job_store: JobStore = Depends(get_job_store),
) -> JobListResponse:
    all_jobs = await job_store.list_all()
    if status:
        all_jobs = [j for j in all_jobs if j.status.value == status]
    total = len(all_jobs)
    page = all_jobs[offset : offset + limit]
    return JobListResponse(
        jobs=[
            JobSummary(
                job_id=j.job_id,
                status=j.status.value,
                created_at=j.created_at.isoformat(),
                completed_at=j.completed_at.isoformat() if j.completed_at else None,
            )
            for j in page
        ],
        total=total,
    )


@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
) -> JobStatusResponse:
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} does not exist"},
        )
    return _job_to_status_response(job)


@router.delete("/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    job_store: JobStore = Depends(get_job_store),
) -> None:
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(
            status_code=404,
            detail={"code": "JOB_NOT_FOUND", "message": f"Job {job_id} does not exist"},
        )
    if job.status == JobStatus.RUNNING or job.module2_status == Module2Status.RUNNING:
        raise HTTPException(
            status_code=409,
            detail={"code": "JOB_RUNNING", "message": "Cannot cancel a running job"},
        )
    await job_store.delete(job_id)
