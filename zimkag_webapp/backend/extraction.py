"""Document parsing + clause segmentation.

Supports PDF (pdfplumber), DOCX (python-docx) and plain text. Splits raw text
into reasonable clause-level units suitable for sentence-level classification.
"""
from __future__ import annotations
import io
import re
from pathlib import Path
from typing import List

import pdfplumber
import docx

from .config import settings


# ── Heading / numbering patterns kept as a single line (don't sentence-split)
HEADING_PATTERNS = [
    re.compile(r"^[A-Z][A-Z0-9 \-,'/&()]{2,}$"),                       # ALL-CAPS HEADING
    re.compile(r"^\d+(\.\d+)*\s+[A-Z]"),                               # 1. / 1.1 / 1.2.3 Heading
    re.compile(r"^[a-z]\)\s+"),                                        # a) item
    re.compile(r"^[ivxlcdm]+\)\s+", re.IGNORECASE),                    # i) ii) iii)
    re.compile(r"^(SECTION|CLAUSE|PART|ARTICLE|ANNEXURE)\s", re.I),
]

# Common multi-line junk to strip
JUNK_LINE = re.compile(
    r"^(page\s+\d+(\s+of\s+\d+)?|\d+\s*$|signed[:\s].*|witness.*|"
    r"date[:\s].*|address[:\s].*|tel[:\s].*|email[:\s].*)$",
    re.IGNORECASE,
)


def extract_pdf(data: bytes) -> str:
    out: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            t = page.extract_text() or ""
            if t.strip():
                out.append(t)
    return "\n".join(out)


def extract_docx(data: bytes) -> str:
    doc = docx.Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def extract_txt(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def extract_text(filename: str, data: bytes) -> str:
    """Dispatch by file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_pdf(data)
    if ext == ".docx":
        return extract_docx(data)
    if ext in (".txt", ".text"):
        return extract_txt(data)
    raise ValueError(f"Unsupported file type: {ext}. Use .pdf, .docx or .txt.")


def is_heading(line: str) -> bool:
    if len(line) < 80 and any(p.search(line) for p in HEADING_PATTERNS):
        return True
    return False


def _strip_noise(text: str) -> str:
    # Collapse hyphenated line wraps from PDFs ("contrac-\ntor" → "contractor")
    text = re.sub(r"-\n(\w)", r"\1", text)
    # Normalise whitespace
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text


def split_clauses(raw: str) -> List[str]:
    """Split raw document text into clause-sized units.

    Strategy:
      1. Split into lines, drop junk + tiny lines.
      2. Keep headings as standalone units.
      3. For prose lines longer than ~350 chars, split on sentence boundaries.
      4. Deduplicate while preserving order.
    """
    raw = _strip_noise(raw)
    lines = [l.strip() for l in raw.split("\n")]
    lines = [l for l in lines if len(l) >= settings.MIN_CLAUSE_CHARS or is_heading(l)]
    lines = [l for l in lines if not JUNK_LINE.match(l)]

    clauses: list[str] = []
    for line in lines:
        if is_heading(line):
            clauses.append(line)
            continue
        if len(line) > 350:
            sents = re.split(r"(?<=[.!?])\s+(?=[A-Z(])", line)
            for s in sents:
                s = s.strip()
                if len(s) >= settings.MIN_CLAUSE_CHARS:
                    clauses.append(s)
        else:
            clauses.append(line)

    # Dedup, preserve order
    seen: set[str] = set()
    unique: list[str] = []
    for c in clauses:
        key = re.sub(r"\s+", " ", c).strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(c)

    return unique[: settings.MAX_CLAUSES]
