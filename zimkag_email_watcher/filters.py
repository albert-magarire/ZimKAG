"""Construction-contract keyword detection and text extraction for the pre-filter.

We *only* trigger an expensive ZimKAG analysis if the attachment contains at
least N distinct construction-contract keywords. This avoids burning compute
on invoices, photos, generic PDFs, marketing material, etc.
"""
from __future__ import annotations
import io
import re
from pathlib import Path
from typing import Iterable

import pdfplumber
import docx


# ── Construction-contract keyword library ─────────────────────────────────────
# Each entry is a regex pattern (case-insensitive, whole-word) and a label.
# The label is what gets counted as a "distinct hit" — so "contractor" and
# "sub-contractor" both count under different labels.

_PATTERNS: list[tuple[str, str]] = [
    # ── Parties & roles ────────────────────────────────────────────
    (r"\bcontractor\b",                    "contractor"),
    (r"\bsub[\s-]?contractor\b",           "sub-contractor"),
    (r"\bemployer\b",                      "employer"),
    (r"\bengineer\b",                      "engineer"),
    (r"\barchitect\b",                     "architect"),
    (r"\bproject\s+manager\b",             "project_manager"),
    (r"\bquantity\s+surveyor\b",           "quantity_surveyor"),

    # ── Core contractual concepts ──────────────────────────────────
    (r"\bvariations?\b",                   "variation"),
    (r"\bpayments?\b",                     "payment"),
    (r"\bretention\b",                     "retention"),
    (r"\bliquidated\s+damages\b",          "liquidated_damages"),
    (r"\bdamages\b",                       "damages"),
    (r"\bpenalt(y|ies)\b",                 "penalty"),
    (r"\bdefects?\b",                      "defects"),
    (r"\bdefects?\s+liability\b",          "defects_liability"),
    (r"\bdefects?\s+notification\b",       "defects_notification"),
    (r"\bpractical\s+completion\b",        "practical_completion"),
    (r"\btaking[\s-]?over\b",              "taking_over"),
    (r"\bextension\s+of\s+time\b",         "extension_of_time"),
    (r"\b(EOT|E\.O\.T\.)\b",               "extension_of_time"),
    (r"\bforce\s+majeure\b",               "force_majeure"),
    (r"\bcompensation\s+events?\b",        "compensation_event"),
    (r"\btermination\b",                   "termination"),
    (r"\bassignment\b",                    "assignment"),
    (r"\bclaims?\b",                       "claim"),
    (r"\bdisputes?\b",                     "dispute"),
    (r"\barbitration\b",                   "arbitration"),
    (r"\badjudication\b",                  "adjudication"),
    (r"\bmediation\b",                     "mediation"),

    # ── Pricing & financial ────────────────────────────────────────
    (r"\bcontract\s+(sum|price|amount)\b", "contract_sum"),
    (r"\bbill\s+of\s+quantit(y|ies)\b",    "bill_of_quantities"),
    (r"\bBOQ\b",                           "bill_of_quantities"),
    (r"\bprovisional\s+sum\b",             "provisional_sum"),
    (r"\bprime\s+cost\b",                  "prime_cost"),
    (r"\binterim\s+payment\b",             "interim_payment"),
    (r"\bfinal\s+account\b",               "final_account"),
    (r"\bvaluation\b",                     "valuation"),
    (r"\bcertificate\b",                   "certificate"),
    (r"\bescalation\b",                    "escalation"),
    (r"\bdayworks?\b",                     "daywork"),

    # ── Programme & site ───────────────────────────────────────────
    (r"\bprogramme\b",                     "programme"),
    (r"\bcompletion\s+date\b",             "completion_date"),
    (r"\bcommencement\s+date\b",           "commencement_date"),
    (r"\bsite\s+possession\b",             "site_possession"),
    (r"\bworks?\b",                        "works"),
    (r"\bspecifications?\b",               "specifications"),
    (r"\bdrawings?\b",                     "drawings"),
    (r"\bas[\s-]?built\b",                 "as_built"),
    (r"\bsnagging\b",                      "snagging"),
    (r"\bpunch[\s-]?list\b",               "punch_list"),
    (r"\bhandover\b",                      "handover"),

    # ── Securities & insurance ─────────────────────────────────────
    (r"\bperformance\s+(bond|security|guarantee)\b", "performance_bond"),
    (r"\bbank\s+guarantee\b",              "bank_guarantee"),
    (r"\badvance\s+payment\b",             "advance_payment"),
    (r"\bmobilisation\b",                  "mobilisation"),
    (r"\bdemobilisation\b",                "demobilisation"),
    (r"\binsurance\b",                     "insurance"),
    (r"\bindemnif(y|ication|ies)\b",       "indemnify"),
    (r"\bindemnit(y|ies)\b",               "indemnify"),
    (r"\bwarrant(y|ies)\b",                "warranty"),

    # ── Contract types & standards ────────────────────────────────
    (r"\bJCT\b",                           "JCT"),
    (r"\bNEC\s*[34]?\b",                   "NEC4"),
    (r"\bFIDIC\b",                         "FIDIC"),
    (r"\b(red|yellow|silver)\s+book\b",    "FIDIC_book"),
    (r"\bparticular\s+conditions\b",       "particular_conditions"),
    (r"\bspecial\s+conditions\b",          "special_conditions"),
    (r"\bgeneral\s+conditions\b",          "general_conditions"),
    (r"\bcontract\s+data\b",               "contract_data"),

    # ── Misc construction nouns ───────────────────────────────────
    (r"\bsubcontractor\b",                 "subcontractor"),
    (r"\bnominated\s+sub[\s-]?contractor\b","nominated_subcontractor"),
    (r"\btender\b",                        "tender"),
    (r"\bletter\s+of\s+acceptance\b",      "letter_of_acceptance"),
    (r"\bworkmanship\b",                   "workmanship"),
    (r"\bmaterials?\b",                    "materials"),
    (r"\bpreliminaries\b",                 "preliminaries"),
    (r"\bsite\s+instruction\b",            "site_instruction"),
    (r"\bvariation\s+order\b",             "variation_order"),
    (r"\bset[\s-]?off\b",                  "set_off"),
    (r"\bpay[\s-]?when[\s-]?paid\b",       "pay_when_paid"),
    (r"\bbreach\b",                        "breach"),
    (r"\binsolvency\b",                    "insolvency"),
    (r"\bgoverning\s+law\b",               "governing_law"),
]

