from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
import logging
from threading import Barrier
from unittest.mock import Mock

import httpx
import openai
from langchain_openai import ChatOpenAI
from langsmith.run_helpers import get_tracing_context
import pytest

from fakes import IDENTITY, FakeLLM
from module_2_reasoning import _retry, retrieval, schemas
from module_2_reasoning.privacy import (
    PrivacyError,
    PrivacyGuard,
    REMOVED,
    active_guard,
    privacy_scope,
)
from module_2_reasoning.schemas import ClinicalSummary
from module_2_reasoning.summarizer import summarize


def assert_no_identity(value):
    serialised = json.dumps(value, ensure_ascii=False, default=str)
    for token in (*IDENTITY.values(), "Марко", "Тестовий", "Синтетичний", "12.04.1990"):
        assert token not in serialised


def test_export_allowlist_keeps_measurements_and_does_not_mutate_input(
    identified_patient,
):
    original = deepcopy(identified_patient)
    guard = PrivacyGuard.from_patient(identified_patient)
    clean = guard.patient_export(identified_patient, identified_patient["patient_info"])
    assert_no_identity(clean)
    assert set(clean) == {"patient_info", "test_results"}
    assert clean["patient_info"] == {
        "age": 30,
        "gender": "male",
        "activity_level": "recreational",
    }
    row = clean["test_results"][0]["results"]["tables"][0]["rows"][0]
    assert (row["left"], row["right"], row["norm"], row["asymmetry_percent"]) == (
        12,
        20,
        [15, 25],
        40,
    )
    assert "40%" in clean["test_results"][0]["interpretation"]
    assert identified_patient == original
    assert_no_identity(repr(guard))


def test_known_identity_is_removed_case_insensitively_and_after_unicode_normalisation():
    guard = PrivacyGuard.from_patient(
        {"patient_info": {"fullName": "Ірина Тестенко", "patientId": "ABC-123"}}
    )
    assert guard.text("ІРИНА\u200b   ТЕСТЕНКО abc-123") == REMOVED + " " + REMOVED
    assert guard.text("Тестенко, Ірина: 30 kg") == f"{REMOVED}, {REMOVED}: 30 kg"


@pytest.mark.parametrize("code", [7, "12", "1234", "１２"])
def test_short_numeric_identity_preserves_summary_measurements_and_report(code):
    guard = PrivacyGuard.from_patient({"patient_info": {"patient_code": code}})
    clinical_text = "Phase 1: 3 x 12 reps; 0.7 kg; 1234 steps"
    filtered = schemas.FilteredTestResult(
        test_name="Strength",
        flagged_params=[
            schemas.FlaggedParameter(
                parameter="Force",
                left=12,
                right=20,
                unit="kg",
                norm=[15, 25],
                flag_reason="below_norm",
            )
        ],
        interpretation_uk=clinical_text,
        has_norm_data=True,
    )

    class ClinicalLLM(FakeLLM):
        def respond(self, schema, prompt):
            result = super().respond(schema, prompt)
            result.full_patient_summary = clinical_text
            return result

    llm = ClinicalLLM()
    with privacy_scope(guard):
        result = summarize([filtered], {"age": 30, "gender": "male"}, llm)
    prompt = llm.calls[0][1]
    data = json.loads(
        prompt.rsplit("<filtered_data>", 1)[1].split("</filtered_data>")[0]
    )
    assert data == [filtered.model_dump()]
    assert result.full_patient_summary == clinical_text
    assert guard.text(f"patient_code={code}; {clinical_text}") == (
        f"{REMOVED}; {clinical_text}"
    )


def test_long_numeric_identity_is_still_removed():
    guard = PrivacyGuard.from_patient({"patient_code": "12345"})
    assert guard.text("Record 12345; 12 kg") == f"Record {REMOVED}; 12 kg"


def test_unknown_patient_fields_do_not_become_identity_tokens(synthetic_patient):
    info = synthetic_patient["patient_info"]
    info.update(dominant_side="right", height=180, diagnosis="knee pain")
    guard = PrivacyGuard.from_patient(synthetic_patient)
    clinical = {"right": 20, "interpretation": "knee pain; ROM 180 deg"}
    assert guard.clean(clinical) == clinical
    exported = guard.patient_export(synthetic_patient, info)
    assert set(exported["patient_info"]) == {"age", "gender", "activity_level"}


