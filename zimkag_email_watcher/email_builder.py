"""HTML email composer for the ZimKAG analysis reply.

Renders a clean, mobile-friendly summary email with:
  • Risk distribution overview
  • Top high-risk and top opportunity clauses
  • A note that the full PDF is attached
"""
from __future__ import annotations
import html as html_lib
from datetime import datetime
from typing import Any

RISK_META = {
    "high":        {"label": "High Risk",    "icon": "🚨", "color": "#dc2626", "bg": "#fee2e2"},
    "medium":      {"label": "Medium Risk",  "icon": "🟠", "color": "#ea580c", "bg": "#ffedd5"},
    "low":         {"label": "Low Risk",     "icon": "🟡", "color": "#ca8a04", "bg": "#fef9c3"},
    "opportunity": {"label": "Opportunity",  "icon": "✅", "color": "#16a34a", "bg": "#dcfce7"},
    "neutral":     {"label": "Neutral",      "icon": "⚪", "color": "#6b7280", "bg": "#f3f4f6"},
}


def _esc(s: str) -> str:
    return html_lib.escape(s or "", quote=True)


def _truncate(s: str, n: int = 240) -> str:
    s = (s or "").strip()
    return s if len(s) <= n else s[: n - 1].rstrip() + "…"


def _count_by_risk(results: list[dict[str, Any]]) -> dict[str, int]:
    counts = {k: 0 for k in RISK_META}
    for r in results:
        rl = r.get("risk_level", "low")
        if rl in counts:
            counts[rl] += 1
    return counts


def _top_n(results: list[dict[str, Any]], risk: str, n: int = 3) -> list[dict[str, Any]]:
    filtered = [r for r in results if r.get("risk_level") == risk]
    return sorted(filtered, key=lambda r: -float(r.get("confidence", 0)))[:n]


def _clause_card_html(r: dict[str, Any]) -> str:
    meta = RISK_META.get(r.get("risk_level", "low"), RISK_META["low"])
    clause = _truncate(r.get("clause", ""), 280)
    rewrite = _truncate(r.get("suggested_rewrite", "") or "", 280)
    interp = _truncate(r.get("interpretation", ""), 220)
    kg = _truncate(r.get("kg_suggestion", ""), 220)
    has_rewrite = rewrite and rewrite != clause

    rewrite_block = (
        f"""
        <div style="background:#ecfdf5;border:1px solid #a7f3d0;border-radius:8px;padding:10px 12px;margin-top:8px;">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#065f46;letter-spacing:.05em;margin-bottom:4px;">Suggested fairer rewrite</div>
          <div style="font-size:13px;color:#065f46;line-height:1.55;">{_esc(rewrite)}</div>
        </div>
        """
        if has_rewrite else ""
    )

    return f"""
    <tr><td style="padding:0 0 14px 0;">
      <div style="border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;background:#fff;">
        <div style="background:{meta['bg']};padding:8px 14px;display:flex;align-items:center;">
          <span style="display:inline-block;background:{meta['color']};color:#fff;padding:3px 10px;border-radius:999px;font-size:11px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;">
            {meta['icon']} {meta['label']}
          </span>
          <span style="font-size:11px;color:#6b7280;margin-left:10px;font-family:Consolas,monospace;">
            conf {r.get('confidence', 0)}% · {_esc(r.get('clause_type', '—'))}
          </span>
        </div>
        <div style="padding:12px 14px;">
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#1a5f7a;letter-spacing:.05em;margin-bottom:4px;">Clause</div>
          <div style="font-size:13px;color:#1f2937;line-height:1.55;">{_esc(clause)}</div>
          <div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#1a5f7a;letter-spacing:.05em;margin:10px 0 4px;">Interpretation</div>
          <div style="font-size:13px;color:#1f2937;line-height:1.55;">{_esc(interp)}</div>
          { f'<div style="font-size:11px;font-weight:700;text-transform:uppercase;color:#1a5f7a;letter-spacing:.05em;margin:10px 0 4px;">Guidance</div><div style="font-size:13px;color:#475569;line-height:1.55;font-style:italic;">{_esc(kg)}</div>' if kg else "" }
          {rewrite_block}
        </div>
      </div>
    </td></tr>
    """


def _summary_pill(label: str, count: int, color: str, bg: str) -> str:
    return f"""
    <td align="center" style="padding:6px;">
      <div style="background:{bg};border-radius:12px;padding:14px 6px;">
        <div style="font-size:24px;font-weight:800;color:{color};font-family:'Segoe UI',Roboto,sans-serif;">{count}</div>
        <div style="font-size:10px;font-weight:700;text-transform:uppercase;color:{color};letter-spacing:.06em;">{label}</div>
      </div>
    </td>
    """


def build_subject(original_subject: str, contract_filename: str) -> str:
    base = (original_subject or "").strip()
    if base.lower().startswith(("re:", "fwd:")):
        prefix = ""
    else:
        prefix = "Re: " if base else ""
    label = base or contract_filename
    return f"[ZimKAG] Contract risk analysis – {prefix}{label}"[:160]


