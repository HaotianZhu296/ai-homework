"""Extract plain text from a resume file (DOCX, PDF or plain text).

DOCX is read straight from its XML with the standard library, so the common
case needs no third-party package. PDF uses pypdf.
"""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
MAX_CHARS = 20_000


class UnsupportedFile(ValueError):
    pass


def docx_to_text(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            xml = zf.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as exc:
        raise UnsupportedFile("not a valid .docx file") from exc
    root = ElementTree.fromstring(xml)
    lines = []
    for para in root.iter(f"{W}p"):
        parts = []
        for node in para.iter():
            if node.tag == f"{W}t" and node.text:
                parts.append(node.text)
            elif node.tag == f"{W}tab":
                parts.append("\t")
            elif node.tag in (f"{W}br", f"{W}cr"):
                parts.append("\n")
        is_list_item = para.find(f"{W}pPr/{W}numPr") is not None
        text = "".join(parts).strip()
        if text:
            lines.append(f"- {text}" if is_list_item else text)
    return "\n".join(lines)


def pdf_to_text(data: bytes) -> str:
    from pypdf import PdfReader  # imported lazily: only PDF uploads need it

    try:
        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)
    except Exception as exc:  # pypdf raises many different error types
        raise UnsupportedFile(f"could not read PDF: {exc}") from exc


def detect_kind(data: bytes, filename: str = "", content_type: str = "") -> str:
    name = filename.lower()
    if data[:4] == b"%PDF" or name.endswith(".pdf") or "pdf" in content_type:
        return "pdf"
    if data[:2] == b"PK" or name.endswith(".docx") or "wordprocessingml" in content_type:
        return "docx"
    if name.endswith((".txt", ".md")) or content_type.startswith("text/"):
        return "text"
    try:
        data.decode("utf-8")
        return "text"
    except UnicodeDecodeError:
        raise UnsupportedFile("unsupported file type; upload a .docx, .pdf or .txt resume") from None


def clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\xa0", " ")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()[:MAX_CHARS]


def extract_text(data: bytes, filename: str = "", content_type: str = "") -> tuple[str, str]:
    """Return (text, kind). Raises UnsupportedFile for files that cannot be read."""
    if not data:
        raise UnsupportedFile("the file is empty")
    kind = detect_kind(data, filename, content_type)
    if kind == "docx":
        text = docx_to_text(data)
    elif kind == "pdf":
        text = pdf_to_text(data)
    else:
        text = data.decode("utf-8", errors="replace")
    text = clean(text)
    if not text:
        raise UnsupportedFile("no text found in the file (is it a scanned image?)")
    return text, kind
