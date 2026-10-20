# scripts/ingest/3_build_exercise_db.py
"""
Pass 2 — Exercise DB builder.

Reads all structured protocol JSONs from 2_structured_json/, deduplicates raw
exercise names using ChromaDB semantic search + LLM entity resolution, and writes
one canonical ExerciseCard JSON per unique exercise to 3_exercises_db/.
ChromaDB (rehab_exercises collection) is used for vector search and persistence.

Exercises are processed one at a time, sequentially.

NOTE: ChromaDB collections are dimension-specific. If changing EMBEDDING_PROVIDER/EMBEDDING_MODEL, clear
  data/chromadb/ and re-run this script and 4_populate_chromadb.py.
"""

import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

import chromadb
import requests
from chromadb import Collection
from module_2_reasoning.embeddings import make_embedding_function
from langchain_core.exceptions import OutputParserException
from langchain_openai import ChatOpenAI
from rapidfuzz import fuzz

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
load_dotenv(_PROJECT_ROOT / "api" / ".env", override=True)

if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _chroma import build_exercise_doc, build_exercise_metadata  # noqa: E402
from _prompts import load_prompt  # noqa: E402
from _retry import invoke_with_retry  # noqa: E402
from schemas import EntityResolutionDecision, ExerciseCard  # noqa: E402

PROCESSING_ERRORS = (ValueError, requests.RequestException, OutputParserException)

JSON_DIR = _PROJECT_ROOT / "data" / "knowledge_base" / "protocols" / "2_structured_json"
DB_DIR = _PROJECT_ROOT / "data" / "knowledge_base" / "protocols" / "3_exercises_db"
CHROMA_DIR = _PROJECT_ROOT / "data" / "chromadb"

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
LLM_MATCHER_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
LLM_GENERATOR_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-pro-preview")
LLM_FALLBACK_MODEL = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3-flash-preview")
TOP_N_CANDIDATES = 20
DISTANCE_THRESHOLD = 0.35  # cosine distance ≤ 0.35 ↔ similarity ≥ 0.65
MAX_SUFFIX_SEARCH = 99  # max slug-N to check in find_existing_card_for_slug
LLM_RETRY_ATTEMPTS = 5
LLM_RETRY_BASE_DELAY = 4  # seconds; backoff: 4, 8, 16, 32, 64


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------


def get_exercises(section_dict: dict) -> list[dict]:
    """Return exercise list tolerating both 'exercises' and 'patient_exercises' keys."""
    return section_dict.get("patient_exercises") or section_dict.get("exercises") or []


def load_all_raw_names(
    json_dir: Path,
) -> list[tuple[str, str | None, str]]:
    """
    Walk all JSON files in json_dir and collect (raw_name, specifications, protocol_body_part).
    Deduplicates by normalized key (lowercase) — first-seen wins.
    Skips irrelevant/non-clinical documents.
    protocol_body_part: first primary_body_part from the protocol (hint for card generation).
    """
    seen: dict[str, tuple[str, str | None, str]] = {}
    for json_path in sorted(json_dir.glob("*.json")):
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Could not read {json_path.name}: {e}")
            continue

        if not data.get("is_valid_clinical_source", True):
            continue
        if data.get("doc_type") == "Irrelevant":
            continue

        body_parts = data.get("primary_body_parts") or data.get("primary_body_part")
        if isinstance(body_parts, list) and body_parts:
            protocol_body_part = body_parts[0]
        elif isinstance(body_parts, str) and body_parts:
            protocol_body_part = body_parts
        else:
            protocol_body_part = "Unknown"

        for section in data.get("sections", []):
            for ex in get_exercises(section):
                raw_name = ex.get("raw_name", "").strip()
                if not raw_name:
                    continue
                key = raw_name.lower()
                if key not in seen:
                    seen[key] = (raw_name, ex.get("specifications"), protocol_body_part)

    return list(seen.values())


def make_exercise_id(canonical_name: str) -> str:
    """'Straight Leg Raise' → 'straight-leg-raise'"""
    slug = canonical_name.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def load_existing_aliases(db_dir: Path) -> set[str]:
    """Build a flat set of all known aliases from existing exercise cards."""
    aliases: set[str] = set()
    for card_path in db_dir.glob("*.json"):
        if card_path.stem.startswith("_"):
            continue
        try:
            data = json.loads(card_path.read_text(encoding="utf-8"))
            aliases.update(data.get("aliases", []))
            aliases.add(data.get("canonical_name", ""))
        except (OSError, json.JSONDecodeError):
            pass
    return aliases