def build_html(
    *,
    sender_name: str,
    contract_filename: str,
    keyword_hits: int,
    matched_keywords: list[str],
    job: dict[str, Any],
) -> str:
    """Compose the HTML body of the reply email."""
    results: list[dict[str, Any]] = job.get("results") or []
    counts = _count_by_risk(results)
    total = len(results)

    high_top = _top_n(results, "high", n=3)
    opp_top = _top_n(results, "opportunity", n=2)

    risk_cards = "".join(_clause_card_html(r) for r in high_top) or (
        '<tr><td style="padding:10px 14px;color:#6b7280;font-style:italic;">No high-risk clauses found — well drafted!</td></tr>'
    )
    opp_cards = "".join(_clause_card_html(r) for r in opp_top) or (
        '<tr><td style="padding:10px 14px;color:#6b7280;font-style:italic;">No contractor-favourable opportunities surfaced in this contract.</td></tr>'
    )

    keyword_chips = "".join(
        f'<span style="display:inline-block;background:#e0e7ff;color:#3730a3;border-radius:999px;padding:3px 9px;font-size:11px;font-weight:600;margin:2px 4px 2px 0;">{_esc(k.replace("_", " "))}</span>'
        for k in matched_keywords[:14]
    )

    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#f9f3e6;font-family:'Segoe UI',Roboto,Helvetica,Arial,sans-serif;color:#1f2937;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f9f3e6;">
    <tr><td align="center" style="padding:30px 12px;">
      <table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#fff;border-radius:14px;overflow:hidden;box-shadow:0 10px 30px -12px rgba(0,0,0,.15);">

        <!-- Header -->
        <tr><td style="background:linear-gradient(135deg,#1a5f7a 0%,#0f172a 100%);padding:24px 28px;color:#fff;">
          <div style="font-size:11px;letter-spacing:.18em;text-transform:uppercase;color:#ffc107;font-weight:700;">ZimKAG · Contract Risk Analysis</div>
          <h1 style="margin:6px 0 0;font-size:24px;font-weight:800;color:#fff;">Hi {_esc(sender_name) or "there"},</h1>
          <p style="margin:8px 0 0;font-size:14px;color:#cbd5e1;line-height:1.55;">
            I detected a construction contract in your inbox — <strong style="color:#fff;">{_esc(contract_filename)}</strong> — and ran a full risk analysis. Here's the summary; the complete clause-by-clause report is attached as a PDF.
          </p>
        </td></tr>

        <!-- Keyword trigger -->
        <tr><td style="padding:18px 28px 0;">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#6b7280;font-weight:700;margin-bottom:6px;">Why this was analysed</div>
          <div style="font-size:13px;color:#475569;">Found <strong>{keyword_hits}</strong> construction-contract keywords in the document:</div>
          <div style="margin-top:8px;">{keyword_chips}</div>
        </td></tr>

        <!-- Summary pills -->
        <tr><td style="padding:24px 20px 6px;">
          <div style="font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:#6b7280;font-weight:700;margin:0 8px 8px;">Risk distribution · {total} clauses analysed</div>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
            <tr>
              {_summary_pill("High",        counts["high"],        RISK_META["high"]["color"],        RISK_META["high"]["bg"])}
              {_summary_pill("Medium",      counts["medium"],      RISK_META["medium"]["color"],      RISK_META["medium"]["bg"])}
              {_summary_pill("Low",         counts["low"],         RISK_META["low"]["color"],         RISK_META["low"]["bg"])}
              {_summary_pill("Opportunity", counts["opportunity"], RISK_META["opportunity"]["color"], RISK_META["opportunity"]["bg"])}
              {_summary_pill("Neutral",     counts["neutral"],     RISK_META["neutral"]["color"],     RISK_META["neutral"]["bg"])}
            </tr>
          </table>
        </td></tr>

        <!-- Top risks -->
        <tr><td style="padding:20px 28px 4px;">
          <div style="font-size:13px;font-weight:800;color:#dc2626;text-transform:uppercase;letter-spacing:.06em;">🚨 Top high-risk clauses</div>
          <p style="margin:4px 0 12px;font-size:12px;color:#6b7280;">Showing the three highest-confidence high-risk findings.</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{risk_cards}</table>
        </td></tr>

        <!-- Opportunities -->
        <tr><td style="padding:8px 28px 4px;">
          <div style="font-size:13px;font-weight:800;color:#16a34a;text-transform:uppercase;letter-spacing:.06em;">✅ Contractor-favourable clauses</div>
          <p style="margin:4px 0 12px;font-size:12px;color:#6b7280;">Opportunities worth defending in negotiation.</p>
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0">{opp_cards}</table>
        </td></tr>

        <!-- Footer -->
        <tr><td style="background:#f9f3e6;padding:20px 28px;border-top:1px solid #e5e7eb;">
          <p style="margin:0 0 6px;font-size:12px;color:#1a5f7a;font-weight:700;">📎 Full PDF report attached.</p>
          <p style="margin:0;font-size:11px;color:#6b7280;line-height:1.5;">
            This analysis is generated by <strong>ZimKAG</strong>, a supervised NLP model trained on JCT, NEC4, FIDIC and bespoke Zimbabwean construction contracts as part of an MSc Quantity Surveying research project at the University of Zimbabwe.
            Findings are advisory only — please consult your quantity surveyor or legal counsel before relying on them in negotiation.
          </p>
          <p style="margin:10px 0 0;font-size:10px;color:#9ca3af;">
            Generated {_esc(datetime.now().strftime('%d %b %Y · %H:%M'))} · ZimKAG Email Watcher v1.0
          </p>
        </td></tr>

      </table>
    </td></tr>
  </table>
</body></html>
"""
