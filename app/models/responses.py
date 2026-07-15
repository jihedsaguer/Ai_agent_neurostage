from pydantic import BaseModel
from datetime import datetime

# Extract
class ExtractResponse(BaseModel):
    extractedText: str
    wordCount: int
    language: str

# Embed
class EmbedResponse(BaseModel):
    success: bool
    updatedAt: str = ""

    def __init__(self, **data):
        if "updatedAt" not in data or not data["updatedAt"]:
            data["updatedAt"] = datetime.utcnow().isoformat()
        super().__init__(**data)

class BulkEmbedResponse(BaseModel):
    indexed: int
    failed: int
    duration: float

# Suggest
class SuggestionItem(BaseModel):
    subjectId: str
    score: float
    matchedKeywords: list[str]

class SuggestResponse(BaseModel):
    suggestions: list[SuggestionItem]

# Generate
class GenerateSubjectResponse(BaseModel):
    titre: str
    description: str
    techno: list[str]
    prerequis: str
    niveau: str
    rawPromptUsed: str

# RAG
class RagSourceItem(BaseModel):
    documentName: str
    excerpt: str

class RagIngestResponse(BaseModel):
    success: bool
    chunksIndexed: int

class RagQueryResponse(BaseModel):
    answer: str
    sources: list[RagSourceItem]