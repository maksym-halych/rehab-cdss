"""Local, per-run de-identification for patient data sent outside Module 2.

Identity values never enter graph state, provider metadata or persistent mappings.
See docs/adr/ADR-05-llm-privacy.md for the boundary and free-text limitations.
"""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import math
import logging
import re
import unicodedata
from typing import Any

from langsmith import tracing_context
from langchain_core.globals import get_debug, get_verbose
from pydantic import BaseModel


REMOVED = "[REDACTED]"  # One constant, never a person-specific pseudonym.


class PrivacyError(ValueError):
    """A safe error message that does not contain input values."""


def _normalise(text: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKC", text)
        if unicodedata.category(char) != "Cf"
    )


def _key(text: str) -> str:
    return re.sub(r"[\W_]", "", _normalise(text).casefold())


_IDENTITY_KEYS = {
    "name",
    "fullname",
    "firstname",
    "lastname",
    "middlename",
    "surname",
    "patronymic",
    "patientname",
    "personname",
    "manualpersonname",
    "піб",
    "прізвище",
    "імя",
    "побатькові",
    "фио",
    "фамилия",
    "имя",
    "id",
    "patientid",
    "personid",
    "patientcode",
    "personkey",
    "selectedpersonkey",
    "localid",
    "medicalrecordnumber",
    "mrn",
    "recordid",
    "externalid",
    "externalreference",
    "birthdate",
    "dateofbirth",
    "dob",
    "birthday",
    "датанародження",
    "датарождения",
    "email",
    "emailaddress",
    "phone",
    "phonenumber",
    "telephone",
    "mobile",
    "address",
    "homeaddress",
    "адреса",
    "телефон",
    "passport",
    "passportnumber",
    "ssn",
    "taxid",
    "insuranceid",
    "filename",
    "filepath",
    "sourcefile",
    "sourcefilename",
}
_NAME_KEYS = {
    "name",
    "fullname",
    "firstname",
    "lastname",
    "middlename",
    "surname",
    "patronymic",
    "patientname",
    "personname",
    "manualpersonname",
    "піб",
    "прізвище",
    "імя",
    "побатькові",
    "фио",
    "фамилия",
    "имя",
}

# Defence in depth for identifiers repeated in clinical free text or model output.
_PATTERNS = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"[\w.+-]+@[\w.-]+\.[a-z\u0400-\u04ff]{2,}",
        r"https?://[^\s<>\"']+",
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        r"(?<!\d)(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])(?!\d)",
        r"(?<!\d)(?:0?[1-9]|[12]\d|3[01])[-/.](?:0?[1-9]|1[0-2])[-/.](?:19|20)\d{2}(?!\d)",
        r"(?<!\w)\+?\d(?:[ ()-]*\d){9,}(?!\w)",
        r"\b(?:sk-[a-z0-9_-]{12,}|gh[pousr]_[a-z0-9]{20,})\b",
        r"\b(?:patient[_ ]?(?:id|code|name)|person[_ ]?(?:id|name)|local[_ ]?id|"
        r"full[_ ]?name|first[_ ]?name|last[_ ]?name|date[_ ]?of[_ ]?birth|birth[_ ]?date|"
        r"dob|mrn|passport|address|email|phone|telephone|піб|прізвище|ім['’]?я|дата\s+народження|"
        r"код\s+пацієнта|адреса|телефон)\s*[=:]\s*[^\n\r;|<>]+",
    )
)


def _scalars(value: Any):
    if isinstance(value, dict):
        for child in value.values():
            yield from _scalars(child)
    elif isinstance(value, list):
        for child in value:
            yield from _scalars(child)
    elif isinstance(value, (str, int, float)) and not isinstance(value, bool):
        yield str(value)