_COMPILED = [(re.compile(p, re.IGNORECASE), label) for p, label in _PATTERNS]


# ── Public API ────────────────────────────────────────────────────────────────

def count_keyword_hits(text: str) -> tuple[int, list[str]]:
    """Return (distinct_label_count, sorted_label_list) for the given text.

    Two patterns sharing a label only count once (e.g. 'EOT' and
    'extension of time' both map to 'extension_of_time').
    """
    if not text:
        return 0, []
    hits: set[str] = set()
    for rx, label in _COMPILED:
        if rx.search(text):
            hits.add(label)
    return len(hits), sorted(hits)


def is_likely_contract(text: str, min_hits: int = 3) -> tuple[bool, int, list[str]]:
    """Convenience wrapper used by the watcher."""
    n, labels = count_keyword_hits(text)
    return n >= min_hits, n, labels


# ── Text extraction (for pre-filter only; the webapp re-parses on analysis) ──

SUPPORTED_EXTS = {".pdf", ".docx", ".txt", ".text"}


def is_supported(filename: str) -> bool:
    return Path(filename).suffix.lower() in SUPPORTED_EXTS


def extract_pdf(data: bytes) -> str:
    try:
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return "\n".join((page.extract_text() or "") for page in pdf.pages)
    except Exception:
        return ""


def extract_docx(data: bytes) -> str:
    try:
        d = docx.Document(io.BytesIO(data))
        return "\n".join(p.text for p in d.paragraphs)
    except Exception:
        return ""


def extract_txt(data: bytes) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def extract_text(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return extract_pdf(data)
    if ext == ".docx":
        return extract_docx(data)
    if ext in (".txt", ".text"):
        return extract_txt(data)
    return ""
