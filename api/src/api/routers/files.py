import os
import tempfile
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from ..dependencies import verify_api_key
from ..services.file_service import ALLOWED_EXTENSIONS, MAX_FILE_SIZE_BYTES, MAX_FILES_PER_JOB

router = APIRouter(dependencies=[Depends(verify_api_key)])

ALLOWED_EXT_SET = ALLOWED_EXTENSIONS


class PersonGuessResponse(BaseModel):
    key: str
    display: str
    surname: Optional[str] = None
    name: Optional[str] = None
    source: Optional[str] = None


class PdfFileGroups(BaseModel):
    dental: list[str] = []
    postural: list[str] = []
    baropodometry: list[str] = []
    dynamic_baropodometry: list[str] = []
    spine3d: list[str] = []


class CsvFileGroups(BaseModel):
    cervical_goniometry: list[str] = []
    leg_dynamometry: list[str] = []
    leg_goniometry: list[str] = []
    arm_goniometry: list[str] = []
    arm_dynamometry: list[str] = []
    single_leg_balance: list[str] = []
    single_leg_landing: list[str] = []
    mccall_hamstrings: list[str] = []
    shoulder_test: list[str] = []
    push_up: list[str] = []
    handstand_push_up: list[str] = []
    counter_movement_jump: list[str] = []
    single_leg_counter_movement_jump: list[str] = []
    drop_jump: list[str] = []
    imtp: list[str] = []
    bipodal_stance: list[str] = []
    bipodal_landing: list[str] = []
    skipping: list[str] = []
    squats_advanced_analysis: list[str] = []


class FileGroups(BaseModel):
    pdf: PdfFileGroups
    csv: CsvFileGroups
    unknown: list[str] = []


class DetectFilesResponse(BaseModel):
    detected_people: list[PersonGuessResponse]
    file_groups: FileGroups
    file_assignments: dict[str, str] = {}
    total_files: int
    recognized_files: int
    unrecognized_files: int


