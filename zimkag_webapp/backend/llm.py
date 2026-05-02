"""Thin Groq client used for clause rewrites + risk explanations.

If GROQ_API_KEY is missing, callers should gracefully fall back to KG-only
suggestions (the inference module already does this).
"""
from __future__ import annotations
import re
import time
from typing import Optional

import requests

from .config import settings


class GroqClient:
    def __init__(self) -> None:
        self.api_key = settings.GROQ_API_KEY
        self.model = settings.GROQ_MODEL
        self.url = settings.GROQ_URL
        self.enabled = bool(self.api_key) and not self.api_key.startswith("your_")

    def chat(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 600,
        timeout: int = 30,
    ) -> str:
        """Single-turn completion. Returns '' on any error / when disabled."""
        if not self.enabled:
            return ""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "system",
                    "content": system or (
                        "You are a senior construction-contract risk analyst with "
                        "expertise in JCT, NEC4, FIDIC and bespoke Zimbabwean "
                        "contracts. Be concise, professional and cite the contractor's "
                        "perspective."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        try:
            r = requests.post(self.url, headers=headers, json=payload, timeout=timeout)
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            # Surface rate-limit retry-after as a single short backoff
            if r.status_code == 429:
                time.sleep(2)
        except Exception:
            return ""
        return ""


# ── Prompt templates per risk category ────────────────────────────────────────

REWRITE_SYSTEM = (
    "You are a senior construction-contract risk analyst. Output ONLY the two "
    "sections REWRITE and RISK with no preamble, no markdown headings."
)

PROMPT_TEMPLATES = {
    "currency_risk": (
        "The following construction-contract clause exposes the contractor to "
        "currency / forex risk in Zimbabwe (USD/ZiG/RTGS volatility, RBZ rate "
        "movements, foreign-currency unavailability).\n\n"
        "Do TWO things:\n"
        "1. Rewrite the clause so payments are indexed to the official RBZ "
        "interbank rate at each payment date, with a cost-escalation formula "
        "for imported materials and a forex-unavailability force-majeure carve-out.\n"
        "2. In ONE sentence explain the financial risk to the contractor.\n\n"
        "Respond exactly in this format:\n"
        "REWRITE: <rewritten clause>\n"
        "RISK: <one-sentence explanation>\n\n"
        "Clause: {clause}"
    ),
    "penalty_risk": (
        "The following clause contains a penalty / liquidated-damages provision "
        "that is likely unfair to the contractor.\n\n"
        "Do TWO things:\n"
        "1. Rewrite to cap LADs at no more than 5% of the Contract Sum, link "
        "them to the Employer's actual loss, and exclude delays caused by the "
        "Employer or by Relevant Events.\n"
        "2. In ONE sentence explain the legal risk.\n\n"
        "Respond exactly in this format:\n"
        "REWRITE: <rewritten clause>\n"
        "RISK: <one-sentence explanation>\n\n"
        "Clause: {clause}"
    ),
    "indemnity_risk": (
        "The following clause requires the contractor to indemnify the Employer "
        "broadly or bear unlimited / consequential-loss liability.\n\n"
        "Do TWO things:\n"
        "1. Rewrite to allocate liability proportionally to each party's fault, "
        "exclude indirect/consequential loss and cap aggregate liability at the "
        "Contract Sum.\n"
        "2. In ONE sentence explain why the original is risky.\n\n"
        "Respond exactly in this format:\n"
        "REWRITE: <rewritten clause>\n"
        "RISK: <one-sentence explanation>\n\n"
        "Clause: {clause}"
    ),
    "termination_risk": (
        "The following termination clause favours the Employer disproportionately.\n\n"
        "Do TWO things:\n"
        "1. Rewrite to require reasonable notice, recovery of demobilisation "
        "costs and loss of profit on remaining works upon termination for "
        "convenience.\n"
        "2. In ONE sentence explain the contractor's exposure.\n\n"
        "Respond exactly in this format:\n"
        "REWRITE: <rewritten clause>\n"
        "RISK: <one-sentence explanation>\n\n"
        "Clause: {clause}"
    ),
    "ground_conditions_risk": (
        "The following clause shifts unforeseeable physical / ground conditions "
        "risk onto the contractor.\n\n"
        "Do TWO things:\n"
        "1. Rewrite to preserve a compensation event for unforeseeable physical "
        "conditions (mirror NEC4 60.1(12) or FIDIC 4.12).\n"
        "2. In ONE sentence explain the risk.\n\n"
        "Respond exactly in this format:\n"
        "REWRITE: <rewritten clause>\n"
        "RISK: <one-sentence explanation>\n\n"
        "Clause: {clause}"
    ),
    "payment_risk": (
        "The following payment / set-off clause undermines the contractor's "
        "cash-flow protection.\n\n"
        "Do TWO things:\n"
        "1. Rewrite to (a) limit set-off to amounts that have been ascertained "
        "and notified, (b) preserve the contractor's right to suspend on "
        "non-payment after a 7-day notice, and (c) require interest on overdue "
        "sums.\n"
        "2. In ONE sentence explain the cash-flow risk.\n\n"
        "Respond exactly in this format:\n"
        "REWRITE: <rewritten clause>\n"
        "RISK: <one-sentence explanation>\n\n"
        "Clause: {clause}"
    ),
    "_default_high": (
        "The following construction-contract clause is high-risk for the "
        "contractor in Zimbabwe.\n\n"
        "Do TWO things:\n"
        "1. Rewrite to balance the risk allocation while keeping the legal intent.\n"
        "2. In ONE sentence explain the main risk.\n\n"
        "Respond exactly in this format:\n"
        "REWRITE: <rewritten clause>\n"
        "RISK: <one-sentence explanation>\n\n"
        "Clause: {clause}"
    ),
    "_default_medium": (
        "The following clause carries moderate risk to the contractor.\n\n"
        "Do TWO things:\n"
        "1. Suggest a tightened rewrite that closes the contractor's exposure.\n"
        "2. In ONE sentence explain the residual risk.\n\n"
        "Respond exactly in this format:\n"
        "REWRITE: <rewritten clause>\n"
        "RISK: <one-sentence explanation>\n\n"
        "Clause: {clause}"
    ),
    "_default_opportunity": (
        "The following clause is a contractor-favourable opportunity.\n\n"
        "Output one sentence advising how to lock it in during negotiation, in "
        "this format:\n"
        "REWRITE: <unchanged clause>\n"
        "RISK: <one sentence on how to defend the opportunity>\n\n"
        "Clause: {clause}"
    ),
    "_default_neutral": (
        "Rephrase the following standard contract clause for clarity, without "
        "changing its legal meaning. Output ONLY the rephrased clause on a "
        "single line, no preamble.\n\nClause: {clause}"
    ),
}


REWRITE_RX = re.compile(r"REWRITE\s*:?\s*(.+?)(?=\nRISK\s*:|\Z)", re.DOTALL | re.IGNORECASE)
RISK_RX = re.compile(r"RISK\s*:?\s*(.+?)\Z", re.DOTALL | re.IGNORECASE)


def parse_rewrite(raw: str) -> tuple[str, str]:
    """Parse `REWRITE: ... RISK: ...` blocks → (rewrite, risk_explanation).

    Returns ('', '') when parsing fails.
    """
    if not raw:
        return "", ""
    rw = REWRITE_RX.search(raw)
    rk = RISK_RX.search(raw)
    rewrite = rw.group(1).strip() if rw else ""
    risk = rk.group(1).strip() if rk else ""
    # If parser failed entirely, treat the whole thing as a rewrite
    if not rewrite and not risk:
        rewrite = raw.strip()
    return rewrite, risk


# Singleton
groq = GroqClient()