def find_existing_card_for_slug(db_dir: Path, slug: str) -> str | None:
    """Return exercise_id if a card with this slug already exists, else None."""
    if (db_dir / f"{slug}.json").exists():
        return slug
    for n in range(1, MAX_SUFFIX_SEARCH + 1):
        cand = f"{slug}-{n}"
        if (db_dir / f"{cand}.json").exists():
            return cand
    return None


# ---------------------------------------------------------------------------
# ChromaDB helpers
# ---------------------------------------------------------------------------


def find_top_candidates_chroma(
    raw_name: str,
    collection: Collection,
    top_n: int = TOP_N_CANDIDATES,
    distance_threshold: float = DISTANCE_THRESHOLD,
) -> list[tuple[str, float]]:
    """
    Query ChromaDB for top candidates similar to raw_name.
    Returns list of (exercise_id, similarity_score) where score = 1 - cosine_distance.
    Only returns candidates with distance <= distance_threshold.
    """
    count = collection.count()
    if count == 0:
        return []

    results = collection.query(
        query_texts=[raw_name],
        n_results=min(top_n, count),
    )
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[]])[0]

    candidates = []
    for eid, dist in zip(ids, distances):
        if dist <= distance_threshold:
            # Convert cosine distance → similarity score for LLM context
            candidates.append((eid, round(1.0 - dist, 4)))
    return candidates


# ---------------------------------------------------------------------------
# LLM operations
# ---------------------------------------------------------------------------


def resolve_entity(
    raw_name: str,
    specifications: str | None,
    candidates: list[tuple[str, float]],
    db_dir: Path,
    llm: ChatOpenAI,
    fallback_llm: ChatOpenAI | None = None,
) -> EntityResolutionDecision:
    """Call LLM to decide MERGE vs CREATE_NEW against top candidates."""
    structured_llm = llm.with_structured_output(EntityResolutionDecision)

    candidates_data = []
    for eid, score in candidates:
        card_path = db_dir / f"{eid}.json"
        if not card_path.exists():
            continue
        try:
            card = json.loads(card_path.read_text(encoding="utf-8"))
            candidates_data.append(
                {
                    "exercise_id": eid,
                    "canonical_name": card.get("canonical_name", eid),
                    "aliases": card.get("aliases", []),
                    "primary_body_parts": card.get("primary_body_parts", []),
                    "similarity_score": round(score, 4),
                }
            )
        except (OSError, json.JSONDecodeError):
            pass

    specs_str = specifications.strip() if specifications else "not specified"
    prompt = load_prompt(
        "entity_resolution",
        RAW_NAME=raw_name,
        SPECIFICATIONS=specs_str,
        CANDIDATES_JSON=json.dumps(candidates_data, indent=2),
    )

    def _invoke():
        return structured_llm.invoke(prompt)

    fallback_invoke_fn = None
    if fallback_llm is not None:
        fallback_structured = fallback_llm.with_structured_output(
            EntityResolutionDecision
        )

        def _fallback():
            return fallback_structured.invoke(prompt)

        fallback_invoke_fn = _fallback

    return invoke_with_retry(_invoke, fallback_invoke_fn=fallback_invoke_fn)


def generate_exercise_card(
    raw_name: str,
    specifications: str | None,
    protocol_body_part: str,
    llm: ChatOpenAI,
    fallback_llm: ChatOpenAI | None = None,
) -> ExerciseCard:
    """Generate a full ExerciseCard for a new exercise."""
    structured_llm = llm.with_structured_output(ExerciseCard)
    prompt = load_prompt(
        "exercise_card_generation",
        RAW_NAME=raw_name,
        SPECIFICATIONS=specifications or "not specified",
        PROTOCOL_BODY_PART=protocol_body_part,
    )

    def _invoke():
        return structured_llm.invoke(prompt)

    fallback_invoke_fn = None
    if fallback_llm is not None:
        fallback_structured = fallback_llm.with_structured_output(ExerciseCard)

        def _fallback():
            return fallback_structured.invoke(prompt)

        fallback_invoke_fn = _fallback

    card: ExerciseCard = invoke_with_retry(
        _invoke, fallback_invoke_fn=fallback_invoke_fn
    )
    if raw_name not in card.aliases:
        card.aliases.insert(0, raw_name)
    return card