@router.post("/files/detect", response_model=DetectFilesResponse)
async def detect_files_endpoint(
    files: list[UploadFile] = File(...),
    manual_person_name: str = Form(default=""),
) -> DetectFilesResponse:
    if not files:
        raise HTTPException(status_code=400, detail={"code": "NO_FILES", "message": "No files provided"})
    if len(files) > MAX_FILES_PER_JOB:
        raise HTTPException(status_code=413, detail={"code": "TOO_MANY_FILES", "message": f"Too many files: max {MAX_FILES_PER_JOB}"})

    # Save to temp dir for detection
    with tempfile.TemporaryDirectory() as tmp_dir:
        saved_paths: list[str] = []
        for upload in files:
            suffix = Path(upload.filename or "").suffix.lower()
            if suffix not in ALLOWED_EXT_SET:
                raise HTTPException(
                    status_code=400,
                    detail={"code": "INVALID_FILE_TYPE", "message": f"Unsupported file type: {upload.filename}"},
                )
            safe_name = os.path.basename(upload.filename or "upload")
            dest = os.path.join(tmp_dir, safe_name)
            total = 0
            async with aiofiles.open(dest, "wb") as f:
                while chunk := await upload.read(65536):
                    total += len(chunk)
                    if total > MAX_FILE_SIZE_BYTES:
                        raise HTTPException(
                            status_code=413,
                            detail={"code": "FILE_TOO_LARGE", "message": f"File too large: {upload.filename}"},
                        )
                    await f.write(chunk)
            saved_paths.append(dest)

        # Use existing detection logic
        from module_1_aggregation.processing.file_detection import detect_files
        from module_1_aggregation.processing.person_detection import (
            build_people_index,
            UNKNOWN_PERSON_KEY,
        )

        class _FileProxy:
            __slots__ = ("name",)
            def __init__(self, path: str):
                self.name = path

        file_proxies = [_FileProxy(p) for p in saved_paths]
        detected = detect_files(file_proxies)
        people, path_map = build_people_index(saved_paths, manual_name=manual_person_name or None)

        # Build response
        files_by_type = detected.get("files_by_type", {})

        def _basenames(paths: list) -> list[str]:
            return [os.path.basename(str(p)) for p in paths]

        def _pdf_basenames(key: str) -> list[str]:
            items = files_by_type.get(key) or []
            return [os.path.basename(getattr(f, "name", str(f))) for f in items]

        pdf_groups = PdfFileGroups(
            dental=_pdf_basenames("dental"),
            postural=_pdf_basenames("postural"),
            baropodometry=_pdf_basenames("baropodometry"),
            dynamic_baropodometry=_pdf_basenames("dynamic_baropodometry"),
            spine3d=_pdf_basenames("spine3d"),
        )
        csv_groups = CsvFileGroups(
            cervical_goniometry=_basenames(detected.get("csv_goniometry_paths") or []),
            leg_dynamometry=_basenames(detected.get("csv_leg_dynamometry_paths") or []),
            leg_goniometry=_basenames(detected.get("csv_leg_goniometry_paths") or []),
            arm_goniometry=_basenames(detected.get("csv_arm_goniometry_paths") or []),
            arm_dynamometry=_basenames(detected.get("csv_arm_dynamometry_paths") or []),
            single_leg_balance=_basenames(detected.get("csv_single_leg_balance_paths") or []),
            single_leg_landing=_basenames(detected.get("csv_single_leg_landing_paths") or []),
            mccall_hamstrings=_basenames(detected.get("csv_mccall_paths") or []),
            shoulder_test=_basenames(detected.get("csv_shoulder_paths") or []),
            push_up=_basenames(detected.get("csv_push_up_paths") or []),
            handstand_push_up=_basenames(detected.get("csv_handstand_push_up_paths") or []),
            counter_movement_jump=_basenames(detected.get("csv_counter_movement_jump_paths") or []),
            single_leg_counter_movement_jump=_basenames(detected.get("csv_single_leg_counter_movement_jump_paths") or []),
            drop_jump=_basenames(detected.get("csv_drop_jump_paths") or []),
            imtp=_basenames(detected.get("csv_imtp_paths") or []),
            bipodal_stance=_basenames(detected.get("csv_bipodal_stance_paths") or []),
            bipodal_landing=_basenames(detected.get("csv_bipodal_landing_paths") or []),
            skipping=_basenames(detected.get("csv_skipping_paths") or []),
            squats_advanced_analysis=_basenames(detected.get("csv_squats_advanced_analysis_paths") or []),
        )

        # Count recognized vs unknown
        recognized_basenames: set[str] = set()
        for lst in [
            pdf_groups.dental, pdf_groups.postural, pdf_groups.baropodometry,
            pdf_groups.dynamic_baropodometry, pdf_groups.spine3d,
            csv_groups.cervical_goniometry, csv_groups.leg_dynamometry,
            csv_groups.leg_goniometry, csv_groups.arm_goniometry, csv_groups.arm_dynamometry,
            csv_groups.single_leg_balance, csv_groups.single_leg_landing,
            csv_groups.mccall_hamstrings, csv_groups.shoulder_test,
            csv_groups.push_up, csv_groups.handstand_push_up,
            csv_groups.counter_movement_jump, csv_groups.single_leg_counter_movement_jump,
            csv_groups.drop_jump, csv_groups.imtp, csv_groups.bipodal_stance,
            csv_groups.bipodal_landing, csv_groups.skipping, csv_groups.squats_advanced_analysis,
        ]:
            recognized_basenames.update(lst)

        all_basenames = [os.path.basename(p) for p in saved_paths]
        unknown = [b for b in all_basenames if b not in recognized_basenames]
        recognized_count = len(recognized_basenames.intersection(set(all_basenames)))

        detected_people = [
            PersonGuessResponse(
                key=p.key,
                display=p.display,
                surname=p.surname,
                name=p.name,
                source=p.source,
            )
            for p in people
            if p.key != UNKNOWN_PERSON_KEY
        ]

        file_assignments: dict[str, str] = {
            os.path.basename(path): guess.key
            for path, guess in path_map.items()
            if guess.key != UNKNOWN_PERSON_KEY
        }

        return DetectFilesResponse(
            detected_people=detected_people,
            file_groups=FileGroups(pdf=pdf_groups, csv=csv_groups, unknown=unknown),
            file_assignments=file_assignments,
            total_files=len(saved_paths),
            recognized_files=recognized_count,
            unrecognized_files=len(unknown),
        )
