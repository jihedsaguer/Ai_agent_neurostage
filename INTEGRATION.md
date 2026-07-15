# NEUROSTAGE AI — NestJS Integration Guide

This document tells the NestJS developer exactly what to add to connect
the NestJS backend to this FastAPI AI service.

---

## Environment variables to add to NestJS `.env`

```
AI_SERVICE_URL=http://neurostage_ai:8001   # Docker container name (NOT "ai")
INTERNAL_SECRET=same_value_as_fastapi_INTERNAL_SECRET
```

> **Important:** The FastAPI container name is `neurostage_ai` (set in docker-compose.yml).
> The old guide said `http://ai:8001` — that is wrong. Use `http://neurostage_ai:8001`.

---

## Exact request/response contracts for every endpoint

### 1. After student uploads a CV
**Trigger:** `uploadDocument()` in `profiles.service.ts` when `type === 'CV'`
**Pattern:** Fire-and-forget — never await, never throw to the student.

#### Step 1 — Extract text from the CV file

`POST /extract`

Request body:
```json
{
  "filePath": "/var/neurostage/uploads/cv_filename.pdf",
  "userId": "uuid-string",
  "fileType": "application/pdf"
}
```

Supported `fileType` values: `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `image/jpeg`, `image/png`

Success response `200`:
```json
{
  "extractedText": "Full text content...",
  "wordCount": 342,
  "language": "en"
}
```

Error responses:
- `404` `{ "error": "file_not_found", "detail": "No file at /path" }` — file not on shared volume
- `422` `{ "error": "extraction_failed", "detail": "..." }` — text under 50 chars or unreadable

#### Step 2 — Embed student profile

`POST /embed/student`

Request body:
```json
{
  "userId": "uuid-string",
  "extractedText": "Full text from step 1...",
  "skills": ["React", "Node.js"],
  "university": "Esprit",
  "specialization": "Software Engineering",
  "level": "ING3"
}
```

All fields except `userId` and `extractedText` are optional (default to empty string / empty array).

Success response `200`:
```json
{
  "success": true,
  "updatedAt": "2026-07-03T10:00:00.000000"
}
```

Error response:
- `502` `{ "error": "embedding_failed", "detail": "..." }` — Ollama/OpenAI unreachable after 3 retries

**NestJS TypeScript example:**
```typescript
// Fire-and-forget — wrap in void, do not await at top level
void (async () => {
  try {
    const extractRes = await axios.post(`${AI_SERVICE_URL}/extract`, {
      filePath: file.path,           // absolute path on shared volume
      userId: userId,
      fileType: file.mimetype,
    }, { headers: { 'X-Internal-Secret': INTERNAL_SECRET } });

    const profile = await this.getOrCreateProfile(userId);
    await axios.post(`${AI_SERVICE_URL}/embed/student`, {
      userId,
      extractedText: extractRes.data.extractedText,
      skills: profile.skills ?? [],
      university: profile.university ?? '',
      specialization: profile.specialization ?? '',
      level: profile.level ?? '',
    }, { headers: { 'X-Internal-Secret': INTERNAL_SECRET } });
  } catch (err) {
    this.logger.warn(`AI processing failed for user ${userId}: ${err.message}`);
  }
})();
```

---

### 2. After a subject is validated
**Trigger:** `subjects.service.ts` when subject `status` changes to `VALIDATED`
**Pattern:** Fire-and-forget.

`POST /embed/subject`

Request body:
```json
{
  "subjectId": "uuid-string",
  "titre": "Développement application web fullstack",
  "description": "Développer une application web avec React et Node.js",
  "techno": ["React", "Node.js", "PostgreSQL"],
  "prerequis": "JavaScript, bases de données",
  "niveau": "ING2"
}
```

Success response `200`:
```json
{
  "success": true,
  "updatedAt": "2026-07-03T10:00:00.000000"
}
```

```typescript
void axios.post(`${AI_SERVICE_URL}/embed/subject`, {
  subjectId: subject.id,
  titre: subject.titre,
  description: subject.description,
  techno: subject.techno ?? [],
  prerequis: subject.prerequis ?? '',
  niveau: subject.niveau ?? '',
}, { headers: { 'X-Internal-Secret': INTERNAL_SECRET } })
  .catch(err => this.logger.warn(`Subject embed failed: ${err.message}`));
