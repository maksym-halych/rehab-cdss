from typing import Any

from pydantic import BaseModel

from module_1_aggregation.schemas import (
    Module1Output,
    PatientInfo,
    ResultRow,
    ResultsTable,
    TestResult,
    TestResults,
)

__all__ = [
    "Module1Output",
    "PatientInfo",
    "TestResult",
    "TestResults",
    "ResultRow",
    "ResultsTable",
    "ErrorDetail",
    "ErrorResponse",
]


class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: Any = None


class ErrorResponse(BaseModel):
    error: ErrorDetail