@pytest.mark.parametrize("text", ["ROM 100 - 120 - 140 deg", "sets 10-15-20-25"])
def test_clinical_ranges_are_not_mistaken_for_phone_numbers(text):
    assert PrivacyGuard().text(text) == text


@pytest.mark.parametrize(
    "text",
    [
        "new.person@example.org",
        "+380501234567",
        "+380 (50) 123-45-67",
        "050 123 45 67",
        "2001-05-06",
        "06/05/2001",
        "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "https://example.org/patient/42",
        "ПІБ: Новий Синтетичний;",
        "patient_id=PRIVATE_UNREGISTERED;",
    ],
)
def test_unregistered_identifier_patterns_are_removed(text):
    assert PrivacyGuard().text(text).rstrip(";") == REMOVED


@pytest.mark.parametrize(
    "info",
    [
        {"age": "PRIVATE_SENTINEL"},
        {"age": True},
        {"age": 121},
        {"gender": "PRIVATE_SENTINEL"},
        {"activity_level": "PRIVATE_SENTINEL"},
    ],
)
def test_identity_cannot_be_smuggled_through_demographic_fields(info):
    with pytest.raises(PrivacyError) as error:
        PrivacyGuard().patient_context(info)
    assert "PRIVATE_SENTINEL" not in str(error.value)


@pytest.mark.parametrize(
    "value", ["PRIVATE_SENTINEL", {"name": "PRIVATE_SENTINEL"}, float("nan"), True]
)
def test_measurements_do_not_accept_untyped_payloads(synthetic_patient, value):
    synthetic_patient["test_results"][0]["results"]["tables"][0]["rows"][0]["left"] = (
        value
    )
    with pytest.raises(PrivacyError) as error:
        PrivacyGuard().patient_export(
            synthetic_patient, synthetic_patient["patient_info"]
        )
    assert "PRIVATE_SENTINEL" not in str(error.value)


def test_missing_context_fails_before_provider_or_embedding_lookup(monkeypatch):
    llm = FakeLLM()
    lookup = Mock(side_effect=AssertionError("Must not open database"))
    monkeypatch.setattr(retrieval, "get_collections", lookup)
    with pytest.raises(PrivacyError):
        _retry.invoke_structured(llm, ClinicalSummary, "clinical data")
    with pytest.raises(PrivacyError):
        retrieval.search_protocols("clinical query")
    assert llm.calls == []
    lookup.assert_not_called()


def test_both_embedding_query_paths_use_the_active_guard(
    monkeypatch, identified_patient
):
    protocols, exercises = Mock(), Mock()
    empty = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]]}
    protocols.query.return_value = exercises.query.return_value = empty
    monkeypatch.setattr(retrieval, "get_collections", lambda: (protocols, exercises))
    guard = PrivacyGuard.from_patient(identified_patient)
    with privacy_scope(guard):
        query = IDENTITY["name"] + " knee strengthening " + IDENTITY["email"]
        retrieval.search_protocols(query)
        retrieval.search_exercises(query)
    for collection in (protocols, exercises):
        query_texts = collection.query.call_args.kwargs["query_texts"]
        assert_no_identity(query_texts)
        assert "knee strengthening" in query_texts[0]


def _response(content):
    return httpx.Response(
        200,
        json={
            "id": "synthetic-response",
            "object": "chat.completion",
            "created": 1,
            "model": "gpt-4.1-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": json.dumps(content)},
                    "finish_reason": "stop",
                }
            ],
        },
    )


@pytest.mark.parametrize(
    "schema",
    [
        schemas.ClinicalSummary,
        schemas.ProtocolQueryList,
        schemas.GraderOutput,
        schemas.RewrittenQueries,
        schemas.DraftTreatmentPlan,
        schemas.EnglishRehabilitationReport,
        schemas.RehabilitationReport,
    ],
)
def test_guarded_requests_preserve_the_original_strict_response_format(schema):
    payloads = []
    response = FakeLLM().respond(schema, "").model_dump()

    def transport(request):
        payloads.append(json.loads(request.content))
        if len(payloads) == 1:
            # Capture the old request without invoking its unsafe response parser.
            return httpx.Response(400, json={"error": {"message": "Synthetic stop"}})
        return _response(response)

    with httpx.Client(transport=httpx.MockTransport(transport)) as http:
        llm = ChatOpenAI(
            model="gpt-4.1-mini",
            api_key="synthetic-key",
            max_retries=0,
            http_client=http,
        )
        with pytest.raises(openai.BadRequestError):
            llm.with_structured_output(schema).invoke("Synthetic clinical data")
        with privacy_scope(PrivacyGuard()):
            result = _retry.invoke_structured(llm, schema, "Synthetic clinical data")
    assert result.model_dump() == response
    assert len(payloads) == 2
    assert payloads[1]["response_format"] == payloads[0]["response_format"]
    assert payloads[1]["response_format"]["json_schema"]["strict"] is True


