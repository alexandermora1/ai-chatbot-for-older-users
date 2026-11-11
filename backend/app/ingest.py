"""Build the knowledge base: fetch pages, split them into chunks, embed, and save the index.

Usage (from the backend folder):
    python -m app.ingest              # fetch, chunk and embed
    python -m app.ingest --skip-fetch # reuse pages already saved in data/raw
"""

from __future__ import annotations

import argparse

import numpy as np

from .chunk import chunk_pages
from .config import INDEX_DIR, RAW_DIR, SOURCES_FILE, get_settings
from .llm import get_client
from .scrape import fetch_all, load_pages, load_sources
from .store import VectorStore

BATCH_SIZE = 16


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-fetch", action="store_true", help="reuse pages in data/raw instead of fetching")
    args = parser.parse_args()

    settings = get_settings()

    if not args.skip_fetch:
        sources = load_sources(SOURCES_FILE)
        print(f"Fetching {len(sources)} pages...")
        problems = fetch_all(sources, RAW_DIR)
        for source, reason in problems:
            print(f"  SKIPPED {source['id']} ({source['url']}): {reason}")

    pages = load_pages(RAW_DIR)
    if not pages:
        raise SystemExit("No pages in data/raw. Nothing to index.")
    chunks = chunk_pages(pages)
    print(f"{len(pages)} pages split into {len(chunks)} chunks")

    client = get_client(settings)
    vectors: list[list[float]] = []
    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start : start + BATCH_SIZE]
        # The title and heading are embedded with the text, so short chunks keep their context.
        vectors.extend(client.embed([f"{c.title}\n{c.heading}\n{c.text}" for c in batch]))
        print(f"  embedded {min(start + BATCH_SIZE, len(chunks))}/{len(chunks)}")

    VectorStore(chunks, np.asarray(vectors, dtype=np.float32)).save(INDEX_DIR)
    mode = "FAKE stand-in (not real embeddings)" if settings.use_fake_llm else "Azure OpenAI"
    print(f"Saved index to {INDEX_DIR} using {mode}")


if __name__ == "__main__":
    main()
