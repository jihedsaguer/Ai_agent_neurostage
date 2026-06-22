from sre_parse import SUCCESS
from pydantic import BaseModel
from datetime import datetime

class ExtractResponse(BaseModel):
    extractedText: str
    wordCount: int
    language: str

class EmbedResponse(BaseModel):
    success: bool
    updatedAt:  str =""

    def __init__(self, **data):
        if "updatedAt" not in data or not data["updatedAt"]:
            data["updatedAt"] = datetime.utcnow().isoformat()
        super().__init__(**data)

class BulkEmbedResponse(BaseModel):
    indexed: int
    failed: int
    duration: datetime

class RagSourceItem(BaseModel):
    documentName: str
    excerpt: str

class RagIngestResponse(BaseModel):
    success: bool
    chunksIndexed: int

class RagQueryResponse(BaseModel):
    answer: str
    sources: list[RagSourceItem]