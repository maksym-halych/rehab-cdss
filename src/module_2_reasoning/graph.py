"""
LangGraph pipeline for Module 2 — Clinical Reasoning (Agentic RAG).

Graph topology (9 nodes):
    START → filter_node → summarize_node → query_generator_node → protocol_retriever_node
        → grader_node → [relevant_protocols > 0 OR retries >= 2] → reasoner_node → exercise_mapper_node → report_formatter_node → END
                       → [no relevant protocols, retries < 2] → query_rewriter_node → protocol_retriever_node (loop)

Usage:
    from module_2_reasoning.graph import build_pipeline
    pipeline = build_pipeline(llm)
    final_state = pipeline.invoke(initial_state)
"""

from __future__ import annotations

from typing import Any

from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from rapidfuzz import fuzz

from module_2_reasoning.filter import filter_patient_data
from module_2_reasoning.retrieval import (
    body_parts_to_str,
    fetch_full_protocol,
    search_exercises,
    search_protocols,
)
from module_2_reasoning.schemas import (
    ClinicalSummary,
    DraftTreatmentPlan,
    GraderOutput,
    ProtocolQueryList,
    RewrittenQueries,
)
from module_2_reasoning.report_formatter import generate_english_report, translate_report, render_markdown
from module_2_reasoning.summarizer import summarize

from module_2_reasoning._retry import invoke_structured


class PipelineState(TypedDict):
    # inputs
    module1_data: dict
    patient_info: dict
    # node outputs
    filtered_results: list
    clinical_summary: Any  # ClinicalSummary | None
    protocol_queries: list
    full_protocols: list  # list of fetch_full_protocol() output dicts
    draft_plan: Any  # DraftTreatmentPlan | None
    enriched_plan: Any  # dict | None — final JSON with mapped exercise data
    english_report: Any  # EnglishRehabilitationReport | None
    final_report: Any  # str | None — rendered markdown report
    # --- Agentic RAG Fields ---
    retries: int
    grader_feedback: list[str]
    relevant_protocols: list


_ROUTE_REASONER = "reasoner"
_ROUTE_QUERY_REWRITER = "query_rewriter"

# NOTE: body_part list in QUERY_GEN_PROMPT MUST stay in sync with ProtocolQuery.body_part in schemas.py
QUERY_GEN_PROMPT = """\
You are an expert Medical Search Engineer. Your job is to translate complex clinical concerns into highly effective search queries for a Vector Database.
The database contains standard physical therapy protocols and exercise lists. 

PATIENT CONCERNS:
{key_concerns}

CRITICAL RULES FOR SEARCH QUERIES:
1. FOCUS ON INTERVENTIONS, NOT JUST DIAGNOSES: The database contains exercise protocols, not diagnostic manuals. 
   - BAD keyword: "quadriceps dominance anterior shift"
   - GOOD keyword: "hamstring and glute strengthening posterior chain"
   - BAD keyword: "cervical hypomobility"
   - GOOD keyword: "cervical stretching neck mobility exercises"

2. BE SIMPLE AND ATOMIC: Break down complex problems. 
   - If the patient has a 17% strength deficit in the right leg, the query should be: "knee flexion strengthening hip adduction exercises".

3. METADATA FILTERING RULES:
   - 'body_part': MUST be one of: Knee, Shoulder, Spine, Core_Pelvis, Hip, Foot_Ankle, Elbow, Wrist_Hand, Head_Neck_TMJ, General_Body_Multijoint.
     *Rule:* Use 'Core_Pelvis' for pelvic tilt, lower crossed syndrome, core stability. Use 'Head_Neck_TMJ' for TMJ, dental, cervical/neck issues. Use 'General_Body_Multijoint' ONLY for global/cardio/multijoint cases. If leg weakness, use 'Knee' or 'Hip'.
   - 'treatment_type': MUST be 'Non-Operative' UNLESS the patient explicitly had surgery. NEVER leave it null.

4. MULTI-QUERY STRATEGY: Generate 4 to 6 distinct queries to ensure all patient problems are covered. Ensure at least one query directly addresses specific muscle weakness if mentioned.

Output STRICT JSON matching the schema.
"""


