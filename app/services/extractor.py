import unicodedata
import re
from pathlib import Path
from langdetect import detect, LangDetectException


def clean_text(text: str) -> str:
    text = unicodedata.normalize('NFKC', text)
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        stripped = line.strip()
        # remove lines that are only digits (page numbers)
        if re.fullmatch(r'\d+', stripped):
            continue
        cleaned.append(stripped)
    # collapse multiple blank lines into one
    result = '\n'.join(cleaned)
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result.strip()


def detect_language(text: str) -> str:
    try:
        return detect(text)
    except LangDetectException:
        return 'fr'


def extract_from_pdf(file_path: str) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)
    return '\n'.join(text_parts)


def extract_from_docx(file_path: str) -> str:
    from docx import Document
    doc = Document(file_path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return '\n'.join(paragraphs)


def extract_from_image(file_path: str) -> str:
    import pytesseract
    from PIL import Image
    image = Image.open(file_path)
    return pytesseract.image_to_string(image, lang='fra+ara+eng')


def extract_text(file_path: str, file_type: str) -> dict:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f'File not found: {file_path}')

    mime = file_type.lower()

    if mime == 'application/pdf':
        raw = extract_from_pdf(file_path)
    elif mime in (
        'application/vnd.openxmlformats-officedocument'
        '.wordprocessingml.document',
        'application/msword',
    ):
        raw = extract_from_docx(file_path)
    elif mime in ('image/jpeg', 'image/png', 'image/jpg'):
        raw = extract_from_image(file_path)
    else:
        raise ValueError(f'Unsupported file type: {file_type}')

    text = clean_text(raw)

    if len(text) < 50:
        raise ValueError('Could not extract readable text from file')

    word_count = len(text.split())
    language = detect_language(text)

    return {
        'text': text,
        'word_count': word_count,
        'language': language,
    }