```

---

### 3. On app startup — warm the subject index
**Trigger:** `OnModuleInit` in `app.module.ts`

`POST /embed/subjects/bulk`

Request body:
```json
{
  "subjects": [
    {
      "subjectId": "uuid-string",
      "titre": "...",
      "description": "...",
      "techno": ["React"],
      "prerequis": "...",
      "niveau": "ING2"
    }
  ]
}
```

Success response `200`:
```json
{
  "indexed": 12,
  "failed": 0,
  "duration": 4.37
}
```

`duration` is a float (seconds). Subjects that fail to embed are counted in `failed` and logged server-side — the request always returns 200 unless the pool is down.

```typescript
const subjects = await this.subjectsService.getValidatedSubjects();
await axios.post(`${AI_SERVICE_URL}/embed/subjects/bulk`, {
  subjects: subjects.map(s => ({
    subjectId: s.id,
    titre: s.titre,
    description: s.description,
    techno: s.techno ?? [],
    prerequis: s.prerequis ?? '',
    niveau: s.niveau ?? '',
  })),
}, { headers: { 'X-Internal-Secret': INTERNAL_SECRET } });
```

---

### 4. Student requests subject suggestions
**NestJS endpoint:** `GET /profiles/me/subject-suggestions`
**Role guard:** `STUDENT` only

`GET /suggest/{userId}`

- No request body
- `userId` is a UUID path parameter

Success response `200`:
```json
{
  "suggestions": [
    {
      "subjectId": "uuid-string",
      "score": 0.8731,
      "matchedKeywords": ["react", "node.js", "postgresql"]
    }
  ]
}
```

- `score` is cosine similarity (0–1, higher = better match)
- `matchedKeywords` are words that appear in both the CV and the subject text
- Returns empty array `[]` if no subjects are indexed yet (not an error)

Error responses:
- `404` `{ "error": "no_embedding", "detail": "Student CV has not been processed yet" }` — student never uploaded a CV
- `500` `{ "error": "suggestion_failed", "detail": "..." }` — DB failure

```typescript
async getSubjectSuggestions(userId: string) {
  try {
    const res = await axios.get(`${AI_SERVICE_URL}/suggest/${userId}`, {
      headers: { 'X-Internal-Secret': INTERNAL_SECRET },
    });
    return res.data;  // { suggestions: [...] }
  } catch (err) {
    if (err.response?.status === 404) {
      return { suggestions: [], message: 'Upload a CV to get subject suggestions' };
    }
    throw err;
  }
}
```

---

### 5. Generate subject draft from student CVs
**NestJS endpoint:** `POST /subjects/generate-draft`
**Role guard:** `ENCADREUR_PRO` and `ADMIN_FORMATION`

> **Note:** Both roles can call this endpoint. The distinction (DRAFT vs VALIDATED) is
> applied by NestJS when saving to the database — not by FastAPI.

`POST /generate/subject-from-cv`

Request body:
```json
{
  "studentIds": ["uuid-1", "uuid-2"],
  "encadreurId": "uuid-of-requester",
  "context": "Focused on web development and automation"
}
```

- `context` is optional (`null` accepted)
- `studentIds` must contain at least one UUID
- All student IDs must have an existing CV embedding, otherwise 404

Success response `200`:
```json
{
  "titre": "Développement d'une plateforme de monitoring réseau",
  "description": "Concevoir et développer une application...",
  "techno": ["React", "Node.js", "Grafana"],
  "prerequis": "JavaScript, notions de réseaux",
  "niveau": "ING3",
  "rawPromptUsed": "Student CV(s):\n..."
}
```

Error responses:
- `404` `{ "error": "student_not_found", "detail": "No embedding found for student(s): uuid-1" }` — student CV not processed
- `502` `{ "error": "generation_failed", "detail": "..." }` — LLM API error
- `502` `{ "error": "generation_invalid_response", "detail": "..." }` — LLM returned unparseable JSON after 2 attempts

```typescript
async generateSubjectDraft(body: GenerateDraftDto, requesterId: string) {
  const res = await axios.post(`${AI_SERVICE_URL}/generate/subject-from-cv`, {
    studentIds: body.studentIds,
    encadreurId: requesterId,
    context: body.context ?? null,
  }, { headers: { 'X-Internal-Secret': INTERNAL_SECRET } });

  // Save to GenerationIA table
  await this.generationIaRepo.save({
    type: 'SUBJECT_DRAFT',
    prompt: res.data.rawPromptUsed,
    valide_par: requesterId,
    horodatage: new Date(),
  });

  // Return the draft (without rawPromptUsed — internal field)
  const { rawPromptUsed, ...draft } = res.data;
  return draft;
}
```

---

### 6. RAG — Any user asks a question
**NestJS endpoint:** `POST /rag/query`
**Role guard:** All authenticated roles (including `encadreur_academique`)

`POST /rag/query`

Request body:
```json
{
  "question": "Quelle est la durée maximale d'un stage?",
  "userId": "uuid-of-requester"
}
```

Success response `200`:
```json
{
  "answer": "Selon le règlement intérieur...",
  "sources": [
    {
      "documentName": "reglement_stages_2024.pdf",
      "excerpt": "La durée maximale d'un stage est de 6 mois..."
    }
  ]
}
```

- If no relevant chunks found (similarity < 0.5), returns a polite "I don't have enough information" response — **still HTTP 200, not an error**.
- `sources` may be empty if the answer comes from general knowledge fallback.

Error responses:
- `502` `{ "error": "generation_failed", "detail": "..." }` — LLM API unreachable
- `500` `{ "error": "rag_failed", "detail": "..." }` — DB or embedding failure

```typescript
async ragQuery(question: string, userId: string) {
  const res = await axios.post(`${AI_SERVICE_URL}/rag/query`, {
    question,
    userId,
  }, { headers: { 'X-Internal-Secret': INTERNAL_SECRET } });
  return res.data;  // { answer, sources }
}
```

---

### 7. Admin ingests a procedure document into RAG
**NestJS endpoint:** `POST /rag/documents`
**Role guard:** `ADMIN_FORMATION` only

`POST /rag/documents`

Request body:
```json
{
  "filePath": "/var/neurostage/uploads/reglement.pdf",
  "documentName": "reglement_stages_2024.pdf",
  "documentType": "reglement"
}
```

- `filePath` must be accessible on the shared Docker volume
- `documentType` is a free-form label stored with each chunk (e.g. `"convention"`, `"reglement"`, `"guide"`)

Success response `200`:
```json
{
  "success": true,
  "chunksIndexed": 18
}
```

Error responses:
- `404` `{ "error": "file_not_found", "detail": "No file at /path" }`
- `422` `{ "error": "extraction_failed", "detail": "..." }` — unreadable document
- `500` `{ "error": "ingest_failed", "detail": "..." }` — DB failure during chunk storage

```typescript
async ingestRagDocument(filePath: string, documentName: string, documentType: string) {
  const res = await axios.post(`${AI_SERVICE_URL}/rag/documents`, {
    filePath,
    documentName,
    documentType,
  }, { headers: { 'X-Internal-Secret': INTERNAL_SECRET } });
  return res.data;  // { success: true, chunksIndexed: N }
}
```

---

## The one call FastAPI makes back to NestJS

After embedding a student CV, FastAPI fires this request asynchronously:

```
POST {NESTJS_INTERNAL_URL}/internal/profiles/{userId}/ai-processed
Header: X-Internal-Secret: <INTERNAL_SECRET>
Body: (empty)
```

This endpoint **must exist** in NestJS `profiles.controller.ts`:
- **No JWT guard** — authenticated by `X-Internal-Secret` header only
- Sets `isAiProcessed = true` on the student profile
- Returns `{ "success": true }` with HTTP 200
- FastAPI does not retry on failure — it logs a warning and continues

---

## Health check

`GET /health` — no authentication required

```json
{
  "status": "ok",
  "llm_provider": "ollama",
  "pgvector": true,
  "tesseract": true
}
```

Useful for NestJS startup checks or Docker healthchecks.

---

## Network topology in Docker

```
Frontend (React)
      ↓ HTTPS
   Nginx :443
      ↓
