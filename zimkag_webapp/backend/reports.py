"""PDF report generation for completed analyses."""
from __future__ import annotations
import datetime as dt
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List

from fpdf import FPDF

from .config import settings


def _ascii(text: str, max_len: int | None = None) -> str:
    """fpdf2's core fonts are latin-1 only — strip emoji/CJK and normalise."""
    if not text:
        return ""
    text = text.replace("🚨", "[HIGH]") \
               .replace("🟠", "[MED]") \
               .replace("🟡", "[LOW]") \
               .replace("✅", "[OPP]") \
               .replace("⚪", "[NEU]") \
               .replace("→", "->") \
               .replace("–", "-").replace("—", "-") \
               .replace("'", "'").replace("'", "'") \
               .replace(""", '"').replace(""", '"')
    text = re.sub(r"[^\x00-\xff]", "", text)
    if max_len and len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


class ZimKAGReport(FPDF):
    def header(self):
        self.set_fill_color(26, 95, 122)  # navy
        self.rect(0, 0, 210, 18, style="F")
        self.set_font("Helvetica", "B", 14)
        self.set_text_color(255, 255, 255)
        self.set_xy(10, 5)
        self.cell(0, 8, "ZimKAG Contract Risk Analysis Report", align="L")
        self.set_font("Helvetica", "", 9)
        self.set_xy(10, 11)
        self.cell(0, 5, "Supervised NLP for Bespoke Construction Contracts in Zimbabwe", align="L")
        self.set_text_color(0, 0, 0)
        self.set_y(22)

    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(120, 120, 120)
        self.cell(
            0, 8,
            f"ZimKAG  |  {dt.datetime.now():%Y-%m-%d %H:%M}  |  Page {self.page_no()}",
            align="C",
        )


RISK_FILL = {
    "high":        (220, 38, 38),
    "medium":      (234, 88, 12),
    "low":         (202, 138, 4),
    "opportunity": (22, 163, 74),
    "neutral":     (107, 114, 128),
}


def _summary_block(pdf: ZimKAGReport, results: List[Dict[str, Any]], filename: str) -> None:
    counts = {k: 0 for k in RISK_FILL}
    for r in results:
        counts[r.get("risk_level", "low")] = counts.get(r.get("risk_level", "low"), 0) + 1

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(26, 95, 122)
    pdf.cell(0, 8, "Executive Summary", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", "", 10)
    pdf.multi_cell(
        0, 5,
        f"Document: {_ascii(filename, 90)}\n"
        f"Total clauses analysed: {len(results)}\n"
        f"Generated: {dt.datetime.now():%Y-%m-%d %H:%M}",
    )
    pdf.ln(2)

    # Risk count bars
    pdf.set_font("Helvetica", "B", 10)
    pdf.cell(0, 6, "Risk distribution", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    max_count = max(counts.values()) or 1
    for level, count in counts.items():
        bar_w = (count / max_count) * 110
        r, g, b = RISK_FILL[level]
        pdf.set_fill_color(r, g, b)
        x_start = pdf.get_x()
        pdf.cell(28, 6, level.title())
        pdf.cell(bar_w if bar_w > 1 else 1, 6, "", fill=True)
        pdf.cell(0, 6, f"  {count}", new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)


def _clause_card(pdf: ZimKAGReport, idx: int, r: Dict[str, Any]) -> None:
    risk = r.get("risk_level", "low")
    rcolor = RISK_FILL.get(risk, RISK_FILL["low"])

    # Estimate height to avoid mid-card page break
    if pdf.get_y() > 250:
        pdf.add_page()

    # Risk pill
    pdf.set_fill_color(*rcolor)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(35, 6, _ascii(r.get("risk_label", risk.title())), align="C", fill=True)

    pdf.set_text_color(80, 80, 80)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(
        0, 6,
        f"  #{idx}   conf {r.get('confidence', 0)}%   type: {r.get('clause_type', '-')}",
        new_x="LMARGIN", new_y="NEXT",
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)

    # Clause text
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, "Clause", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 4.5, _ascii(r.get("clause", ""), 1200))
    pdf.ln(1)

    # Interpretation
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(0, 5, "Interpretation", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 9)
    pdf.multi_cell(0, 4.5, _ascii(r.get("interpretation", ""), 600))
    pdf.ln(1)

    # KG suggestion
    if r.get("kg_suggestion"):
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, "Knowledge-graph guidance", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "I", 9)
        pdf.multi_cell(0, 4.5, _ascii(r.get("kg_suggestion", ""), 600))
        pdf.ln(1)

    # Suggested rewrite
    if r.get("suggested_rewrite") and r.get("suggested_rewrite") != r.get("clause"):
        pdf.set_font("Helvetica", "B", 9)
        pdf.cell(0, 5, "Suggested rewrite", new_x="LMARGIN", new_y="NEXT")
        pdf.set_font("Helvetica", "", 9)
        pdf.multi_cell(0, 4.5, _ascii(r.get("suggested_rewrite", ""), 1200))

    pdf.set_draw_color(220, 220, 220)
    pdf.set_line_width(0.3)
    y = pdf.get_y() + 2
    pdf.line(10, y, 200, y)
    pdf.ln(5)


def build_report(results: List[Dict[str, Any]], filename: str = "Contract") -> Path:
    """Generate a PDF report and return its path on disk."""
    pdf = ZimKAGReport(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    _summary_block(pdf, results, filename)

    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(26, 95, 122)
    pdf.cell(0, 8, "Clause-by-Clause Analysis", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    # Order: high → medium → opportunity → low → neutral
    order = {"high": 0, "medium": 1, "opportunity": 2, "low": 3, "neutral": 4}
    sorted_results = sorted(results, key=lambda x: order.get(x.get("risk_level"), 99))
    for i, r in enumerate(sorted_results, 1):
        _clause_card(pdf, i, r)

    out = settings.REPORTS_DIR / f"zimkag_report_{uuid.uuid4().hex[:8]}.pdf"
    pdf.output(str(out))
    return out
