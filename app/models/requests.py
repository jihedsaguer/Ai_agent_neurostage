from pydantic import BaseModel

class ExtractRequest(BaseModel):
    filePath: str
    userId: str
    fileType: str

class EmbedStudentRequest(BaseModel):
    userId: str
    extractedText: str
    skills: list[str] = []
    university: str = ""
    specialization: str = ""
    level: str = ""

class EmbedSubjectRequest(BaseModel):
    subjectId: str
    titre: str
    description: str
    techno: list[str] = []
    prerequis: str = ""
    niveau: str = ""

class EmbedSubjectsBulkRequest(BaseModel):
    subjects: list[EmbedSubjectRequest]

class GenerateSubjectRequest(BaseModel):
    studentIds: list[str]
    encadreurId: str
    context: str | None = None

class RagIngestRequest(BaseModel):
    filePath: str
    documentName: str
    documentType: str

class RagQueryRequest(BaseModel):
    question: str
    userId: str
