"""Tests for scraping, chunking, the vector store and the RAG logic. No network or Azure key is needed."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from app.chunk import Chunk, chunk_page
from app.llm import FakeClient
from app.rag import NOT_FOUND_TEXT, PERSONAL_DATA_TEXT, answer_question, build_user_prompt, contains_personal_number
from app.scrape import Page, Unit, extract, load_pages, load_sources, save_page
from app.store import Hit, VectorStore

FIXTURE = Path(__file__).parent / "fixtures" / "page.html"


def make_page() -> Page:
    return extract(FIXTURE.read_text(encoding="utf-8"), id="demo", topic="bankid", url="https://example.org/glemt")


def make_chunk(id: str, text: str, url: str = "https://example.org/a", title: str = "Tittel") -> Chunk:
    return Chunk(id=id, page_id="p", topic="bankid", url=url, title=title, heading="", text=text)


def make_store(chunks: list[Chunk]) -> VectorStore:
    client = FakeClient()
    return VectorStore(chunks, np.asarray(client.embed([c.text for c in chunks]), dtype=np.float32))


class ScriptedClient(FakeClient):
    """Uses the fake embeddings, but returns a fixed chat reply and records the prompts."""

    def __init__(self, reply: str) -> None:
        self.reply = reply
        self.calls: list[tuple[str, str]] = []

    def chat(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        return self.reply


# --- scraping ---


def test_extract_keeps_content_and_drops_noise():
    page = make_page()
    texts = [u.text for u in page.units]
    assert page.title == "Glemt passord"
    assert "Har du glemt passordet ditt, kan du lage et nytt selv." in texts
    joined = " ".join(texts)
    for noise in ["Meny", "Bunntekst", "Skjema", "console.log", "color: red"]:
        assert noise not in joined


def test_extract_numbers_ordered_lists_and_removes_duplicates():
    texts = [u.text for u in make_page().units]
    assert "1. Åpne appen på telefonen." in texts
    assert "2. Velg «Glemt passord»." in texts
    assert "3. Lag et nytt passord og skriv det to ganger." in texts
    assert texts.count("- Gi aldri passordet ditt til andre.") == 1


def test_pages_round_trip_to_disk(tmp_path):
    page = make_page()
    save_page(page, tmp_path)
    loaded = load_pages(tmp_path)
    assert len(loaded) == 1
    assert loaded[0].units == page.units and loaded[0].url == page.url


def test_load_sources_skips_disabled(tmp_path):
    path = tmp_path / "sources.json"
    path.write_text(
        json.dumps(
            {
                "sources": [
                    {"id": "a", "topic": "bankid", "url": "https://example.org/a", "enabled": True},
                    {"id": "b", "topic": "bankid", "url": "https://example.org/b", "enabled": False},
                ]
            }
        )
    )
    assert [s["id"] for s in load_sources(path)] == ["a"]


def test_real_sources_file_is_valid():
    from app.config import SOURCES_FILE

    sources = load_sources(SOURCES_FILE)
    assert len(sources) >= 20
    assert len({s["id"] for s in sources}) == len(sources)
    assert {s["topic"] for s in sources} == {"bankid", "svindel", "helsenorge"}
    assert all(s["url"].startswith("https://") for s in sources)


# --- chunking ---


def test_small_page_becomes_one_chunk_with_metadata():
    chunks = chunk_page(make_page())
    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.url == "https://example.org/glemt"
    assert chunk.title == "Glemt passord"
    assert "## Slik gjør du det" in chunk.text
    assert "1. Åpne appen på telefonen." in chunk.text


def test_long_page_is_split_within_limit_and_keeps_all_text():
    units = [Unit("heading", "Start")]
    for section in range(6):
        units.append(Unit("heading", f"Del {section}"))
        units.extend(Unit("text", f"Avsnitt {section}-{i}. " + "ord " * 60) for i in range(3))
    page = Page(id="lang", topic="svindel", url="https://example.org/lang", title="Lang side", fetched="2026-01-01", units=units)
    chunks = chunk_page(page, max_chars=1000, min_chars=300)
    assert len(chunks) > 1
    assert [c.id for c in chunks] == [f"lang-{i}" for i in range(1, len(chunks) + 1)]
    for chunk in chunks:
        body = "\n".join(line for line in chunk.text.splitlines() if not line.startswith("## "))
        assert len(body) <= 1000 + 10
        assert not chunk.text.splitlines()[-1].startswith("## "), "a chunk must not end with a heading"
    all_text = "\n".join(c.text for c in chunks)
    for section in range(6):
        for i in range(3):
            assert f"Avsnitt {section}-{i}." in all_text


def test_very_long_paragraph_is_split():
    text = " ".join(f"Setning nummer {i} er her." for i in range(200))
    page = Page(id="x", topic="bankid", url="https://example.org/x", title="X", fetched="2026-01-01", units=[Unit("text", text)])
    chunks = chunk_page(page, max_chars=500)
    assert len(chunks) > 5
    assert all(len(c.text) <= 500 for c in chunks)


def test_heading_only_page_gives_no_chunks():
    page = Page(id="h", topic="bankid", url="https://example.org/h", title="H", fetched="2026-01-01", units=[Unit("heading", "Bare tittel")])
    assert chunk_page(page) == []


# --- vector store ---


def test_search_ranks_the_matching_chunk_first(tmp_path):
    chunks = [
        make_chunk("1", "Slik lager du nytt passord i BankID-appen når du har glemt passordet."),
        make_chunk("2", "Svindlere sender falske meldinger med lenker på SMS."),
        make_chunk("3", "På Helsenorge kan du se timeavtaler og resepter."),
    ]
    store = make_store(chunks)
    client = FakeClient()
    hits = store.search(client.embed(["falske SMS meldinger med lenker"])[0], top_k=2)
    assert len(hits) == 2
    assert hits[0].chunk.id == "2"
    assert hits[0].score > hits[1].score

    store.save(tmp_path)
    reloaded = VectorStore.load(tmp_path)
    assert [c.id for c in reloaded.chunks] == ["1", "2", "3"]
    assert reloaded.search(client.embed(["glemt passord BankID-appen"])[0], top_k=1)[0].chunk.id == "1"


def test_search_handles_empty_query_vector():
    store = make_store([make_chunk("1", "Noe tekst om passord")])
    assert store.search([0.0] * FakeClient.DIMENSIONS) == []


# --- RAG ---

CHUNKS = [
    make_chunk("1", "Har du glemt passordet til BankID, kan du lage et nytt passord i BankID-appen.", "https://example.org/passord", "Glemt passord"),
    make_chunk("2", "Svindlere sender falske meldinger på SMS med lenker. Ikke trykk på lenken.", "https://example.org/sms", "SMS-svindel"),
]


def test_answer_uses_only_sources_the_model_reports():
    client = ScriptedClient(json.dumps({"found": True, "intro": "Du kan lage et nytt passord.", "steps": ["Åpne appen.", " "], "closing": "Husk koden.", "used_sources": [1]}))
    answer = answer_question("Jeg har glemt passordet til BankID", store=make_store(CHUNKS), client=client, top_k=2, min_score=0.0)
    assert answer.found
    assert answer.steps == ["Åpne appen."]
    assert [s.url for s in answer.sources] == ["https://example.org/passord"]
    system, user = client.calls[0]
    assert "Svar bare ut fra kildene" in system
    assert "[Kilde 1] Glemt passord" in user and "Jeg har glemt passordet til BankID" in user


def test_answer_always_has_a_source_even_if_model_reports_none():
    client = ScriptedClient('```json\n{"found": true, "intro": "Svar.", "steps": [], "used_sources": [99]}\n```')
    answer = answer_question("glemt passord BankID", store=make_store(CHUNKS), client=client, top_k=1, min_score=0.0)
    assert answer.found and len(answer.sources) == 1


def test_no_relevant_chunk_means_no_model_call():
    client = ScriptedClient("{}")
    answer = answer_question("xyzzy qwerty", store=make_store(CHUNKS), client=client, min_score=0.2)
    assert not answer.found and answer.intro == NOT_FOUND_TEXT and answer.sources == []
    assert client.calls == []


def test_model_saying_not_found_or_garbage_gives_fallback():
    store = make_store(CHUNKS)
    for reply in ['{"found": false, "intro": "", "steps": []}', "dette er ikke json", '{"found": true, "intro": "  "}', "[1, 2]"]:
        answer = answer_question("glemt passord BankID", store=store, client=ScriptedClient(reply), min_score=0.0)
        assert not answer.found and answer.intro == NOT_FOUND_TEXT


def test_personal_number_is_stopped_before_any_model_call():
    assert contains_personal_number("mitt nummer er 01020312345")
    assert contains_personal_number("010203 12345 er nummeret")
    assert not contains_personal_number("ring 22 33 44 55 eller 02800")
    assert not contains_personal_number("ordre 123456789012345")
    client = ScriptedClient("{}")
    client.embed = lambda texts: (_ for _ in ()).throw(AssertionError("must not embed"))  # type: ignore[method-assign]
    answer = answer_question("Fødselsnummeret mitt er 01020312345, kan du logge inn?", store=make_store(CHUNKS), client=client)
    assert not answer.found and answer.intro == PERSONAL_DATA_TEXT


def test_fake_client_answers_from_first_source():
    hits = [Hit(CHUNKS[1], 0.9), Hit(CHUNKS[0], 0.5)]
    data = json.loads(FakeClient().chat("system", build_user_prompt("Er dette svindel?", hits)))
    assert data["found"] and data["used_sources"] == [1]
    assert "Svindlere sender falske meldinger" in data["steps"][0]
