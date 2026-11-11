"""Tests for the HTTP API, using the fake client and a tiny in-memory index."""

from __future__ import annotations

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import main
from app.chunk import Chunk
from app.config import Settings
from app.llm import FakeClient
from app.store import VectorStore


@pytest.fixture
def client(monkeypatch):
    chunks = [
        Chunk("a-1", "a", "bankid", "https://example.org/passord", "Glemt passord", "", "Har du glemt passordet til BankID, lager du et nytt i BankID-appen."),
        Chunk("b-1", "b", "svindel", "https://example.org/sms", "SMS-svindel", "", "Svindlere sender falske meldinger på SMS med lenker."),
    ]
    fake = FakeClient()
    store = VectorStore(chunks, np.asarray(fake.embed([c.text for c in chunks]), dtype=np.float32))
    settings = Settings("", "", "", "", "", use_fake_llm=True, top_k=2, min_score=0.2)
    monkeypatch.setattr(main, "get_store", lambda: store)
    monkeypatch.setattr(main, "get_llm", lambda: fake)
    monkeypatch.setattr(main, "get_settings", lambda: settings)
    return TestClient(main.app)


def test_health(client):
    assert client.get("/api/health").json() == {"status": "ok", "chunks": 2, "fake_llm": True}


def test_suggestions_are_norwegian_questions(client):
    data = client.get("/api/suggestions").json()
    assert len(data["suggestions"]) >= 4
    assert "BankID" in data["reminder"]


def test_ask_returns_answer_with_source(client):
    response = client.post("/api/ask", json={"question": "Jeg har glemt passordet til BankID"})
    assert response.status_code == 200
    data = response.json()
    assert data["found"] is True
    assert data["sources"][0] == {"title": "Glemt passord", "url": "https://example.org/passord"}
    assert set(data) == {"found", "intro", "steps", "closing", "sources"}


def test_ask_out_of_scope_gives_honest_fallback(client):
    data = client.post("/api/ask", json={"question": "plommetre gressklipper"}).json()
    assert data["found"] is False and data["sources"] == [] and "vet jeg dessverre ikke" in data["intro"]


@pytest.mark.parametrize("question", ["", "   ", "a" * 501])
def test_ask_rejects_empty_and_too_long_questions(client, question):
    assert client.post("/api/ask", json={"question": question}).status_code == 422


def test_ask_without_index_returns_503(client, monkeypatch):
    def missing():
        raise FileNotFoundError

    monkeypatch.setattr(main, "get_store", missing)
    response = client.post("/api/ask", json={"question": "Hei"})
    assert response.status_code == 503 and "ikke bygget" in response.json()["detail"]


def test_provider_errors_do_not_leak_details(client, monkeypatch):
    class Broken(FakeClient):
        def chat(self, system, user):
            raise ValueError("secret-key-123 rejected")

    monkeypatch.setattr(main, "get_llm", lambda: Broken())
    response = client.post("/api/ask", json={"question": "glemt passord BankID"})
    assert response.status_code == 502 and "secret" not in response.text