@dataclass(frozen=True, repr=False)
class PrivacyGuard:
    _identifiers: tuple[re.Pattern, ...] = field(default=(), repr=False)

    @classmethod
    def from_patient(cls, *sources: dict) -> PrivacyGuard:
        tokens: set[str] = set()

        def collect(value):
            if isinstance(value, dict):
                for key, child in value.items():
                    normal_key = _key(str(key))
                    if normal_key in _IDENTITY_KEYS:
                        for scalar in _scalars(child):
                            scalar = _normalise(scalar).strip()
                            if scalar:
                                tokens.add(scalar)
                                if normal_key in _NAME_KEYS:
                                    tokens.update(re.findall(r"[^\W\d_]{2,}", scalar))
                    collect(child)
            elif isinstance(value, list):
                for child in value:
                    collect(child)

        for source in sources:
            collect(source)
        expressions = []
        for token in sorted(tokens, key=len, reverse=True):
            # A short number alone is ambiguous with measurements and dosages.
            # Identity fields stay excluded; labelled IDs are still scrubbed.
            if token.isdigit() and len(token) < 5:
                continue
            # Whitespace variants are common in copied names and clinical notes.
            expression = r"\s+".join(re.escape(part) for part in token.split())
            expressions.append(re.compile(r"(?<!\w)" + expression + r"(?!\w)", re.I))
        return cls(tuple(expressions))

    def text(self, value: str) -> str:
        text = _normalise(value)
        for expression in self._identifiers:
            text = expression.sub(REMOVED, text)
        for expression in _PATTERNS:
            text = expression.sub(REMOVED, text)
        return text

    def clean(self, value: Any) -> Any:
        """Copy nested data; sanitize strings without mutating local source data."""
        if isinstance(value, BaseModel):
            return type(value).model_validate(self.clean(value.model_dump()))
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, dict):
            return {
                self.text(str(key)): self.clean(child) for key, child in value.items()
            }
        if isinstance(value, (list, tuple)):
            return [self.clean(child) for child in value]
        return value

    def patient_context(self, info: dict) -> dict:
        if not isinstance(info, dict):
            raise PrivacyError("Invalid patient context.")
        age = info.get("age")
        if age is not None and (type(age) is not int or not 0 <= age <= 120):
            raise PrivacyError("Patient age must be an integer between 0 and 120.")
        gender = str(info.get("gender") or "unknown").strip().casefold()
        genders = {
            "male": "male",
            "female": "female",
            "чоловік": "male",
            "чоловіча": "male",
            "жінка": "female",
            "жіноча": "female",
            "unknown": "unknown",
            "other": "other",
        }
        activity = str(info.get("activity_level") or "unknown").strip().casefold()
        if gender not in genders or activity not in {
            "elite",
            "recreational",
            "low",
            "unknown",
        }:
            raise PrivacyError(
                "Unsupported gender or activity level in patient context."
            )
        return {"age": age, "gender": genders[gender], "activity_level": activity}

    def patient_export(self, source: dict, info: dict) -> dict:
        """Allow only the fields consumed by the clinical filter.

        Unknown metadata, file paths, IDs and additional patient fields stay local.
        Numeric fields must be numbers; labels and clinical narratives are scrubbed.
        """
        tests = source.get("test_results", [])
        if not isinstance(tests, list):
            raise PrivacyError("Invalid test results.")
        safe_tests = []
        for test in tests:
            if not isinstance(test, dict):
                raise PrivacyError("Invalid test result.")
            safe = {
                key: self._clinical_text(test.get(key))
                for key in ("test_name", "interpretation", "recommendations")
            }
            safe["test_name"] = safe["test_name"] or "unknown"
            tables = []
            for table in test.get("results", {}).get("tables", []):
                rows = []
                for row in table.get("rows", []):
                    safe_row = {
                        key: self._clinical_text(row.get(key))
                        for key in ("parameter", "unit")
                    }
                    safe_row["parameter"] = safe_row["parameter"] or "unknown"
                    for key in (
                        "value",
                        "left",
                        "right",
                        "asymmetry_percent",
                        "asymmetry_norm_max",
                        "norm",
                    ):
                        if key in row:
                            safe_row[key] = _measurement(
                                row[key], allow_list=key == "norm"
                            )
                    rows.append(safe_row)
                tables.append({"rows": rows})
            safe["results"] = {"tables": tables}
            safe_tests.append(safe)
        return {"patient_info": self.patient_context(info), "test_results": safe_tests}

    def _clinical_text(self, value):
        if value is not None and not isinstance(value, str):
            raise PrivacyError("Clinical text must be a string or null.")
        return self.text(value) if value else None


def _measurement(value, *, allow_list=False):
    if value is None:
        return None
    if allow_list and isinstance(value, list):
        return [_measurement(item) for item in value]
    if type(value) not in (int, float) or not math.isfinite(value):
        raise PrivacyError("Clinical measurements must be finite numbers.")
    return value


_ACTIVE_GUARD: ContextVar[PrivacyGuard | None] = ContextVar(
    "patient_privacy", default=None
)


def active_guard() -> PrivacyGuard:
    guard = _ACTIVE_GUARD.get()
    if guard is None:
        raise PrivacyError(
            "A patient privacy context is required before an external request."
        )
    return guard


@contextmanager
def privacy_scope(guard: PrivacyGuard):
    # SDK debug output can include raw provider error bodies before our handler.
    # Refuse this configuration instead of changing process-wide logging levels.
    provider_names = {"openai", "openai._base_client", "httpx", "httpcore"}
    provider_names.update(
        name
        for name in tuple(logging.Logger.manager.loggerDict)
        if name.startswith(("openai.", "httpx.", "httpcore."))
    )
    if any(
        logging.getLogger(name).isEnabledFor(logging.DEBUG) for name in provider_names
    ):
        raise PrivacyError(
            "Provider debug logging must be disabled for patient processing."
        )
    token = _ACTIVE_GUARD.set(guard)
    try:
        # Disable remote tracing even if enabled in the deployment environment.
        with tracing_context(enabled=False, parent=False):
            yield
    finally:
        _ACTIVE_GUARD.reset(token)


class PrivatePipeline:
    """Sanitize before LangGraph sees input; isolate identities between jobs."""

    def __init__(self, graph):
        self._graph = graph

    def invoke(self, initial_state: dict, config: dict | None = None):
        if get_debug() or get_verbose():
            raise PrivacyError("Patient processing does not permit debug output.")
        try:
            source = initial_state.get("module1_data", {})
            info = initial_state.get("patient_info", source.get("patient_info", {}))
            guard = PrivacyGuard.from_patient(source, {"patient_info": info})
            with privacy_scope(guard):
                safe_source = guard.patient_export(source, info)
                safe_state = {
                    "module1_data": safe_source,
                    "patient_info": safe_source["patient_info"],
                    "retries": 0,
                    "grader_feedback": [],
                }
                # No caller-supplied callbacks, run names or metadata with identities.
                safe_config = {"callbacks": []}
                if config and "recursion_limit" in config:
                    safe_config["recursion_limit"] = config["recursion_limit"]
                return guard.clean(self._graph.invoke(safe_state, config=safe_config))
        except PrivacyError:
            raise
        except Exception:
            # Provider/validation/IO errors can contain requests, outputs or paths.
            raise PrivacyError(
                "Module 2 could not complete the de-identified request."
            ) from None