def merge_aliases_into_card(
    exercise_id: str, aliases_to_add: list[str], db_dir: Path
) -> dict:
    """Add aliases to an existing card. Returns updated card dict (for ChromaDB upsert)."""
    card_path = db_dir / f"{exercise_id}.json"
    data = json.loads(card_path.read_text(encoding="utf-8"))
    existing = set(data.get("aliases", []))
    for a in aliases_to_add:
        if a and a not in existing:
            data.setdefault("aliases", []).append(a)
            existing.add(a)
    card_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return data


# ---------------------------------------------------------------------------
# Single-item processing
# ---------------------------------------------------------------------------

_NewCard = tuple[str, ExerciseCard]  # (exercise_id_slug, card)
_Merge = tuple[str, str]  # (target_id, raw_name)


def _process_one(
    raw_name: str,
    specs: str | None,
    protocol_body_part: str,
    collection: Collection,
    db_dir: Path,
    llm_matcher: ChatOpenAI,
    llm_generator: ChatOpenAI,
    global_processed_aliases: set[str],
    fallback_llm_matcher: ChatOpenAI | None = None,
    fallback_llm_generator: ChatOpenAI | None = None,
) -> tuple[list[_NewCard], list[_Merge], int]:
    """
    Process a single (raw_name, specifications). Returns (new_cards, merges, errors).
    All operations are sequential.
    """
    new_cards: list[_NewCard] = []
    merges: list[_Merge] = []

    # Step 1: ChromaDB candidate search
    try:
        candidates = find_top_candidates_chroma(raw_name, collection)
    except Exception as e:
        print(f"  Query error for {raw_name!r}: {e}")
        return [], [], 1

    # Step 2: Pre-LLM fuzzy matching + LLM entity resolution (if candidates)
    if candidates:
        # Pre-LLM: deterministic fuzzy match to skip LLM for obvious duplicates
        for eid, score in candidates:
            try:
                cand_card = json.loads(
                    (db_dir / f"{eid}.json").read_text(encoding="utf-8")
                )
            except (OSError, json.JSONDecodeError):
                continue
            cand_name = cand_card.get("canonical_name", "")
            if fuzz.token_sort_ratio(raw_name.lower(), cand_name.lower()) > 90:
                print(f"  [Auto-Merge by Fuzzy]: '{raw_name}' == '{cand_name}'")
                return [], [(eid, raw_name)], 0

        # Fall through to LLM if no fuzzy match
        try:
            print(f"  Resolving: {raw_name!r}...")
            decision = resolve_entity(
                raw_name,
                specs,
                candidates,
                db_dir,
                llm_matcher,
                fallback_llm=fallback_llm_matcher,
            )
            if decision.decision == "MERGE":
                target_id = decision.merge_target_id
                if not target_id:
                    print(
                        f"  Warning: MERGE without target for {raw_name!r}. Treating as CREATE_NEW."
                    )
                elif not (db_dir / f"{target_id}.json").exists():
                    print(
                        f"  Warning: merge target '{target_id}' not on disk. Treating as CREATE_NEW."
                    )
                else:
                    merges.append((target_id, raw_name))
                    print(f"  Merged into: {target_id}  ← {raw_name!r}")
                    return new_cards, merges, 0
        except PROCESSING_ERRORS as e:
            print(f"  Resolution error for {raw_name!r}: {e}")
            return [], [], 1
        # fall through to CREATE_NEW

    # Step 3: Card generation
    try:
        print(f"  Generating card: {raw_name!r}...")
        card = generate_exercise_card(
            raw_name,
            specs,
            protocol_body_part,
            llm_generator,
            fallback_llm=fallback_llm_generator,
        )

        # Alias validation: drop any alias already claimed by another card
        # Preserve raw_name as first (aliases[0]); deduplicate rest while keeping order
        lower_global = {a.lower().strip() for a in global_processed_aliases}
        raw_lower = raw_name.lower().strip()
        safe_aliases = [raw_name]  # always keep triggering name first
        seen_lower = {raw_lower}
        for alias in card.aliases:
            clean = alias.lower().strip()
            if clean == raw_lower or clean in seen_lower:
                continue
            if clean in lower_global:
                print(f"  [Warning] Dropping hallucinated overlapping alias: '{alias}'")
            else:
                safe_aliases.append(alias)
                seen_lower.add(clean)
        card.aliases = safe_aliases

        slug = make_exercise_id(card.canonical_name)
        new_cards.append((slug, card))
        print(f"  Created: {slug}.json  ← {raw_name!r}")
    except PROCESSING_ERRORS as e:
        print(f"  Card generation error for {raw_name!r}: {e}")
        return [], [], 1

    return new_cards, merges, 0


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    if not JSON_DIR.exists():
        print(f"Error: Input directory does not exist: {JSON_DIR}")
        return

    diploma_key = os.getenv("DIPLOMA_API_KEY")
    if not diploma_key:
        raise ValueError("DIPLOMA_API_KEY environment variable is required")


    llm_matcher = ChatOpenAI(
        model=LLM_MATCHER_MODEL,
        base_url=GEMINI_BASE_URL,
        api_key=diploma_key,
        temperature=0,
    )
    llm_generator = ChatOpenAI(
        model=LLM_GENERATOR_MODEL,
        base_url=GEMINI_BASE_URL,
        api_key=diploma_key,
        temperature=0,
    )
    fallback_llm = ChatOpenAI(
        model=LLM_FALLBACK_MODEL,
        base_url=GEMINI_BASE_URL,
        api_key=diploma_key,
        temperature=0,
    )

    ef = make_embedding_function()
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = chroma_client.get_or_create_collection(
        name="rehab_exercises",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    # Fast-skip set: all aliases already in the DB (case-insensitive to match load normalization)
    processed_aliases = load_existing_aliases(DB_DIR)
    lower_processed = {a.lower() for a in processed_aliases}

    all_raw_names = load_all_raw_names(JSON_DIR)
    pending = [
        (n, s, ctx) for n, s, ctx in all_raw_names if n.lower() not in lower_processed
    ]
    skipped = len(all_raw_names) - len(pending)

    print(
        f"Found {len(all_raw_names)} unique raw names. "
        f"{skipped} already in DB, {len(pending)} to process."
    )

    total_merged = total_created = total_errors = 0

    for i, (raw_name, specs, protocol_body_part) in enumerate(pending, 1):
        print(f"\n[{i}/{len(pending)}] {raw_name!r}")

        new_cards, merges, batch_errors = _process_one(
            raw_name,
            specs,
            protocol_body_part,
            collection,
            DB_DIR,
            llm_matcher,
            llm_generator,
            processed_aliases,
            fallback_llm_matcher=fallback_llm,
            fallback_llm_generator=fallback_llm,
        )

        # Commit merges (sequential)
        for target_id, raw_name in merges:
            card_data = merge_aliases_into_card(target_id, [raw_name], DB_DIR)
            collection.upsert(
                ids=[target_id],
                documents=[build_exercise_doc(card_data)],
                metadatas=[build_exercise_metadata(card_data)],
            )
            processed_aliases.add(raw_name)
        total_merged += len(merges)

        # Commit new cards + upsert to ChromaDB (merge into existing if slug exists)
        for slug, card in new_cards:
            raw_name = card.aliases[0] if card.aliases else card.canonical_name
            existing_id = find_existing_card_for_slug(DB_DIR, slug)

            if existing_id:
                # Slug collision: merge all aliases from new card into existing
                card_data = merge_aliases_into_card(existing_id, card.aliases, DB_DIR)
                collection.upsert(
                    ids=[existing_id],
                    documents=[build_exercise_doc(card_data)],
                    metadatas=[build_exercise_metadata(card_data)],
                )
                processed_aliases.add(raw_name)
                processed_aliases.update(card_data.get("aliases", []))
                processed_aliases.add(card_data.get("canonical_name", ""))
                total_merged += 1
                print(f"  Merged into: {existing_id}  ← {raw_name!r}")
                continue

            exercise_id = slug
            suffix = 1
            while (DB_DIR / f"{exercise_id}.json").exists():
                exercise_id = f"{slug}-{suffix}"
                suffix += 1

            card_path = DB_DIR / f"{exercise_id}.json"
            card_path.write_text(card.model_dump_json(indent=2), encoding="utf-8")

            # Upsert to ChromaDB
            card_dict = card.model_dump()
            collection.upsert(
                ids=[exercise_id],
                documents=[build_exercise_doc(card_dict)],
                metadatas=[build_exercise_metadata(card_dict)],
            )

            processed_aliases.update(card.aliases)
            processed_aliases.add(card.canonical_name)
            total_created += 1

        total_errors += batch_errors

    print(
        f"\nDone. {len(all_raw_names)} total | "
        f"{skipped} skipped | {total_merged} merged | "
        f"{total_created} created | {total_errors} errors"
    )


if __name__ == "__main__":
    main()
