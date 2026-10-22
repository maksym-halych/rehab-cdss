"""Deterministic synthetic provider responses; never use for clinical decisions."""

from types import SimpleNamespace

from module_2_reasoning import schemas


IDENTITY = {
    "name": "Марко Тестовий Синтетичний",
    "patient_code": "PRIVATE-PATIENT-4829",
    "birth_date": "1990-04-12",
    "email": "synthetic.person@example.org",
    "phone": "+380 (50) 123-45-67",
    "address": "PRIVATE_ADDRESS_4829",
    "external_reference": "PRIVATE_REFERENCE_4829",
}


PROTOCOL_HIT = {
    "id": "synthetic-knee-0",
    "document": "Synthetic Knee extension protocol for testing only.",
    "metadata": {
        "parent_id": "synthetic-knee",
        "doc_type": "Guideline_General",
        "primary_body_parts": ["Knee"],
        "section_title": "Demo phase",
    },
    "distance": 0.1,
}
EXERCISE_HIT = {
    "id": "synthetic-exercise",
    "document": "Synthetic instructions. Do not use for treatment.",
    "metadata": {"canonical_name": "Knee extension", "is_high_impact": False},
    "distance": 0.1,
}


class FakeLLM:
    def __init__(self, **kwargs):
        self.calls = []

    def with_structured_output(self, schema):
        if isinstance(schema, dict):
            schema = getattr(schemas, schema["title"])
        return SimpleNamespace(invoke=lambda prompt: self.respond(schema, prompt))

    def respond(self, schema, prompt):
        self.calls.append((schema.__name__, prompt))
        query = {"body_part": "Knee", "keywords": "synthetic knee extension"}
        exercise = {
            "raw_name_from_protocol": "Knee extension",
            "source_protocol_id": "synthetic-knee",
            "source_section_title": "Demo phase",
        }
        report_exercise = {
            "exercise_name": "Knee extension",
            "patient_instructions": EXERCISE_HIT["document"],
            "clinical_rationale": "Synthetic test rationale",
            "source_protocol_id": "synthetic-knee",
            "source_section_title": "Demo phase",
        }
        phase = {
            "phase_title": "Demo phase",
            "phase_goals": ["Synthetic goal"],
            "clinical_interventions": [],
            "phase_precautions": ["Demo only"],
            "progression_criteria": ["Synthetic criterion"],
        }
        responses = {
            schemas.ClinicalSummary: {
                "thought_process": "Test fixture",
                "patient_context": "Synthetic adult",
                "findings": ["Synthetic strength finding"],
                "key_concerns": ["Synthetic concern"],
                "full_patient_summary": "Synthetic adult with simulated strength measurements.",
            },
            schemas.ProtocolQueryList: {"queries": [query]},
            schemas.RewrittenQueries: {
                "thought_process": "Test fixture",
                "queries": [query],
            },
            schemas.GraderOutput: {
                "thought_process": "Test fixture",
                "evaluations": [{"protocol_id": "synthetic-knee", "is_relevant": True}],
            },
            schemas.DraftTreatmentPlan: {
                "thought_process": "Test fixture",
                "precaution_analysis": [],
                "global_precautions": ["Demo only"],
                "phases": [{**phase, "prescribed_exercises": [exercise]}],
            },
        }
        if schema in (
            schemas.EnglishRehabilitationReport,
            schemas.RehabilitationReport,
        ):
            return schema.model_validate(
                {
                    "thought_process": "Test fixture",
                    "report_title": "Synthetic demo report",
                    "patient_context": "Synthetic adult",
                    "clinical_findings": ["Synthetic finding"],
                    "key_concerns": ["Synthetic concern"],
                    "global_precautions": ["Demo only"],
                    "phases": [{**phase, "exercises": [report_exercise]}],
                    "summary_recommendations": "Test output only. Do not use for treatment.",
                }
            )
        return schema.model_validate(responses[schema])
