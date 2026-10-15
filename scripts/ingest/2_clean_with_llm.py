# scripts/ingest/2_clean_with_llm.py
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dotenv import load_dotenv

import chromadb
import requests
from chromadb import Collection
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
from langchain_core.exceptions import OutputParserException
from langchain_openai import ChatOpenAI

_SCRIPT_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _SCRIPT_DIR.parent.parent
load_dotenv(_PROJECT_ROOT / ".env", override=True)

if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from _chroma import build_protocol_doc, build_protocol_metadata  # noqa: E402
from _prompts import load_prompt  # noqa: E402
from _retry import invoke_with_retry  # noqa: E402
from schemas import ClinicalProtocol  # noqa: E402

PROCESSING_ERRORS = (ValueError, requests.RequestException, OutputParserException)

RAW_DIR = _PROJECT_ROOT / "data" / "knowledge_base" / "protocols" / "1_extracted_raw"
JSON_DIR = _PROJECT_ROOT / "data" / "knowledge_base" / "protocols" / "2_structured_json"
CHROMA_DIR = _PROJECT_ROOT / "data" / "chromadb"

EMBED_MODEL = "text-embedding-3-small"
BATCH_SIZE = 5


def analyze_and_clean_text(
    raw_text: str,
    llm: ChatOpenAI,
    fallback_llm: ChatOpenAI | None = None,
) -> ClinicalProtocol:
    structured_llm = llm.with_structured_output(ClinicalProtocol)
    prompt = load_prompt("protocol_extraction", RAW_TEXT=raw_text)

    def _invoke():
        return structured_llm.invoke(prompt)

    fallback_invoke_fn = None
    if fallback_llm is not None:
        fallback_structured = fallback_llm.with_structured_output(ClinicalProtocol)

        def _fallback():
            return fallback_structured.invoke(prompt)

        fallback_invoke_fn = _fallback

    return invoke_with_retry(_invoke, fallback_invoke_fn=fallback_invoke_fn)


def _upsert_protocol_sections(
    protocol: ClinicalProtocol, source_file: str, collection: Collection
) -> None:
    """Build section documents + metadata dicts, call collection.upsert()."""
    protocol_dict = protocol.model_dump()
    file_stem = Path(source_file).stem
    ids, documents, metadatas = [], [], []

    for idx, section in enumerate(protocol.sections):
        section_dict = protocol_dict["sections"][idx]
        doc_text = build_protocol_doc(protocol_dict, section_dict, idx)
        metadata = build_protocol_metadata(
            protocol_dict, section_dict, idx, source_file
        )
        ids.append(f"{file_stem}__s{idx}")
        documents.append(doc_text)
        metadatas.append(metadata)

    if ids:
        collection.upsert(ids=ids, documents=documents, metadatas=metadatas)


def _process_one(
    txt_path: Path,
    llm: ChatOpenAI,
    collection: Collection,
    fallback_llm: ChatOpenAI | None = None,
) -> None:
    filename = txt_path.name
    out_path = JSON_DIR / txt_path.with_suffix(".json").name
    if out_path.exists():
        print(f"Skipping {filename}: Already processed.")
        return
    print(f"Processing {filename}...")
    raw_text = txt_path.read_text(encoding="utf-8")
    try:
        result = analyze_and_clean_text(raw_text, llm, fallback_llm)
        if not result.is_valid_clinical_source or result.doc_type == "Irrelevant":
            print(f"Skipping {filename}: Irrelevant or non-clinical.")
            return
        out_path.write_text(
            result.model_dump_json(indent=2),
            encoding="utf-8",
        )
        print(f"Saved {out_path.name} (Type: {result.doc_type})")
        _upsert_protocol_sections(result, out_path.name, collection)
    except PROCESSING_ERRORS as e:
        print(f"Error processing {filename}: {e}")


def main() -> None:
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)

    if not RAW_DIR.exists():
        print(f"Error: Input directory does not exist: {RAW_DIR}")
        return

    api_key = os.getenv("DIPLOMA_API_KEY")
    if not api_key:
        raise ValueError("DIPLOMA_API_KEY is required (set in .env or environment)")

    openai_key = os.getenv("OPENAI_API_KEY")
    if not openai_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required for ChromaDB embeddings"
        )

    llm = ChatOpenAI(
        model="gemini-3.1-pro-preview",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=api_key,
        temperature=0,
    )
    fallback_llm = ChatOpenAI(
        model="gemini-2.5-pro",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        api_key=api_key,
        temperature=0,
    )

    ef = OpenAIEmbeddingFunction(api_key=openai_key, model_name=EMBED_MODEL)
    chroma_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = chroma_client.get_or_create_collection(
        name="rehab_protocols",
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )

    txt_files = sorted(RAW_DIR.glob("*.txt"))
    print(f"Found {len(txt_files)} file(s) — processing with batch_size={BATCH_SIZE}")
    with ThreadPoolExecutor(max_workers=BATCH_SIZE) as executor:
        executor.map(
            lambda p: _process_one(p, llm, collection, fallback_llm), txt_files
        )


if __name__ == "__main__":
    main()
