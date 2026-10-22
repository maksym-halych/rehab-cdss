import os
import shutil
from pathlib import Path

import aiofiles
from fastapi import UploadFile
from module_2_reasoning.paths import DATA_DIR

TEMP_ROOT = Path("temp_files")
REPORTS_ROOT = DATA_DIR / "reports"

ALLOWED_EXTENSIONS = frozenset([".pdf", ".csv"])
MAX_FILE_SIZE_BYTES = int(os.getenv("CDSS_MAX_FILE_SIZE_MB", "60")) * 1024 * 1024
MAX_FILES_PER_JOB = int(os.getenv("CDSS_MAX_FILES_PER_JOB", "120"))


async def save_uploads(job_id: str, files: list[UploadFile]) -> list[Path]:
    if len(files) > MAX_FILES_PER_JOB:
        raise ValueError(f"Too many files: {len(files)} > {MAX_FILES_PER_JOB}")

    run_dir = TEMP_ROOT / job_id
    run_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported file type: {upload.filename}")

        # Sanitize filename: use only basename to prevent directory traversal
        safe_name = os.path.basename(upload.filename or "upload")
        dest = run_dir / safe_name
        total = 0
        async with aiofiles.open(dest, "wb") as f:
            while chunk := await upload.read(65536):
                total += len(chunk)
                if total > MAX_FILE_SIZE_BYTES:
                    raise ValueError(f"File too large: {upload.filename}")
                await f.write(chunk)
        paths.append(dest)

    return paths


async def cleanup_run_dir(job_id: str) -> None:
    run_dir = TEMP_ROOT / job_id
    if run_dir.exists():
        shutil.rmtree(run_dir, ignore_errors=True)