@pytest.mark.parametrize("status_code", [429, 500])
def test_actual_http_payloads_are_clean_on_retry_and_fallback(
    monkeypatch,
    capsys,
    caplog,
    identified_patient,
    status_code,
):
    payloads, tracing = [], []
    response = FakeLLM().respond(ClinicalSummary, "").model_dump()
    response["patient_context"] = "Age 30. " + IDENTITY["name"]
    calls = 0

    def transport(request):
        nonlocal calls
        calls += 1
        payloads.append(json.loads(request.content))
        tracing.append(get_tracing_context()["enabled"])
        if calls == 1:
            return httpx.Response(
                status_code,
                json={
                    "error": {
                        "message": IDENTITY["name"] + IDENTITY["patient_code"],
                        "type": "synthetic_error",
                        "code": "synthetic_error",
                    }
                },
            )
        return _response(response)

    monkeypatch.setattr(_retry.time, "sleep", lambda _: None)
    monkeypatch.setenv("LANGSMITH_TRACING", "true")
    guard = PrivacyGuard.from_patient(identified_patient)
    with httpx.Client(transport=httpx.MockTransport(transport)) as http:
        llm = ChatOpenAI(
            model="gpt-4.1-mini",
            api_key="synthetic-key",
            max_retries=0,
            http_client=http,
        )
        fallback = ChatOpenAI(
            model="gpt-4.1-mini",
            api_key="synthetic-fallback-key",
            max_retries=0,
            http_client=http,
        )
        with privacy_scope(guard):
            result = _retry.invoke_structured(
                llm,
                ClinicalSummary,
                "; ".join(IDENTITY.values()) + " Strength: 12 kg",
                fallback if status_code == 429 else None,
            )
    assert calls == 2
    assert payloads[0]["response_format"] == payloads[1]["response_format"]
    assert payloads[0]["response_format"]["json_schema"]["strict"] is True
    assert tracing == [False, False]
    assert_no_identity(payloads)
    assert_no_identity(result.model_dump())
    assert "12 kg" in payloads[0]["messages"][0]["content"]
    assert_no_identity(capsys.readouterr().out + caplog.text)


def test_provider_validation_errors_do_not_expose_body_or_secret(capsys):
    llm = Mock()
    llm.callbacks = None
    llm.verbose = False
    llm.with_structured_output.return_value.invoke.side_effect = RuntimeError(
        "PRIVATE_SENTINEL synthetic-secret"
    )
    with privacy_scope(PrivacyGuard()), pytest.raises(PrivacyError) as error:
        _retry.invoke_structured(llm, ClinicalSummary, "clinical data")
    assert "PRIVATE_SENTINEL" not in str(error.value)
    assert "synthetic-secret" not in capsys.readouterr().out


def test_parallel_jobs_have_separate_identity_contexts():
    barrier = Barrier(2)

    def run(name, other):
        with privacy_scope(PrivacyGuard.from_patient({"name": name})):
            barrier.wait(timeout=5)
            assert active_guard().text(name) == REMOVED
            assert active_guard().text(other) == other
        with pytest.raises(PrivacyError):
            active_guard()

    with ThreadPoolExecutor(max_workers=2) as executor:
        a = executor.submit(run, "SYNTHETIC_ALPHA", "SYNTHETIC_BETA")
        b = executor.submit(run, "SYNTHETIC_BETA", "SYNTHETIC_ALPHA")
        a.result(timeout=10)
        b.result(timeout=10)


def test_provider_debug_logging_fails_closed(caplog):
    caplog.set_level(logging.DEBUG, logger="openai._base_client")
    with pytest.raises(PrivacyError, match="debug logging"):
        with privacy_scope(PrivacyGuard()):
            pytest.fail("Provider must not run while debug logging can expose payloads")
    with pytest.raises(PrivacyError):
        active_guard()