def build_pipeline(
    llm: ChatOpenAI, *, fallback_llm: ChatOpenAI | None = None, on_step_start=None
):
    """Factory — returns a compiled LangGraph pipeline."""

    def _notify(step_name: str):
        if on_step_start is not None:
            on_step_start(step_name)

    def filter_node(state: PipelineState) -> dict:
        _notify("filter")
        print("\n[Step 1] Running filter_node...")
        filtered = filter_patient_data(state["module1_data"])
        flagged_count = sum(len(fr.flagged_params) for fr in filtered)
        print(
            f"  {len(filtered)} test(s) processed, {flagged_count} flagged parameter(s) total"
        )
        return {"filtered_results": filtered}

    def summarize_node(state: PipelineState) -> dict:
        _notify("summarize")
        print("\n[Step 2] Running summarize_node (LLM)...")
        summary = summarize(
            state["filtered_results"],
            state["patient_info"],
            llm,
            fallback_llm=fallback_llm,
        )
        return {"clinical_summary": summary}

    def query_generator_node(state: PipelineState) -> dict:
        _notify("query_generator")
        print("\n[Step 3] Running query_generator_node (LLM)...")
        summary: ClinicalSummary = state["clinical_summary"]
        key_concerns_text = "\n".join(f"- {c}" for c in summary.key_concerns)
        prompt = QUERY_GEN_PROMPT.format(key_concerns=key_concerns_text)
        result = invoke_structured(llm, ProtocolQueryList, prompt, fallback_llm)
        print(f"  Generated {len(result.queries)} query/queries:")
        for q in result.queries:
            print(f"    [{q.body_part}] {q.keywords}")
        return {"protocol_queries": result.queries}

    def protocol_retriever_node(state: PipelineState) -> dict:
        _notify("protocol_retriever")
        print("\n[Step 4] Running protocol_retriever_node...")
        seen_ids: set[str] = set()
        results: list[dict] = []

        for query in state["protocol_queries"]:
            hits = search_protocols(
                query=query.keywords,
                n_results=5,
                body_part=query.body_part,
                treatment_type=query.treatment_type,
            )
            for hit in hits:
                if hit["id"] not in seen_ids:
                    seen_ids.add(hit["id"])
                    results.append(hit)

        print(f"  Retrieved {len(results)} unique protocol section(s)")

        # Conditional parent retrieval by doc_type
        full_protocols: list[dict] = []
        seen_parents_phased: set[str] = set()

        for hit in results:
            meta = hit["metadata"]
            doc_type = meta.get("doc_type", "")

            if doc_type == "Protocol_Phased":
                parent_id = meta.get("parent_id")
                if parent_id and parent_id not in seen_parents_phased:
                    seen_parents_phased.add(parent_id)
                    protocol = fetch_full_protocol(parent_id)
                    if protocol:
                        full_protocols.append(protocol)
            else:
                # Guideline_General, Test_Instruction, etc. — single-section protocol from hit
                parent_id = meta.get("parent_id", hit["id"])
                single_section = {
                    "id": hit["id"],
                    "section_title": meta.get("section_title", ""),
                    "section_index": meta.get("section_index", 0),
                    "goals": meta.get("goals", ""),
                    "precautions": meta.get("precautions", ""),
                    "progression_criteria": meta.get("progression_criteria", ""),
                    "document_context": hit.get("document", ""),
                }
                full_protocols.append(
                    {
                        "parent_id": parent_id,
                        "doc_type": meta.get("doc_type", ""),
                        "treatment_type": meta.get("treatment_type", "Unknown"),
                        "primary_body_parts": body_parts_to_str(
                            meta.get("primary_body_parts", "")
                        ),
                        "target_conditions": meta.get("target_conditions", ""),
                        "global_red_flags": meta.get("global_red_flags", ""),
                        "sections": [single_section],
                    }
                )

        total_sections = sum(len(p["sections"]) for p in full_protocols)
        print(
            f"  Fetched {len(full_protocols)} complete protocol(s) ({total_sections} section(s) total)"
        )
        return {"full_protocols": full_protocols}

    def reasoner_node(state: PipelineState) -> dict:
        _notify("reasoner")
        print("\n[Step 6] Running reasoner_node (LLM)...")
        clinical_summary: ClinicalSummary = state["clinical_summary"]
        full_protocols: list[dict] = state.get("relevant_protocols") or state.get(
            "full_protocols", []
        )

        # Build protocol context — strip IDs/distances, keep only useful fields
        protocol_blocks: list[str] = []
        for proto in full_protocols:
            header = (
                f"Protocol: {proto.get('parent_id', 'unknown')} | "
                f"Body: {proto.get('primary_body_parts', '')} | "
                f"Treatment: {proto.get('treatment_type', '')} | "
                f"Conditions: {proto.get('target_conditions', '')}\n"
                f"Global Red Flags: {proto.get('global_red_flags', 'None')}"
            )
            section_texts: list[str] = []
            for sec in proto.get("sections", []):
                section_texts.append(
                    f"  --- {sec.get('section_title', '')} ---\n"
                    f"  Goals: {sec.get('goals', '')}\n"
                    f"  Precautions: {sec.get('precautions', '')}\n"
                    f"  Progression Criteria: {sec.get('progression_criteria', '')}\n"
                    f"  Content:\n  {sec.get('document_context', '')}"
                )
            protocol_blocks.append(header + "\n" + "\n".join(section_texts))

        protocols_text = "\n\n===\n\n".join(protocol_blocks)

        prompt = (
            "You are an expert physiotherapist creating an individualized, phased treatment plan.\n\n"
            "PATIENT CLINICAL SUMMARY:\n"
            f"{clinical_summary.full_patient_summary}\n\n"
            "KEY CONCERNS:\n"
            + "\n".join(f"- {c}" for c in clinical_summary.key_concerns)
            + "\n\n"
            "RETRIEVED PROTOCOLS:\n"
            f"{protocols_text}\n\n"
            "INSTRUCTIONS:\n"
            "1. You may ONLY prescribe exercises that exist in the provided protocol texts. "
            "Do not invent new exercises.\n"
            "2. In `raw_name_from_protocol`, use the exact exercise name from the protocol. "
            "Strip dosages/modifiers and put them in `specifications`.\n"
            "3. TEMPORAL PHASING (CRITICAL): Summarize the plan into 3-5 unified temporal phases. "
            "Do not create micro-phases.\n"
            "   - Each phase represents a rehabilitation stage (e.g., 'Phase 1 — Acute / Protective', "
            "'Phase 2 — Intermediate / Strengthening', 'Phase 3 — Advanced / Return to Activity').\n"
            "   - For multi-region patients, each phase MUST include exercises for ALL body regions "
            "that are active during that time period.\n"
            "   - HANDLING ASYNCHRONOUS PROGRESSION: Different protocols may have different phase counts "
            "and timelines. To integrate them:\n"
            "     a) Align phases by CLINICAL STAGE (acute/protective, intermediate/strengthening, "
            "advanced/return-to-sport), not by protocol-specific phase numbering.\n"
            "     b) If one region progresses faster (e.g., shoulder is ready for advanced exercises "
            "while knee requires acute care), map the advanced shoulder exercises into the same "
            "chronological phase as the acute knee exercises, noting the body part in "
            "`clinical_rationale`.\n"
            "     c) If a region's protocol ends before another's, that region is simply NOT INCLUDED "
            "in later phases — remove it from `region_focus`. Do NOT invent maintenance exercises.\n"
            "     d) Populate `region_focus` with the body regions actively progressing in each phase.\n"
            "   - For single-region patients, this simplifies to standard phased rehab. "
            "Leave `region_focus` empty.\n"
            "4. Do NOT include body-region names in `phase_title`. Use temporal/functional names only.\n"
            "5. PRECAUTION FILTERING (CRITICAL): First DEDUPLICATE global_red_flags across all protocols "
            "— if the same precaution appears in multiple protocols, analyze it only once. "
            "Then populate `precaution_analysis` BEFORE writing `global_precautions`.\n"
            "   AGGREGATION: Merge semantically similar precautions into a single concise bullet. "
            "For example, multiple 'avoid joint mobilization when X/Y/Z' conditions (osteoarthritis, "
            "osteoporosis, infection, fracture, malignancy, etc.) → one aggregated point. "
            "Group by shared action or restriction.\n"
            "   CONCISENESS: Include only the most critical, high-impact precautions. "
            "Prioritize safety-critical restrictions. Keep the list short enough for quick "
            "clinical review — omit secondary or redundant guidance.\n"
            "   CATEGORY RULES:\n"
            "   - 'disease_specific': Precautions tied to a systemic disease or CNS condition "
            "(Stroke, Cancer, Meniere's, BPPV, Spinal Cord Injury, etc.). "
            "EXCLUDE unless the patient actually has that condition per the clinical summary.\n"
            "   - 'procedure_device_specific': Precautions tied to a surgical procedure, medical device, "
            "or specialized treatment modality (Canalith Repositioning, post-op corset, surgical drain, etc.). "
            "EXCLUDE unless the patient had that procedure or you are prescribing it.\n"
            "   - 'biomechanical': ROM limits, load restrictions, weight-bearing status, pain thresholds, "
            "impact restrictions, ergonomic advice, postural limits, prolonged sitting/standing warnings. "
            "ALWAYS RETAIN.\n"
            "   - FAIL-SAFE: If uncertain about a precaution's category, classify as 'biomechanical' to ensure retention.\n"
            "   `global_precautions` MUST contain ONLY entries where `is_applicable_to_patient` is True.\n"
            "6. Provide `clinical_rationale` personalized to THIS patient's clinical summary.\n"
            "7. Include `clinical_interventions` (modalities, manual therapy) from each phase.\n"
            "8. Begin with `thought_process` — your step-by-step reasoning.\n"
            "9. In `raw_name_from_protocol`, copy the exercise name EXACTLY as written in the "
            "[EXERCISES] block (keep prefixes like 'Alternating superman four point kneeling'). "
            "Do NOT paraphrase or abbreviate.\n"
            "10. Extract phase-specific precautions into `phase_precautions` for each phase.\n"
            "11. For multi-region plans, each entry in `progression_criteria` MUST begin with the "
            "region name in brackets (e.g., '[Knee]: full extension without pain').\n"
            "12. SOURCE TRACEABILITY (CRITICAL): For each exercise in `prescribed_exercises`, "
            "set `source_protocol_id` to the protocol's parent_id (shown as 'Protocol: xxx' "
            "in RETRIEVED PROTOCOLS above), and `source_section_title` to the exact section "
            "title (shown as '--- Section Title ---'). Every exercise MUST have both fields.\n"
        )

        draft_plan = invoke_structured(llm, DraftTreatmentPlan, prompt, fallback_llm)
        total_exercises = sum(len(p.prescribed_exercises) for p in draft_plan.phases)
        print(
            f"  Generated plan: {len(draft_plan.phases)} phase(s), "
            f"{total_exercises} exercise(s), "
            f"{len(draft_plan.global_precautions)} precaution(s)"
        )
        return {"draft_plan": draft_plan}

    def exercise_mapper_node(state: PipelineState) -> dict:
        _notify("exercise_mapper")
        print("\n[Step 6] Running exercise_mapper_node...")
        draft_plan: DraftTreatmentPlan = state["draft_plan"]
        FUZZY_THRESHOLD = 85
        STRICT_VECTOR_THRESHOLD = 0.40

        enriched_phases: list[dict] = []
        mapped_count = 0
        unmapped_count = 0

        for phase in draft_plan.phases:
            enriched_exercises: list[dict] = []
            for ex in phase.prescribed_exercises:
                ex_dict = ex.model_dump()
                hits = search_exercises(query=ex.raw_name_from_protocol, n_results=5)

                best_hit = None
                raw_lower = ex.raw_name_from_protocol.lower()
                # Rule A: Fuzzy bypass — find first hit with fuzzy score >= 85
                # Checks canonical_name and all aliases
                for hit in hits:
                    meta = hit["metadata"]
                    names_to_check = [meta.get("canonical_name", "")]
                    aliases_str = meta.get("aliases", "")
                    if aliases_str:
                        names_to_check.extend(
                            a.strip() for a in aliases_str.split(",") if a.strip()
                        )
                    for name in names_to_check:
                        score = fuzz.token_set_ratio(raw_lower, name.lower())
                        if score >= FUZZY_THRESHOLD:
                            best_hit = hit
                            break
                    if best_hit is not None:
                        break

                # Rule B: Strict vector fallback — top hit with distance < 0.40
                if (
                    best_hit is None
                    and hits
                    and hits[0]["distance"] < STRICT_VECTOR_THRESHOLD
                ):
                    best_hit = hits[0]

                if best_hit is not None:
                    meta = best_hit["metadata"]
                    ex_dict["is_mapped"] = True
                    ex_dict["canonical_name"] = meta.get("canonical_name", "")
                    ex_dict["patient_instructions"] = best_hit.get("document", "")
                    ex_dict["mechanics_tags"] = {
                        "is_closed_chain": meta.get("is_closed_chain", False),
                        "has_axial_load": meta.get("has_axial_load", False),
                        "is_high_impact": meta.get("is_high_impact", False),
                        "requires_overhead_motion": meta.get(
                            "requires_overhead_motion", False
                        ),
                    }
                    ex_dict["match_distance"] = best_hit["distance"]
                    mapped_count += 1
                else:
                    # Rule C: Miss
                    ex_dict["is_mapped"] = False
                    ex_dict["match_distance"] = hits[0]["distance"] if hits else None
                    unmapped_count += 1
                enriched_exercises.append(ex_dict)

            enriched_phases.append(
                {
                    "phase_title": phase.phase_title,
                    "region_focus": phase.region_focus,
                    "phase_goals": phase.phase_goals,
                    "clinical_interventions": phase.clinical_interventions,
                    "prescribed_exercises": enriched_exercises,
                    "phase_precautions": phase.phase_precautions,
                    "progression_criteria": phase.progression_criteria,
                }
            )

        enriched_plan = {
            "global_precautions": draft_plan.global_precautions,
            "phases": enriched_phases,
        }
        print(f"  Mapped {mapped_count} exercise(s), {unmapped_count} unmapped")
        return {"enriched_plan": enriched_plan}

    # --- Agentic RAG: Grader Node ---

    GRADER_PROMPT = """\
You are a Clinical Protocol Relevance Evaluator. Your job is to determine which retrieved protocols \
are actually relevant to the patient's clinical picture.

PATIENT SUMMARY:
{patient_summary}

KEY CONCERNS:
{key_concerns}

RETRIEVED PROTOCOLS:
{protocols_list}

EVALUATION RULES:
1. REJECT protocols whose target_conditions do not match the patient's clinical picture \
(e.g., neurological protocols for an orthopedic patient, post-operative protocols when no surgery occurred).
2. ACCEPT generic balance/strengthening protocols if the patient has relevant deficits.
3. ACCEPT protocols that address any of the patient's key concerns, even if not a perfect match.
4. When in doubt, ACCEPT — it's better to include a marginally relevant protocol than miss a useful one.

For each protocol, set is_relevant=True or False with a brief reason_for_rejection if False.
Begin with thought_process — evaluate target conditions against the patient summary.
"""

    def grader_node(state: PipelineState) -> dict:
        _notify("grader")
        print("\n[Step 5] Running grader_node (LLM)...")
        clinical_summary: ClinicalSummary = state["clinical_summary"]
        full_protocols: list[dict] = state.get("full_protocols", [])

        if not full_protocols:
            print("  No protocols to grade — passing through empty.")
            return {
                "relevant_protocols": [],
                "grader_feedback": state.get("grader_feedback", []),
            }

        # Build protocol list for prompt
        proto_lines: list[str] = []
        for p in full_protocols:
            proto_lines.append(
                f"- {p.get('parent_id', 'unknown')}: "
                f"body={p.get('primary_body_parts', '')}, "
                f"treatment={p.get('treatment_type', '')}, "
                f"conditions={p.get('target_conditions', '')}"
            )

        prompt = GRADER_PROMPT.format(
            patient_summary=clinical_summary.full_patient_summary,
            key_concerns="\n".join(f"- {c}" for c in clinical_summary.key_concerns),
            protocols_list="\n".join(proto_lines),
        )

        result = invoke_structured(llm, GraderOutput, prompt, fallback_llm)

        # Build lookup of evaluations by protocol_id
        eval_map = {e.protocol_id: e for e in result.evaluations}

        kept: list[dict] = []
        new_feedback: list[str] = []
        for p in full_protocols:
            pid = p.get("parent_id", "unknown")
            ev = eval_map.get(pid)
            if ev and not ev.is_relevant:
                new_feedback.append(f"Rejected '{pid}': {ev.reason_for_rejection}")
            else:
                kept.append(p)

        rejected_count = len(full_protocols) - len(kept)
        print(f"  Kept {len(kept)} protocol(s), rejected {rejected_count}")
        for fb in new_feedback:
            print(f"    {fb}")

        return {
            "relevant_protocols": kept,
            "grader_feedback": state.get("grader_feedback", []) + new_feedback,
        }

    # --- Agentic RAG: Route After Grader ---

    def route_after_grader(state: PipelineState) -> str:
        if len(state.get("relevant_protocols", [])) > 0:
            return _ROUTE_REASONER
        if state.get("retries", 0) >= 2:
            return _ROUTE_REASONER  # fallback with empty protocols
        return _ROUTE_QUERY_REWRITER

    # --- Agentic RAG: Query Rewriter Node ---

    QUERY_REWRITER_PROMPT = """\
You are a Medical Search Query Rewriter. Previous queries returned protocols that were ALL rejected \
as irrelevant to the patient.

PATIENT KEY CONCERNS:
{key_concerns}

REJECTION FEEDBACK:
{feedback}

REWRITE RULES:
1. Generate 4-6 new queries that avoid the topics mentioned in the rejection feedback.
2. Focus on orthopedic/musculoskeletal rehabilitation terms.
3. Avoid neurological, post-operative (unless surgery confirmed), or unrelated keywords.
4. Each query must have a body_part (one of: Knee, Shoulder, Spine, Core_Pelvis, Hip, Foot_Ankle, \
Elbow, Wrist_Hand, Head_Neck_TMJ, General_Body_Multijoint) and treatment_type (default 'Non-Operative').
5. Use specific exercise/intervention terms in keywords (e.g., 'hamstring strengthening eccentric exercises').

Begin with thought_process — analyze what went wrong and how to fix it.
"""

    def query_rewriter_node(state: PipelineState) -> dict:
        _notify("query_rewriter")
        print("\n[Step 5b] Running query_rewriter_node (LLM)...")
        clinical_summary: ClinicalSummary = state["clinical_summary"]
        feedback = state.get("grader_feedback", [])

        prompt = QUERY_REWRITER_PROMPT.format(
            key_concerns="\n".join(f"- {c}" for c in clinical_summary.key_concerns),
            feedback="\n".join(f"- {f}" for f in feedback)
            if feedback
            else "No specific feedback.",
        )

        result = invoke_structured(llm, RewrittenQueries, prompt, fallback_llm)
        print(
            f"  Rewrote {len(result.queries)} query/queries (retry {state.get('retries', 0) + 1}):"
        )
        for q in result.queries:
            print(f"    [{q.body_part}] {q.keywords}")

        return {
            "protocol_queries": result.queries,
            "retries": state.get("retries", 0) + 1,
        }

    def report_generator_node(state: PipelineState) -> dict:
        _notify("report_formatter")  # Same step name for UI — single "Формування звіту"
        print("\n[Step 7a] Running report_generator_node (LLM)...")
        english_report = generate_english_report(
            clinical_summary=state["clinical_summary"],
            enriched_plan=state.get("enriched_plan", {}),
            patient_info=state.get("patient_info", {}),
            llm=llm,
            fallback_llm=fallback_llm,
        )
        print(f"  Generated English report: {len(english_report.model_dump_json())} chars")
        return {"english_report": english_report}

    def report_translator_node(state: PipelineState) -> dict:
        # NO _notify — shares UI step with report_generator
        print("\n[Step 7b] Running report_translator_node (LLM)...")
        ukrainian_report = translate_report(
            english_report=state["english_report"],
            llm=llm,
            fallback_llm=fallback_llm,
        )
        markdown = render_markdown(ukrainian_report, lang="uk")
        print(f"  Generated Ukrainian report: {len(markdown)} characters")
        return {"final_report": markdown}

    # --- Build Graph ---

    graph = (
        StateGraph(PipelineState)
        .add_node("filter", filter_node)
        .add_node("summarize", summarize_node)
        .add_node("query_generator", query_generator_node)
        .add_node("protocol_retriever", protocol_retriever_node)
        .add_node("grader", grader_node)
        .add_node("query_rewriter", query_rewriter_node)
        .add_node("reasoner", reasoner_node)
        .add_node("exercise_mapper", exercise_mapper_node)
        .add_node("report_generator", report_generator_node)
        .add_node("report_translator", report_translator_node)
        .add_edge(START, "filter")
        .add_edge("filter", "summarize")
        .add_edge("summarize", "query_generator")
        .add_edge("query_generator", "protocol_retriever")
        .add_edge("protocol_retriever", "grader")
        # Agentic RAG Loop
        .add_conditional_edges(
            "grader",
            route_after_grader,
            {_ROUTE_REASONER: _ROUTE_REASONER, _ROUTE_QUERY_REWRITER: _ROUTE_QUERY_REWRITER},
        )
        .add_edge("query_rewriter", "protocol_retriever")
        # Final Path
        .add_edge("reasoner", "exercise_mapper")
        .add_edge("exercise_mapper", "report_generator")
        .add_edge("report_generator", "report_translator")
        .add_edge("report_translator", END)
        .compile()
    )
    return graph
