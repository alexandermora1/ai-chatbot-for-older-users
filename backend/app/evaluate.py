"""Run all test questions and write the answers to a CSV file for manual review.

The script checks two things automatically: whether the assistant answered or
declined as expected, and whether the top source has the expected topic. Whether
an answer is correct and in plain language must be judged by a person, in the
empty columns of the CSV file.

Usage (from the backend folder):
    python -m app.evaluate
"""

from __future__ import annotations

import csv
import json
from datetime import datetime

from .config import EVAL_DIR, INDEX_DIR, get_settings
from .llm import get_client
from .rag import answer_question
from .store import VectorStore

COLUMNS = [
    "id",
    "topic",
    "question",
    "expect_found",
    "found",
    "found_as_expected",
    "source_topic_as_expected",
    "answer",
    "sources",
    "correct (riktig/delvis/feil)",
    "plain language (ja/nei)",
    "notes",
]


def main() -> None:
    settings = get_settings()
    store = VectorStore.load(INDEX_DIR)
    client = get_client(settings)
    topic_by_url = {chunk.url: chunk.topic for chunk in store.chunks}
    questions = json.loads((EVAL_DIR / "questions.json").read_text(encoding="utf-8"))["questions"]

    rows = []
    for item in questions:
        answer = answer_question(
            item["question"], store=store, client=client, top_k=settings.top_k, min_score=settings.min_score
        )
        found_ok = answer.found == item["expect_found"]
        if answer.found and item["expect_found"]:
            topic_ok = "yes" if topic_by_url.get(answer.sources[0].url) == item["topic"] else "no"
        else:
            topic_ok = ""
        text = answer.intro
        if answer.steps:
            text += "\n" + "\n".join(f"{n}. {step}" for n, step in enumerate(answer.steps, start=1))
        if answer.closing:
            text += "\n" + answer.closing
        rows.append(
            {
                "id": item["id"],
                "topic": item["topic"],
                "question": item["question"],
                "expect_found": item["expect_found"],
                "found": answer.found,
                "found_as_expected": "yes" if found_ok else "no",
                "source_topic_as_expected": topic_ok,
                "answer": text,
                "sources": "\n".join(source.url for source in answer.sources),
                "correct (riktig/delvis/feil)": "",
                "plain language (ja/nei)": "",
                "notes": "",
            }
        )
        print(f"{item['id']:>2}  {'ok  ' if found_ok else 'DIFF'}  {item['question']}")

    path = EVAL_DIR / f"results-{datetime.now():%Y%m%d-%H%M}.csv"
    # utf-8-sig makes Excel show Norwegian letters correctly.
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    as_expected = sum(row["found_as_expected"] == "yes" for row in rows)
    print(f"\nAnswered or declined as expected: {as_expected}/{len(rows)}")
    if settings.use_fake_llm:
        print("NOTE: this run used the FAKE stand-in, so the numbers say nothing about real quality.")
    print(f"Wrote {path}. Fill in the empty columns by hand.")


if __name__ == "__main__":
    main()