NestJS :3000  ←→  FastAPI :8001  (container: neurostage_ai)
      ↓                ↓
   PostgreSQL :5432 (shared — container: neurostage_postgres)
```

All three backend services must be on `neurostage_network`.
The FastAPI service joins this network as **external** (network is owned by the NestJS compose project).

---

## Shared volume

CV files and uploaded documents are stored on a named Docker volume `uploads` mounted at:
- **NestJS:** `/var/neurostage/uploads`
- **FastAPI:** `/var/neurostage/uploads` (same mount path)

**Both services must mount the same volume** so that `filePath` values passed from NestJS to FastAPI resolve to the same files.

In the NestJS `docker-compose.yml`, ensure the `ai` service is added with:
```yaml
  ai:
    image: neurostage-ai:latest        # or: build: ../Ai_agent_neurostage
    container_name: neurostage_ai
    environment:
      DATABASE_URL: postgresql://neuro_admin:neuro_password@db:5432/neurostage_db
      INTERNAL_SECRET: ${INTERNAL_SECRET}
      NESTJS_INTERNAL_URL: http://app:3000
      UPLOAD_DIR: /var/neurostage/uploads
      LLM_PROVIDER: ${LLM_PROVIDER:-ollama}
      LLM_BASE_URL: ${LLM_BASE_URL:-http://host.docker.internal:11434/v1}
      EMBEDDING_MODEL: ${EMBEDDING_MODEL:-nomic-embed-text}
      GENERATION_MODEL: ${GENERATION_MODEL:-llama3.2}
      EMBEDDING_DIMENSIONS: ${EMBEDDING_DIMENSIONS:-768}
    volumes:
      - uploads:/var/neurostage/uploads     # same volume as NestJS
    depends_on:
      db:
        condition: service_healthy
    networks:
      - neurostage_network
    restart: unless-stopped
    ports:
      - "8001:8001"                         # optional — only needed for local testing
```

---

## Switching from Ollama to OpenAI in production

Change these env vars only — no code changes needed:

```
LLM_PROVIDER=openai
LLM_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-...
EMBEDDING_MODEL=text-embedding-3-small
GENERATION_MODEL=gpt-4o-mini
EMBEDDING_DIMENSIONS=1536
```

> **Warning:** If you switch embedding models, the existing vectors in
> `student_embeddings` and `subject_embeddings` are **incompatible** —
> dimensions change from 768 to 1536. You must clear both tables and
> re-embed everything:
> ```sql
> DELETE FROM student_embeddings;
> DELETE FROM subject_embeddings;
> DELETE FROM rag_chunks;
> ```
> Then trigger re-embedding by having students re-upload CVs and
> calling the bulk subject re-index endpoint. The `rag_chunks` table
> must also be cleared since embeddings are dimension-dependent.

---

## Security notes

- The `X-Internal-Secret` header is validated on **every endpoint except `/health`** using `hmac.compare_digest` (timing-safe).
- The frontend **never calls FastAPI directly**. All AI calls go through NestJS.
- The secret must be identical in both `.env` files. Use a strong random value in production (e.g. `openssl rand -hex 32`).