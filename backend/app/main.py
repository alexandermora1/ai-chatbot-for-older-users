"""FastAPI app. Questions are answered in memory and are never logged or stored.

Run from the backend folder:
    uvicorn app.main:app --reload
"""

from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import INDEX_DIR, get_settings
from .llm import LLMClient, get_client
from .rag import SAFETY_REMINDER, SUGGESTIONS, answer_question
from .store import VectorStore

app = FastAPI(title="AI chatbot for older users", docs_url="/api/docs", openapi_url="/api/openapi.json")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)


class SourceOut(BaseModel):
    title: str
    url: str


class AskResponse(BaseModel):
    found: bool
    intro: str
    steps: list[str]
    closing: str
    sources: list[SourceOut]


@lru_cache
def get_store() -> VectorStore:
    return VectorStore.load(INDEX_DIR)


@lru_cache
def get_llm() -> LLMClient:
    return get_client(get_settings())


@app.get("/api/health")
def health() -> dict:
    settings = get_settings()
    try:
        chunks = len(get_store())
    except FileNotFoundError:
        chunks = 0
    return {"status": "ok", "chunks": chunks, "fake_llm": settings.use_fake_llm}


@app.get("/api/suggestions")
def suggestions() -> dict:
    return {"suggestions": SUGGESTIONS, "reminder": SAFETY_REMINDER}


@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    if not request.question.strip():
        raise HTTPException(status_code=422, detail="Skriv et spørsmål først.")
    settings = get_settings()
    try:
        store = get_store()
    except FileNotFoundError:
        raise HTTPException(status_code=503, detail="Kunnskapsbasen er ikke bygget ennå.") from None
    try:
        answer = answer_question(
            request.question, store=store, client=get_llm(), top_k=settings.top_k, min_score=settings.min_score
        )
    except RuntimeError as error:  # Missing configuration.
        raise HTTPException(status_code=503, detail=str(error)) from None
    except Exception:
        # Do not leak details from the provider, and do not log the question.
        raise HTTPException(status_code=502, detail="Jeg får ikke kontakt med språkmodellen akkurat nå.") from None
    return AskResponse(**asdict(answer))
