"""Language model clients.

AzureClient talks to Azure OpenAI. FakeClient is a stand-in that needs no
network or key, so tests and UI work can run without cost. It is not a
language model: its "embeddings" only count shared words, and its "answers"
just repeat the first source.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Protocol

from .config import Settings


class LLMClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

    def chat(self, system: str, user: str) -> str: ...


class AzureClient:
    def __init__(self, settings: Settings) -> None:
        missing = [
            name
            for name, value in {
                "AZURE_OPENAI_ENDPOINT": settings.azure_endpoint,
                "AZURE_OPENAI_API_KEY": settings.azure_api_key,
                "AZURE_OPENAI_CHAT_DEPLOYMENT": settings.chat_deployment,
                "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": settings.embedding_deployment,
            }.items()
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Missing settings in backend/.env: " + ", ".join(missing) + ". See .env.example, or set USE_FAKE_LLM=1."
            )
        from openai import AzureOpenAI

        self._client = AzureOpenAI(
            azure_endpoint=settings.azure_endpoint,
            api_key=settings.azure_api_key,
            api_version=settings.azure_api_version,
        )
        self._chat_deployment = settings.chat_deployment
        self._embedding_deployment = settings.embedding_deployment

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self._client.embeddings.create(model=self._embedding_deployment, input=texts)
        return [item.embedding for item in response.data]

    def chat(self, system: str, user: str) -> str:
        response = self._client.chat.completions.create(
            model=self._chat_deployment,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            response_format={"type": "json_object"},
            max_completion_tokens=1500,
        )
        return response.choices[0].message.content or ""


class FakeClient:
    """Deterministic stand-in used when USE_FAKE_LLM=1 and in tests."""

    DIMENSIONS = 1024

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.DIMENSIONS
        for word in re.findall(r"\w+", text.lower()):
            if len(word) < 3:
                continue
            bucket = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16) % self.DIMENSIONS
            vector[bucket] += 1.0
        norm = math.sqrt(sum(v * v for v in vector)) or 1.0
        return [v / norm for v in vector]

    def chat(self, system: str, user: str) -> str:
        match = re.search(r"\[Kilde 1\][^\n]*\n(?:[^\n]*\n)*?Tekst:\n(.*?)(?=\n\[Kilde \d+\]|\n---|\Z)", user, re.DOTALL)
        lines = []
        if match:
            lines = [line.lstrip("-0123456789. ") for line in match.group(1).splitlines() if line and not line.startswith("## ")]
        return json.dumps(
            {
                "found": bool(lines),
                "intro": "Testmodus uten språkmodell. Dette er tekst hentet rett fra den første kilden:",
                "steps": lines[:4],
                "closing": "",
                "used_sources": [1] if lines else [],
            },
            ensure_ascii=False,
        )


def get_client(settings: Settings) -> LLMClient:
    return FakeClient() if settings.use_fake_llm else AzureClient(settings)
