# NEUROSTAGE AI — AI Service

The AI service powering **NEUROSTAGE AI**, an internship-management platform developed for SOTETEL. This repository contains the Python/FastAPI component that provides document processing, semantic matching, AI-assisted internship-subject generation, and retrieval-augmented question answering (RAG).

> **Repository scope:** This is the AI service, not the complete NEUROSTAGE application. The main application backend (NestJS) calls this service through internal HTTP endpoints.

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [API endpoints](#api-endpoints)
- [Requirements](#requirements)
- [Configuration](#configuration)
- [Run with Docker Compose](#run-with-docker-compose)
- [Run locally](#run-locally)
- [NestJS integration](#nestjs-integration)
- [Health check and API documentation](#health-check-and-api-documentation)
- [Security notes](#security-notes)
- [Troubleshooting](#troubleshooting)

## Features

### 1. CV and document text extraction

Extracts and normalizes text from:

- PDF files using `pdfplumber`.
- DOCX files using `python-docx`.
- JPG/JPEG and PNG images using Tesseract OCR through `pytesseract`.

The OCR configuration includes French, Arabic, and English language data. The extraction endpoint also returns a word count and detected language.

### 2. Semantic CV-to-subject matching

- Generates embeddings for student CVs and validated internship subjects.
- Stores vectors in PostgreSQL using `pgvector`.
- Retrieves the five closest subjects using cosine similarity.
- Returns similarity scores and overlapping keywords to help explain each suggestion.

### 3. AI-assisted internship-subject generation

Generates a structured internship-subject draft from one or more student CVs and optional supervisor context. The response contains a title, description, technologies, prerequisites, and academic level.

The AI service returns a draft; the main application remains responsible for its business workflow and validation.

### 4. Retrieval-Augmented Generation (RAG)

- Extracts text from knowledge documents.
- Splits document text into overlapping chunks.
- Creates and stores an embedding for each chunk.
- Retrieves relevant chunks when a user asks a question.
- Generates an answer using the retrieved context and returns source document names and excerpts.

Supported document formats follow the extraction capabilities listed above.

## Architecture

The service is built with **FastAPI** and is designed to work alongside the NEUROSTAGE NestJS backend.

```text
                 NEUROSTAGE application
                         NestJS
                           |
                 Internal HTTP requests
               (X-Internal-Secret header)
                           |
                           v
                  FastAPI AI Service
                  /      |       \
             Extract   Embeddings  RAG / Generation
                |          |             |
                |          v             v
                |     Ollama or an OpenAI-compatible API
                |                        |
                +------------------------+
                           |
                           v
                   PostgreSQL + pgvector
             student_embeddings / subject_embeddings
                         rag_chunks
```

The service connects to PostgreSQL through an asynchronous `asyncpg` connection pool. At startup, it enables the `vector` extension if needed and creates the embedding tables and cosine-similarity indexes used by the service.

For student CV processing, the service can notify NestJS through an internal callback after the embedding has been stored. The upload directory must therefore be accessible to both applications when they exchange files by path.

## Technology stack

| Area | Technology |
|---|---|
| API framework | FastAPI |
| ASGI server | Uvicorn |
| Language | Python 3.11 |
| PDF extraction | pdfplumber |
| DOCX extraction | python-docx |
| OCR | Tesseract OCR, pytesseract, Pillow |
| Embedding and generation client | OpenAI Python SDK (also used with Ollama's OpenAI-compatible API) |
| Default embedding model | `nomic-embed-text` |
| Default generation model | `llama3.2` |
| Vector storage and search | PostgreSQL, pgvector |
| Database driver | asyncpg |
| Containerization | Docker, Docker Compose |

## API endpoints

All endpoints below, except `GET /health`, require the internal shared secret in the `X-Internal-Secret` request header.

| Method | Endpoint | Purpose |
|---|---|---|
| `GET` | `/health` | Check service, database/pgvector, OCR, and LLM configuration status. |
| `POST` | `/extract` | Extract and normalize text from a supported file. |
| `POST` | `/embed/student` | Generate and store a student's CV embedding. |
| `POST` | `/embed/subject` | Generate and store an internship subject embedding. |
| `POST` | `/embed/subjects/bulk` | Index multiple internship subjects. |
| `GET` | `/suggest/{user_id}` | Return the five closest subjects for a processed student CV. |
| `POST` | `/generate/subject-from-cv` | Generate an internship-subject draft from student CVs. |
| `POST` | `/rag/documents` | Ingest a document into the RAG knowledge base. |
| `POST` | `/rag/query` | Answer a question using retrieved knowledge chunks. |

See [`INTEGRATION.md`](./INTEGRATION.md) for request and response examples and the corresponding NestJS integration flow.

## Requirements

For local development:

- Python 3.11 or newer.
- PostgreSQL with the `pgvector` extension available.
- Tesseract OCR installed with French (`fra`), Arabic (`ara`), and English (`eng`) language data.
- An LLM provider compatible with the configured client:
  - Ollama with the configured embedding and generation models; or
  - OpenAI API credentials and compatible model names.
- Access to the NestJS backend if you need the CV-processing callback or full platform integration.

Docker Compose uses the `pgvector/pgvector:pg16` image and the repository Dockerfile, which installs Tesseract and the required language packs in the AI container.

## Configuration

Create your local environment file from the template:

```bash
cp .env.example .env
```

Update the values for your environment. The main variables are:

| Variable | Description |
|---|---|
| `DATABASE_URL` | PostgreSQL connection URL. |
| `INTERNAL_SECRET` | Shared secret used to authenticate internal requests. It must match the value configured in NestJS. |
| `NESTJS_INTERNAL_URL` | Base URL used by FastAPI for internal NestJS callbacks. |
| `UPLOAD_DIR` | Directory where uploaded files are available to the service. |
| `UPLOAD_BASE_URL` | Base URL of the application serving uploaded files, where required. |
| `LLM_PROVIDER` | Provider selector. The default is `ollama`; the code also supports `openai`. |
| `LLM_BASE_URL` | OpenAI-compatible API base URL. Used for the Ollama endpoint when `LLM_PROVIDER=ollama`. |
| `EMBEDDING_MODEL` | Model used to create embeddings. |
| `GENERATION_MODEL` | Model used for subject generation and RAG answers. |
| `EMBEDDING_DIMENSIONS` | Vector size expected by the PostgreSQL embedding columns. It must match the embedding model output. |
| `OPENAI_API_KEY` | API key when using the OpenAI provider. |
| `ENVIRONMENT` | Runtime environment label. |

The checked-in `.env.example` is configured for local Ollama development with `nomic-embed-text`, `llama3.2`, and 768-dimensional embeddings. If you change embedding models, make sure `EMBEDDING_DIMENSIONS` matches the model's actual output size and is consistent with the vectors already stored in the database.

### Ollama setup

For the default local configuration, install and run Ollama on the host machine, then pull the configured models:

```bash
ollama pull nomic-embed-text
ollama pull llama3.2
```

Make sure the FastAPI process or container can reach the Ollama OpenAI-compatible API at the URL configured by `LLM_BASE_URL`. When running the AI service inside Docker, the host URL may differ by operating system and Docker configuration.

### OpenAI provider

To use OpenAI instead, configure the provider and credentials in `.env`:

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=your_api_key
EMBEDDING_MODEL=text-embedding-3-small
GENERATION_MODEL=gpt-4o-mini
EMBEDDING_DIMENSIONS=1536
```

Use model names and vector dimensions that are valid for your account and deployment. Changing embedding dimensions may require recreating or migrating the existing vector tables.

## Run with Docker Compose

The repository includes a `Dockerfile` and `docker-compose.yml`. The Compose configuration declares `neurostage_network` as an **external Docker network**, so create it first if it does not already exist:

```bash
docker network create neurostage_network
```

Then create and configure `.env`:

```bash
cp .env.example .env
```

Set a strong, unique `INTERNAL_SECRET` and adjust the provider and connection settings. Start the AI service and its PostgreSQL database:

```bash
docker compose up --build -d
```

View logs:

```bash
docker compose logs -f ai
```

Stop the containers:

```bash
docker compose down
```

The Compose file defines persistent Docker volumes for PostgreSQL data and uploaded files. `docker compose down` does not remove these volumes; do not use `docker compose down -v` unless you intentionally want to delete the persisted data.

**Before production use:** The current Compose file contains development database credentials directly in its service definitions. Replace them with securely supplied environment variables or secrets in both the database and AI service configurations. The Compose file also sets the AI service's database URL explicitly, so changing `DATABASE_URL` in `.env` alone will not override that Compose value.

**Integration note:** The Compose file in this repository starts the AI service and PostgreSQL; it does not define the NestJS application container. The configured NestJS callback URL and shared upload directory must be reachable from the AI container. For full integration, connect the NestJS service to the same Docker network and mount the upload volume consistently. The Compose network must be available to the other application services as well.

## Run locally

1. Create and activate a virtual environment:

   ```bash
   python -m venv .venv
   ```

   macOS/Linux:

   ```bash
   source .venv/bin/activate
   ```

   Windows PowerShell:

   ```powershell
   .venv\Scripts\Activate.ps1
   ```

2. Install Python dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Install Tesseract OCR and the French, Arabic, and English language packs using your operating system's package manager.

4. Create `.env` from `.env.example` and configure `DATABASE_URL`, `INTERNAL_SECRET`, and your LLM provider settings. Make sure PostgreSQL is running and the configured database user can create the `vector` extension and the service tables/indexes.

5. Start the API:

   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8001
   ```

The API will be available at `http://localhost:8001`.

## NestJS integration

The NestJS backend calls the protected FastAPI routes using the `X-Internal-Secret` header. Configure the following values in the NestJS environment:

```dotenv
AI_SERVICE_URL=http://neurostage_ai:8001
INTERNAL_SECRET=the_same_secret_used_by_the_ai_service
```

The service expects file paths passed by NestJS to exist inside the AI container's mounted upload directory. Both services must therefore share access to the same uploaded files. The callback URL configured in `NESTJS_INTERNAL_URL` must resolve from the AI container.

For the complete endpoint contracts, payload fields, callback behavior, and role-level NestJS integration notes, see [`INTEGRATION.md`](./INTEGRATION.md).

## Health check and API documentation

Once the service is running, check its health:

```bash
curl http://localhost:8001/health
```

FastAPI's interactive API documentation is available at:

- Swagger UI: `http://localhost:8001/docs`
- ReDoc: `http://localhost:8001/redoc`

The health endpoint reports the configured LLM provider and checks the database/pgvector extension, Tesseract availability, and LLM configuration. A `degraded` status means one or more checks did not pass; inspect the service logs and environment configuration.

## Security notes

- Do not commit `.env` files, API keys, database credentials, or production secrets.
- Replace all example credentials and use a strong, randomly generated `INTERNAL_SECRET` shared only by trusted internal services.
- Keep protected AI endpoints off the public internet unless they are behind an appropriate trusted backend or security boundary.
- Restrict database and upload-volume access to the services that need it.
- Treat uploaded CVs and knowledge documents as sensitive personal or business data.

## Troubleshooting

| Symptom | Things to check |
|---|---|
| Database connection fails during startup | Verify `DATABASE_URL`, PostgreSQL availability, Docker network connectivity, and database credentials. |
| `pgvector` extension cannot be created | Confirm the PostgreSQL image supports pgvector and the database user has permission to create the extension. |
| Ollama connection errors | Confirm Ollama is running, the model has been pulled, and `LLM_BASE_URL` is reachable from the AI container. |
| OCR does not recognize French, Arabic, or English text | Check that the corresponding Tesseract language packs are installed. |
| File not found during extraction | Ensure NestJS and FastAPI use the same mounted upload directory and that the path exists inside the AI container. |
| Protected endpoint returns an authentication error | Check that the `X-Internal-Secret` header matches `INTERNAL_SECRET` exactly. |
| CV processing does not update the NestJS profile | Check `NESTJS_INTERNAL_URL`, Docker network access, the callback route, and service logs. |

---

Developed as part of the **NEUROSTAGE AI** internship-management platform project at **SOTETEL**.
