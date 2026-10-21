import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from module_2_reasoning.paths import DATA_DIR
from pydantic import BaseModel

from ..dependencies import get_current_user

router = APIRouter(dependencies=[Depends(get_current_user)])

_JSON_EXPORTS_DIR = DATA_DIR / "json_exports"
_REPORTS_DIR = DATA_DIR / "reports"


class PatientInfoSummary(BaseModel):
    age: Optional[int] = None
    gender: Optional[str] = None
    activity_level: Optional[str] = None


class PatientSessionSummary(BaseModel):
    session_id: str
    generated_at: str
    patient_info: Optional[PatientInfoSummary] = None
    test_count: int
    has_docx: bool
    json_url: str
    docx_url: Optional[str] = None


class PatientListResponse(BaseModel):
    patients: list[PatientSessionSummary]
    total: int


def _load_sessions() -> list[PatientSessionSummary]:
    sessions: list[PatientSessionSummary] = []

    # From data/reports/{session_id}/ dirs (created by API jobs)
    if _REPORTS_DIR.exists():
        for entry in sorted(_REPORTS_DIR.iterdir(), reverse=True):
            if not entry.is_dir():
                continue
            session_id = entry.name
            # Find JSON file in this dir
            json_files = list(entry.glob("*.json"))
            if not json_files:
                continue
            json_path = json_files[0]
            docx_files = list(entry.glob("*.docx"))
            has_docx = bool(docx_files)
            try:
                with open(json_path, encoding="utf-8") as f:
                    data = json.load(f)
                patient_info = None
                pi = data.get("patient_info")
                if pi:
                    patient_info = PatientInfoSummary(
                        age=pi.get("age"),
                        gender=pi.get("gender"),
                        activity_level=pi.get("activity_level"),
                    )
                test_count = len(data.get("test_results", []))
                generated_at = data.get("generated_at", "")
                sessions.append(
                    PatientSessionSummary(
                        session_id=session_id,
                        generated_at=generated_at,
                        patient_info=patient_info,
                        test_count=test_count,
                        has_docx=has_docx,
                        json_url=f"/api/v1/patients/{session_id}/json",
                        docx_url=f"/api/v1/patients/{session_id}/docx" if has_docx else None,
                    )
                )
            except Exception:
                continue

    return sessions


@router.get("/patients", response_model=PatientListResponse)
async def list_patients(limit: int = 50, offset: int = 0) -> PatientListResponse:
    sessions = _load_sessions()
    total = len(sessions)
    page = sessions[offset : offset + limit]
    return PatientListResponse(patients=page, total=total)


@router.get("/patients/{session_id}/json")
async def get_patient_json(session_id: str):
    # Look in data/reports/{session_id}/
    session_dir = _REPORTS_DIR / session_id
    if session_dir.exists():
        json_files = list(session_dir.glob("*.json"))
        if json_files:
            with open(json_files[0], encoding="utf-8") as f:
                return json.load(f)
    raise HTTPException(
        status_code=404,
        detail={"code": "SESSION_NOT_FOUND", "message": f"Session {session_id} not found"},
    )


@router.get("/patients/{session_id}/docx")
async def get_patient_docx(session_id: str):
    session_dir = _REPORTS_DIR / session_id
    if session_dir.exists():
        docx_files = list(session_dir.glob("*.docx"))
        if docx_files:
            return FileResponse(
                path=str(docx_files[0]),
                media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=f"report_{session_id[:8]}.docx",
            )
    raise HTTPException(
        status_code=404,
        detail={"code": "SESSION_NOT_FOUND", "message": f"Session {session_id} not found or has no DOCX"},
    )
