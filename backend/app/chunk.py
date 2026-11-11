"""Split pages into chunks that are small enough to search and to put in a prompt.

Each chunk keeps the page title, the nearest heading and the URL, so an answer
can always point back to where the text came from.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .scrape import Page

MAX_CHARS = 1000
MIN_CHARS = 300


@dataclass
class Chunk:
    id: str
    page_id: str
    topic: str
    url: str
    title: str
    heading: str
    text: str


def _split_long(text: str, max_chars: int) -> list[str]:
    """Split one very long paragraph on sentence boundaries."""
    if len(text) <= max_chars:
        return [text]
    parts: list[str] = []
    current = ""
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        if current and len(current) + len(sentence) + 1 > max_chars:
            parts.append(current)
            current = sentence
        else:
            current = f"{current} {sentence}".strip()
    if current:
        parts.append(current)
    # A single sentence can still be too long. Cut it hard as a last resort.
    return [part[i : i + max_chars] for part in parts for i in range(0, len(part), max_chars)]


def chunk_page(page: Page, *, max_chars: int = MAX_CHARS, min_chars: int = MIN_CHARS) -> list[Chunk]:
    chunks: list[Chunk] = []
    lines: list[str] = []
    size = 0
    heading = ""  # Heading in force for the chunk being built.
    current_heading = ""  # Latest heading seen on the page.

    def flush() -> None:
        nonlocal lines, size
        body = "\n".join(lines).strip()
        # A chunk with only headings carries no guidance.
        if body and any(not line.startswith("## ") for line in lines):
            chunks.append(
                Chunk(
                    id=f"{page.id}-{len(chunks) + 1}",
                    page_id=page.id,
                    topic=page.topic,
                    url=page.url,
                    title=page.title,
                    heading=heading,
                    text=body,
                )
            )
        lines, size = [], 0

    for unit in page.units:
        if unit.kind == "heading":
            current_heading = unit.text
            # Start a new chunk at a heading once the current one has enough text.
            if size >= min_chars:
                flush()
            if not lines:
                heading = current_heading
            lines.append(f"## {unit.text}")
            continue
        for part in _split_long(unit.text, max_chars):
            if size and size + len(part) > max_chars:
                # A heading at the very end belongs to the text that follows it.
                carried: list[str] = []
                while lines and lines[-1].startswith("## "):
                    carried.insert(0, lines.pop())
                flush()
                lines.extend(carried)
                heading = current_heading
            lines.append(part)
            size += len(part)
    flush()
    return chunks


def chunk_pages(pages: list[Page]) -> list[Chunk]:
    return [chunk for page in pages for chunk in chunk_page(page)]
