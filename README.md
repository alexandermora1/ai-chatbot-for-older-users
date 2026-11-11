# AI chatbot for older users

A Norwegian-language assistant that helps older people with three everyday digital topics: **BankID and login**, **scams and online safety**, and **Helsenorge**. It answers only from public guidance pages, in short numbered steps in plain language, and always links to the source.

This is a practice project for learning retrieval augmented generation (RAG) end to end. It is not a product, and its answers can be wrong.

> **Status: first version, not yet run against real sources or a real model.**
> The code is tested with an offline stand-in for the language model. The first real run (fetching the pages and calling Azure OpenAI) still has to be done on a local machine. See [What has and has not been verified](#what-has-and-has-not-been-verified).

## What it does

- Answers questions about the three topics in Norwegian plain language, as numbered steps.
- Shows a link to the source under every answer.
- Offers suggested questions as large buttons, so the user does not have to type.
- Says honestly when it does not know, or when a question is outside the three topics.
- Never asks for personal data. A question that contains something that looks like a national identity number is stopped before it reaches the language model.
- Stores nothing: no conversations, no logging of questions, no login.

## How it works

```
sources.json ──> scrape ──> chunk ──> embed ──> local index
                                                    │
question ──> embed ──> search top chunks ──> prompt with rules ──> answer + sources ──> React UI
```

1. **Collect** (`app/scrape.py`): fetches the pages listed in `backend/data/sources.json`, honours `robots.txt`, and strips menus, footers, scripts and forms.
2. **Chunk** (`app/chunk.py`): splits each page into pieces of up to about 1000 characters. Every chunk keeps the page title, nearest heading and URL.
3. **Embed** (`app/ingest.py`, `app/llm.py`): turns each chunk into a vector with an Azure OpenAI embedding model.
4. **Search** (`app/store.py`): a small local vector store using NumPy and cosine similarity.
5. **Answer** (`app/rag.py`): sends the best chunks and the question to a chat model with strict rules: answer only from the sources, use plain language, say when the answer is not there, never ask for personal data.
6. **Show** (`app/main.py`, `frontend/`): a FastAPI endpoint returns the answer as structured JSON, and a React page shows the steps and source links.

## Tech stack

| Part | Choice |
| --- | --- |
| Language model | Azure OpenAI (one small chat model, one embedding model) |
| Backend | Python 3.11+, FastAPI |
| Vector search | Local, NumPy |
| Frontend | React, TypeScript, Vite |
| Accessibility target | WCAG 2.2 AA |
| Visual style | Shared with the AI literacy course at [seniorki.no](https://seniorki.no): same colours, typeface, buttons and cards |

## Getting started

You need Python 3.11 or newer, Node.js 20 or newer, and an Azure OpenAI resource with one chat deployment and one embedding deployment.

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
cp .env.example .env             # then fill in your Azure values
```

`.env` holds your API key and is ignored by Git. Never commit it.

Build the knowledge base (fetches the pages and creates embeddings):

```bash
python -m app.ingest
```

Pages that could not be fetched are listed as `SKIPPED` with the reason. Try the search on its own before generating answers:

```bash
python -m app.search "Jeg har glemt BankID-passordet mitt"
```

Start the API:

```bash
uvicorn app.main:app --reload
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173.

### Running without Azure

Set `USE_FAKE_LLM=1` in `backend/.env` to use the built-in stand-in. It needs no key and costs nothing, which is useful for working on the interface. It is not a language model: it matches on shared words and repeats text from the first source.

## Tests and evaluation

```bash
cd backend
pytest                      # unit and API tests, no network or key needed
python -m app.evaluate      # runs the 25 test questions and writes a CSV
```

The evaluation writes `backend/eval/results-<time>.csv` with each answer, its sources, and empty columns to fill in by hand: is the answer correct, and is it in plain language. The script itself only checks whether the assistant answered or declined as expected.

The questions in `backend/eval/questions.json` are preliminary. They should be replaced with questions that older users actually ask.

## Settings

| Variable | Meaning |
| --- | --- |
| `AZURE_OPENAI_ENDPOINT` | Endpoint of your Azure OpenAI resource |
| `AZURE_OPENAI_API_KEY` | API key |
| `AZURE_OPENAI_API_VERSION` | API version, default `2024-10-21` |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Name of your chat deployment |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT` | Name of your embedding deployment |
| `USE_FAKE_LLM` | `1` to run without Azure |
| `TOP_K` | Number of chunks sent to the model, default 4 |
| `MIN_SCORE` | Lowest similarity a chunk needs to be used, default 0.25 |

`MIN_SCORE` is a guess and must be tuned once real embeddings exist. Use `python -m app.search` to see typical scores for good and bad matches.

## Sources and content

The knowledge base is built from public guidance pages from BankID, the Norwegian police, Nkom, Nettvett and Helsenorge. The list is in `backend/data/sources.json`.

- Fetched text and the index are saved under `backend/data/raw` and `backend/data/index`. Both are ignored by Git, so no third-party content is published in this repository.
- Check each site's terms of use before fetching.
- Only four Norwegian Helsenorge pages are enabled so far. Six English Helsenorge pages are listed with `"enabled": false` as reminders to find the Norwegian pages on the same subjects (login, prescriptions, appointments, GP, app, power of attorney).

## Privacy and safety

- Questions are processed in memory and are not logged or saved.
- The interface tells users not to enter personal data.
- Text that looks like a Norwegian national identity number is rejected before any call to Azure.
- Every page shows a reminder never to share BankID codes or passwords.
- Scam and BankID advice is high stakes. A wrong answer here can cost someone money, so answers must be reviewed before anyone relies on them.

## What has and has not been verified

Verified, using the stand-in model:

- Unit and API tests pass.
- The whole chain runs offline: ingest from saved pages, search, evaluation, API and interface.
- The interface was checked in a browser at desktop and mobile width: keyboard use, focus handling, error messages, and no horizontal scrolling at 360 px.

Not verified yet:

- Fetching the real pages. Some sites may block the request, need JavaScript, or have a layout the cleaner handles badly.
- Calls to Azure OpenAI, including whether the chosen chat model accepts the request parameters used in `app/llm.py`.
- Answer quality. Nothing is known yet about how correct or readable the real answers are.
- A full accessibility review. Automated tools such as WAVE and testing with a screen reader remain.
- Testing with older users.

## Project structure

```
backend/
  app/          scrape, chunk, llm, store, rag, ingest, search, evaluate, main (API)
  data/         sources.json (raw pages and index are created locally)
  eval/         test questions
  tests/        pytest tests
frontend/
  src/          React app (Norwegian interface)
```

## Possible next steps

- Replace the preliminary test questions and suggested questions with real ones.
- Add more Norwegian Helsenorge pages.
- Tune `MIN_SCORE`, chunk size and the system prompt based on the evaluation.
- Try Azure AI Search instead of the local vector store.
- Read answers aloud.

## Credits

The first version was written with Claude Code, steered by Alexander Mora.
