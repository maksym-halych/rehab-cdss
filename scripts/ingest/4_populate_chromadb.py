# scripts/ingest/4_populate_chromadb.py
"""
One-shot script: seeds ChromaDB from existing JSON files on disk.

Reads all JSONs from:
  data/knowledge_base/protocols/2_structured_json/   → rehab_protocols collection
  data/knowledge_base/protocols/3_exercises_db/      → rehab_exercises collection

Safe to re-run — upsert is idempotent.
Requires: the embedding key from api/.env (EMBEDDING_PROVIDER)
"""

import json
import sys
from pathlib import Path

import chromadb
from dotenv import load_dotenv
from module_2_reasoning.embeddings import make_embedding_function

_SCRIPT_DIR = Path(__file__).resolve().parent
load_dotenv(_SCRIPT_DIR.parent.parent / "api" / ".env", override=True)
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _chroma import (  # noqa: E402
    build_exercise_doc,
    build_exercise_metadata,
    build_protocol_doc,
    build_protocol_metadata,
)

_PROJECT_ROOT = _SCRIPT_DIR.parent.parent


PROTOCOLS_JSON_DIR = (
    _PROJECT_ROOT / "data" / "knowledge_base" / "protocols" / "2_structured_json"
)
EXERCISES_DB_DIR = (
    _PROJECT_ROOT / "data" / "knowledge_base" / "protocols" / "3_exercises_db"
)
CHROMA_DIR = _PROJECT_ROOT / "data" / "chromadb"

UPSERT_BATCH_SIZE = 50


def populate_protocols(collection: chromadb.Collection) -> int:
    ids, documents, metadatas = [], [], []
    total_sections = 0

    for json_path in sorted(PROTOCOLS_JSON_DIR.glob("*.json")):
        try:
            protocol = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Could not read {json_path.name}: {e}")
            continue

        if not protocol.get("is_valid_clinical_source", True):
            continue
        if protocol.get("doc_type") == "Irrelevant":
            continue

        file_stem = json_path.stem
        for idx, section in enumerate(protocol.get("sections", [])):
            doc_id = f"{file_stem}__s{idx}"
            doc_text = build_protocol_doc(protocol, section, idx)
            metadata = build_protocol_metadata(
                protocol, section, idx, source_file=json_path.name
            )

            ids.append(doc_id)
            documents.append(doc_text)
            metadatas.append(metadata)
            total_sections += 1

    # Upsert in batches
    for start in range(0, len(ids), UPSERT_BATCH_SIZE):
        end = start + UPSERT_BATCH_SIZE
        collection.upsert(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )

    return total_sections


def populate_exercises(collection: chromadb.Collection) -> int:
    ids, documents, metadatas = [], [], []

    for json_path in sorted(EXERCISES_DB_DIR.glob("*.json")):
        if json_path.stem.startswith("_"):
            continue
        try:
            card = json.loads(json_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"Warning: Could not read {json_path.name}: {e}")
            continue

        ids.append(json_path.stem)
        documents.append(build_exercise_doc(card))
        metadata = build_exercise_metadata(card)
        metadatas.append(metadata)

    for start in range(0, len(ids), UPSERT_BATCH_SIZE):
        end = start + UPSERT_BATCH_SIZE
        collection.upsert(
            ids=ids[start:end],
            documents=documents[start:end],
            metadatas=metadatas[start:end],
        )

    return len(ids)


def main() -> None:
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    ef = make_embedding_function()
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))

    protocols_col = client.get_or_create_collection(
        name="rehab_protocols",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    exercises_col = client.get_or_create_collection(
        name="rehab_exercises",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    print("Populating rehab_protocols...")
    n_protocols = len(list(PROTOCOLS_JSON_DIR.glob("*.json")))
    n_sections = populate_protocols(protocols_col)
    print(f"Upserted {n_protocols} protocols ({n_sections} sections total).")

    print("Populating rehab_exercises...")
    n_exercises = populate_exercises(exercises_col)
    print(f"Upserted {n_exercises} exercises.")


if __name__ == "__main__":
    main()
