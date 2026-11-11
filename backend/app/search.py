"""Try the search from the terminal, without generating an answer.

Usage (from the backend folder):
    python -m app.search "Jeg har glemt BankID-passordet mitt"
"""

from __future__ import annotations

import sys

from .config import INDEX_DIR, get_settings
from .llm import get_client
from .store import VectorStore


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit('Usage: python -m app.search "your question"')
    question = " ".join(sys.argv[1:])
    settings = get_settings()
    store = VectorStore.load(INDEX_DIR)
    client = get_client(settings)
    hits = store.search(client.embed([question])[0], settings.top_k)
    print(f"Question: {question}\n")
    for hit in hits:
        marker = "" if hit.score >= settings.min_score else "  (below MIN_SCORE, would be ignored)"
        print(f"{hit.score:.3f}  {hit.chunk.title} > {hit.chunk.heading}{marker}")
        print(f"       {hit.chunk.url}")
        print(f"       {hit.chunk.text[:200].replace(chr(10), ' ')}...\n")


if __name__ == "__main__":
    main()
