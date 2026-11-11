"""A small local vector store.

Chunks are kept in a JSON file and their embeddings in a NumPy file. Search is
cosine similarity between the question vector and every chunk vector, which is
fast enough for a few hundred chunks.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from .chunk import Chunk


@dataclass
class Hit:
    chunk: Chunk
    score: float


class VectorStore:
    def __init__(self, chunks: list[Chunk], embeddings: np.ndarray) -> None:
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks and embeddings must match")
        self.chunks = chunks
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        self._normalised = embeddings / norms
        self._embeddings = embeddings

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query_embedding: list[float], top_k: int = 4) -> list[Hit]:
        if not self.chunks:
            return []
        query = np.asarray(query_embedding, dtype=np.float32)
        norm = np.linalg.norm(query)
        if norm == 0:
            return []
        scores = self._normalised @ (query / norm)
        order = np.argsort(scores)[::-1][:top_k]
        return [Hit(self.chunks[i], float(scores[i])) for i in order]

    def save(self, index_dir: Path) -> None:
        index_dir.mkdir(parents=True, exist_ok=True)
        (index_dir / "chunks.json").write_text(
            json.dumps([asdict(c) for c in self.chunks], ensure_ascii=False, indent=2), encoding="utf-8"
        )
        np.save(index_dir / "embeddings.npy", self._embeddings)

    @classmethod
    def load(cls, index_dir: Path) -> "VectorStore":
        chunks_file = index_dir / "chunks.json"
        if not chunks_file.exists():
            raise FileNotFoundError(f"No index in {index_dir}. Run `python -m app.ingest` first.")
        chunks = [Chunk(**c) for c in json.loads(chunks_file.read_text(encoding="utf-8"))]
        embeddings = np.load(index_dir / "embeddings.npy")
        return cls(chunks, embeddings)
