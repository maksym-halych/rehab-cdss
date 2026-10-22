# ADR-05: Local de-identification before external patient processing

Date: 2026-10-21. Issue: [E2.6 / #23](https://github.com/maksym-halych/rehab-cdss/issues/23).
Status: implementation proposed; team review and QA acceptance pending.

The issue originally reserved ADR-04 for this policy. PR #51 assigned ADR-04 to
Postgres job storage before this change was merged. ADR-05 records the privacy
decision without renumbering the existing database decision.

## Decision

Apply the strict NFR-01 rule: do not send patient names, birth dates, local IDs,
contact details, file names, or other direct identifiers to model providers.
Do not introduce a patient pseudonym, hash, job ID, stable token, or reversible
identity map in an external request. `[REDACTED]` is one shared replacement
constant, not a patient identifier. Any future pseudonym needs a new decision.

Keep only age, normalized gender, activity level, numeric test measurements and
their clinical labels, units, norms and scrubbed clinical interpretations.
Do not derive age from birth date; use the supplied age. Unknown metadata stays
local. Clinical measurements must be finite numbers. Invalid demographic values
or malformed inputs stop processing before a provider request.

## Boundary and implementation

`build_pipeline(...).invoke(...)` is the supported patient-processing entry point
for both the API and CLI. `PrivatePipeline` makes a new `PrivacyGuard` per run,
collects identity values locally, and projects input onto the clinical allowlist
before the compiled LangGraph sees it. Form overrides preserve the original
patient identity in local export metadata so old names repeated in notes are
still removed. Caller-supplied graph state, callbacks, run names and metadata
are not forwarded. Only `recursion_limit` is accepted from invocation config.

The guard removes known identity values and name components after Unicode
normalization, case-insensitive matching and whitespace normalization. Additional
patterns remove email addresses, phone numbers, calendar dates, UUIDs, URLs,
common secret formats and explicitly labelled identity fields in text. It copies
input rather than modifying the local source. Its representation hides tokens.

Every patient-related chat call uses `invoke_structured`: summary, query
generation, grading, rewriting, reasoning, report generation and translation.
The same guard runs before primary, retry and fallback calls. Responses are
scrubbed before local Pydantic validation and reuse in later nodes. The SDK gets
a JSON schema rather than a Pydantic class, so its parsed-model serialization
cannot print a warning containing the raw model response.

Protocol and exercise searches also require the active guard and scrub query
text before Chroma calls the external embedding provider. Identity context uses
`ContextVar`, is isolated between worker threads and is reset after success or
failure. Do not store it on a shared LLM or embedding client.

LangSmith tracing is disabled for the whole patient run, even if enabled in the
environment. LangChain debug/verbose mode, model callbacks and provider debug
logging fail closed. Application progress output contains only static step names
and counts. It does not print patient objects, file paths, generated queries,
grader feedback or provider exception bodies. API/CLI errors use static messages.

The separate `scripts/ingest/` tools process reviewed public rehabilitation
protocols and exercises, not patient exports. They are not patient upload entry
points and must never receive clinic records or patient notes. Their document
processing is outside this patient boundary; this ADR does not claim that those
tools anonymize arbitrary source documents.

## Limits and operating requirements

This is deterministic de-identification, not a general anonymization guarantee.
Unlabelled names absent from the identity fields, new name inflections or
transliterations, novel identifiers and identifying life events in free text
cannot all be recognized by these rules. The input producer must provide known
identifiers in identity fields, and clinical free text needs local review before
real patient use. Do not treat a successful request as proof of anonymity.
The current tests and demos use synthetic inputs only.

Exact age and rare clinical combinations can still allow indirect identification.
Rules can also remove legitimate clinical text when it matches an identity or a
date/phone pattern. Numeric measurements and norms stay unchanged. QA must check
that retained clinical meaning is adequate before use with a new input format.
The application must not silently substitute omitted measurements or conclusions.

Raw JSON remains in local job storage and its existing download endpoint. This
change does not anonymize that storage or add authorization, encryption, retention
rules, or protection against administrator-enabled request-body logging/APM.
Those need their own controls. No raw inputs, provider bodies, or identity maps
should be attached to debugging or telemetry services.

## Verification and acceptance

Run the offline suite from `api/`:

```bash
uv run --locked pytest -W error --cov --cov-fail-under=60 --cov-report=term-missing
```

`test_privacy.py` intercepts actual `ChatOpenAI` JSON requests using an in-memory
HTTP transport, including a retry and a fallback. It checks synthetic names,
dates, local IDs, contacts, tracing, malformed data, embedding queries, provider
errors and thread isolation. No network request reaches a provider.

`test_privacy_pipeline.py` runs the graph with deterministic model responses,
including rejection/rewrite and translation, and checks prompts, outputs and CLI
logs. `test_jobs_demo.py` checks API errors and original/overridden identities.

QA must review the tests and the free-text limits, verify the allowed clinical
values and source traceability, and link its acceptance result to #23. Review and
green CI are required before the issue moves to Done. This document is not a QA
sign-off or approval to process real patient data.
