"""
Query helpers for Module 2 agents.

Provides semantic + metadata-filtered search over the ChromaDB knowledge base:
  - rehab_protocols  (section-level granularity)
  - rehab_exercises  (one doc per exercise card)

Usage:
    from module_2_reasoning.retrieval import search_protocols, search_exercises
"""

import threading

import chromadb
from chromadb import Collection

from .embeddings import make_embedding_function
from .paths import DATA_DIR
from .privacy import active_guard

CHROMA_DIR = DATA_DIR / "chromadb"

# Lazy singleton state
_init_lock = threading.Lock()
_client: object | None = None
_protocols_col: Collection | None = None
_exercises_col: Collection | None = None


def body_parts_to_str(value: list | str | None) -> str:
    """Normalize primary_body_parts from ChromaDB (array or legacy string) to comma-separated string."""
    if isinstance(value, list):
        return ", ".join(str(x) for x in value if x)
    return str(value) if value else ""


def _build_where(filters: dict) -> dict | None:
    """Convert a filters dict into a ChromaDB where clause."""
    if len(filters) == 1:
        return filters
    if len(filters) > 1:
        return {"$and": [{k: v} for k, v in filters.items()]}
    return None


def get_collections() -> tuple[Collection, Collection]:
    """Returns (protocols_collection, exercises_collection). Lazy singleton."""
    global _client, _protocols_col, _exercises_col

    if _protocols_col is not None and _exercises_col is not None:
        return _protocols_col, _exercises_col

    with _init_lock:
        # Re-check inside lock in case another thread initialized first
        if _protocols_col is not None and _exercises_col is not None:
            return _protocols_col, _exercises_col

        ef = make_embedding_function()
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
        _protocols_col = _client.get_or_create_collection(
            name="rehab_protocols",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
        _exercises_col = _client.get_or_create_collection(
            name="rehab_exercises",
            embedding_function=ef,
            metadata={"hnsw:space": "cosine"},
        )
    return _protocols_col, _exercises_col


def search_protocols(
    query: str,
    n_results: int = 5,
    body_part: str | None = None,
    doc_type: str | None = None,
    treatment_type: str | None = None,
) -> list[dict]:
    """
    Semantic search over rehab_protocols (section-level).

    Args:
        query:          Free-text query (e.g. 'ACL reconstruction knee phase 2').
        n_results:      Number of results to return.
        body_part:      Optional filter on `primary_body_parts` metadata field (substring match).
        doc_type:       Optional filter on `doc_type` metadata field.
        treatment_type: Optional filter on `treatment_type` metadata field.

    Returns:
        List of dicts with keys: id, document, metadata, distance.
        Sorted by relevance (lowest distance first for cosine space).
    """
    query = active_guard().text(query)
    protocols_col, _ = get_collections()

    filters = {}
    if body_part:
        filters["primary_body_parts"] = {"$contains": body_part}
    if doc_type:
        filters["doc_type"] = {"$eq": doc_type}
    if treatment_type:
        filters["treatment_type"] = {"$eq": treatment_type}

    kwargs: dict = {"query_texts": [query], "n_results": n_results}
    where = _build_where(filters)
    if where:
        kwargs["where"] = where

    results = protocols_col.query(**kwargs)
    return _unpack_results(results)


def fetch_full_protocol(parent_id: str) -> dict:
    """
    Fetch ALL sections of a protocol by parent_id and return a structured object
    with protocol-level fields hoisted once (not repeated per section).

    Returns:
        {
            "parent_id": str,
            "doc_type": str,
            "treatment_type": str,
            "primary_body_parts": str,   # comma-separated if multiple
            "target_conditions": str,   # comma-separated
            "global_red_flags": str,    # comma-separated — appears ONCE
            "sections": [
                {
                    "id": str,
                    "section_title": str,
                    "section_index": int,
                    "goals": str,
                    "precautions": str,
                    "progression_criteria": str,
                }
            ]
        }
        Sections are sorted by section_index ascending.
        Returns an empty dict if no sections found.
    """
    protocols_col, _ = get_collections()
    results = protocols_col.get(
        where={"parent_id": {"$eq": parent_id}},
        include=["metadatas", "documents"],
    )

    ids = results.get("ids", [])
    metadatas = results.get("metadatas", [])
    documents = results.get("documents", [])
    if not ids:
        return {}

    first = metadatas[0]
    protocol_obj: dict = {
        "parent_id": parent_id,
        "doc_type": first.get("doc_type", ""),
        "treatment_type": first.get("treatment_type", ""),
        "primary_body_parts": body_parts_to_str(first.get("primary_body_parts", "")),
        "target_conditions": first.get("target_conditions", ""),
        "global_red_flags": first.get("global_red_flags", ""),
        "sections": [],
    }

    raw_sections = []
    for doc_id, meta, doc_text in zip(ids, metadatas, documents):
        # Skip sections with empty exercise blocks to prevent hallucination
        if (
            doc_text
            and "[EXERCISES]:" in doc_text
            and len(doc_text.split("[EXERCISES]:")[1].strip()) < 5
        ):
            continue
        raw_sections.append(
            {
                "id": doc_id,
                "section_title": meta.get("section_title", ""),
                "section_index": meta.get("section_index", 0),
                "goals": meta.get("goals", ""),
                "precautions": meta.get("precautions", ""),
                "progression_criteria": meta.get("progression_criteria", ""),
                "document_context": doc_text or "",
            }
        )

    raw_sections.sort(key=lambda x: x["section_index"])
    protocol_obj["sections"] = raw_sections
    return protocol_obj


def search_exercises(
    query: str,
    n_results: int = 10,
    exclude_high_impact: bool = False,
    exclude_axial_load: bool = False,
) -> list[dict]:
    """
    Semantic search over rehab_exercises.

    Args:
        query:              Free-text query.
        n_results:          Number of results to return.
        exclude_high_impact: Filter out exercises with is_high_impact=True.
        exclude_axial_load:  Filter out exercises with has_axial_load=True.

    Returns:
        List of dicts with keys: id, document, metadata, distance.
    """
    query = active_guard().text(query)
    _, exercises_col = get_collections()

    filters = {}
    if exclude_high_impact:
        filters["is_high_impact"] = {"$eq": False}
    if exclude_axial_load:
        filters["has_axial_load"] = {"$eq": False}

    kwargs: dict = {"query_texts": [query], "n_results": n_results}
    where = _build_where(filters)
    if where:
        kwargs["where"] = where

    results = exercises_col.query(**kwargs)
    return _unpack_results(results)


def _unpack_results(results: dict) -> list[dict]:
    """Flatten ChromaDB query result into a list of dicts."""
    out = []
    ids = results.get("ids", [[]])[0]
    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]

    for doc_id, doc, meta, dist in zip(ids, documents, metadatas, distances):
        out.append({"id": doc_id, "document": doc, "metadata": meta, "distance": dist})
    return out
