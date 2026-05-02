"""ZimKAG inference engine — Legal-BERT + Knowledge Graph + Semantic Retrieval.

5-class risk taxonomy: high / medium / low / opportunity / neutral.

Designed to degrade gracefully:
  • Without a trained model → falls back to KG + semantic only.
  • Without GROQ_API_KEY    → uses KG suggestions in place of LLM rewrites.
"""
from __future__ import annotations
import json
import logging
import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import networkx as nx
import torch
from rapidfuzz import fuzz
from sentence_transformers import SentenceTransformer, util
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from .config import settings
from .llm import groq, parse_rewrite, PROMPT_TEMPLATES, REWRITE_SYSTEM

log = logging.getLogger(__name__)

# ── Display metadata ──────────────────────────────────────────────────────────

LABEL_DISPLAY = {
    "high":        {"label": "High Risk",    "icon": "🚨", "color": "#dc2626"},
    "medium":      {"label": "Medium Risk",  "icon": "🟠", "color": "#ea580c"},
    "low":         {"label": "Low Risk",     "icon": "🟡", "color": "#ca8a04"},
    "opportunity": {"label": "Opportunity",  "icon": "✅", "color": "#16a34a"},
    "neutral":     {"label": "Neutral",      "icon": "⚪", "color": "#6b7280"},
}

DEFAULT_ID2LABEL = {0: "high", 1: "medium", 2: "low", 3: "opportunity", 4: "neutral"}

# ── Knowledge graph definition ────────────────────────────────────────────────

KG_ENTRIES: dict[str, dict[str, Any]] = {
    "currency_risk": {
        "triggers": ["currency", "hyperinflation", "exchange rate", "rbz",
                     "convertibility", "forex", "foreign currency",
                     "rtgs", "zig", "usd"],
        "severity": "Critical",
        "category": "currency_risk",
        "suggestion": (
            "Index payments to the official RBZ interbank rate at the date of "
            "each payment, with a cost-escalation formula for imported "
            "materials and a forex-unavailability force-majeure carve-out."
        ),
    },
    "penalty_risk": {
        "triggers": ["penalty", "liquidated damages", "0.5% per day", "2.5%",
                     "uncapped", "without limit", "without cap"],
        "severity": "High",
        "category": "penalty_risk",
        "suggestion": (
            "Cap LADs at no more than 5% of the Contract Sum, link to actual "
            "loss, and exclude employer-caused or relevant-event delays."
        ),
    },
    "indemnity_risk": {
        "triggers": ["indemnify", "hold harmless", "bear all risk",
                     "waive all rights", "unlimited liability",
                     "consequential loss", "indirect loss", "without limit"],
        "severity": "Critical",
        "category": "indemnity_risk",
        "suggestion": (
            "Replace with proportional fault-based liability, exclude "
            "indirect/consequential loss and cap aggregate liability at the "
            "Contract Sum."
        ),
    },
    "termination_risk": {
        "triggers": ["terminate at will", "without cause", "for convenience",
                     "no claim for loss of profit", "step in", "step-in"],
        "severity": "High",
        "category": "termination_risk",
        "suggestion": (
            "Negotiate termination-for-convenience compensation including "
            "demobilisation costs and loss of profit on remaining works."
        ),
    },
    "ground_conditions_risk": {
        "triggers": ["unforeseeable", "ground conditions", "physical conditions",
                     "site information", "howsoever arising", "sub-surface"],
        "severity": "High",
        "category": "ground_conditions_risk",
        "suggestion": (
            "Preserve a compensation event for unforeseeable physical "
            "conditions (mirror NEC4 60.1(12) or FIDIC 4.12)."
        ),
    },
    "payment_risk": {
        "triggers": ["set off", "set-off", "withhold payment", "pay-when-paid",
                     "pay when paid", "no advance payment", "deduct from",
                     "verification"],
        "severity": "High",
        "category": "payment_risk",
        "suggestion": (
            "Limit set-off to ascertained sums; preserve HGCRA-compliant "
            "payment-notice mechanism; secure right to suspend on non-payment."
        ),
    },
    "opportunity_fair": {
        "triggers": ["fair compensation", "extension of time", "deemed accepted",
                     "right to suspend", "interest on overdue",
                     "loss of profit on omission", "mobilisation advance",
                     "advance payment", "retention release", "bank guarantee"],
        "severity": "Opportunity",
        "category": "opportunity_fair",
        "suggestion": (
            "Reinforce in negotiation and ensure a clear procedural mechanism "
            "exists to invoke this entitlement."
        ),
    },
    "force_majeure_protection": {
        "triggers": ["force majeure", "exceptional event", "prevention event",
                     "epidemic", "pandemic", "civil unrest", "act of god"],
        "severity": "Opportunity",
        "category": "force_majeure_protection",
        "suggestion": (
            "Include forex unavailability, hyperinflation and government "
            "action as relief events with both time and cost recovery."
        ),
    },
}


# ── Heuristic clause-type tagger (when model only returns risk_level) ────────

CLAUSE_TYPE_TRIGGERS = {
    "payment":       ["payment", "invoice", "certificate", "interim", "retention",
                      "pay less", "pay-when", "set off", "set-off", "currency",
                      "escalation"],
    "delay":         ["delay", "completion date", "extension of time", "eot",
                      "liquidated damages", "lad", "programme", "critical path"],
    "indemnity":     ["indemnify", "indemnity", "hold harmless", "insurance",
                      "liability", "claims"],
    "variation":     ["variation", "compensation event", "scope", "instruction",
                      "additional work", "omission"],
    "termination":   ["terminate", "termination", "default", "step in", "step-in",
                      "insolvency"],
    "dispute":       ["dispute", "adjudication", "arbitration", "mediation",
                      "daab", "negotiation"],
    "force_majeure": ["force majeure", "exceptional event", "prevention event",
                      "act of god", "pandemic", "civil unrest"],
    "warranty":      ["warrant", "defect", "defects liability", "defects "
                      "notification", "rectification", "guarantee"],
    "regulatory":    ["regulation", "law", "statute", "permit", "licence",
                      "compliance", "ema", "zimra", "nssa", "ohsact"],
    "site_conditions": ["site", "ground conditions", "physical conditions",
                        "access to site"],
}


def guess_clause_type(text: str) -> str:
    low = text.lower()
    best = ("administrative", 0)
    for ctype, triggers in CLAUSE_TYPE_TRIGGERS.items():
        score = sum(1 for t in triggers if t in low)
        if score > best[1]:
            best = (ctype, score)
    return best[0]


# ── Inference engine ─────────────────────────────────────────────────────────

class ZimKAGEngine:
    """Loads model + KG + retriever once; thread-safe for FastAPI use."""

    def __init__(self) -> None:
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = None
        self.tokenizer = None
        self.id2label: dict[int, str] = DEFAULT_ID2LABEL.copy()
        self.label2id: dict[str, int] = {v: k for k, v in self.id2label.items()}
        self._lock = threading.Lock()
        self.model_loaded = False
        self.model_dir = settings.MODEL_DIR

        self._load_model()
        self._load_retriever()
        self._build_kg()

    # ── loading ──────────────────────────────────────────────────────────
    def _load_model(self) -> None:
        path = Path(self.model_dir)
        cfg = path / "config.json"
        if not cfg.exists():
            if settings.ALLOW_NO_MODEL:
                log.warning("No trained model at %s — running KG-only mode.", path)
                return
            raise FileNotFoundError(
                f"Trained model not found at {path}. Train it via the notebook "
                f"and copy the saved folder to MODEL_DIR, or set ALLOW_NO_MODEL=1."
            )
        log.info("Loading model from %s on %s", path, self.device)
        self.tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(
            path, local_files_only=True
        )
        self.model.to(self.device).eval()

        # Prefer the explicit label_map.json saved by the notebook
        lm_path = path / "label_map.json"
        if lm_path.exists():
            try:
                lmap = json.loads(lm_path.read_text(encoding="utf-8"))
                self.id2label = {int(k): v for k, v in lmap["id2label"].items()}
                self.label2id = {v: int(k) for k, v in self.id2label.items()}
            except Exception as e:
                log.warning("label_map.json present but unreadable: %s", e)

        # Fall back to model config if mapping looks like the HF placeholders
        if all(re.match(r"^LABEL_\d+$", v) for v in self.id2label.values()):
            cfg_id2 = self.model.config.id2label or {}
            self.id2label = {int(k): str(v) for k, v in cfg_id2.items()}

        self.model_loaded = True

    def _load_retriever(self) -> None:
        log.info("Loading sentence-transformer (all-MiniLM-L6-v2)…")
        self.retriever = SentenceTransformer("all-MiniLM-L6-v2")
        self.kg_suggestions = [v["suggestion"] for v in KG_ENTRIES.values()]
        self.kg_categories = list(KG_ENTRIES.keys())
        self.kg_embeddings = self.retriever.encode(self.kg_suggestions, convert_to_tensor=True)

    def _build_kg(self) -> None:
        g = nx.DiGraph()
        for cat, data in KG_ENTRIES.items():
            g.add_node(cat, type="risk_category", **data)
            for t in data["triggers"]:
                g.add_node(t, type="trigger")
                g.add_edge(t, cat, relation="activates")
        self.kg = g

    # ── helpers ──────────────────────────────────────────────────────────
    def _kg_match(self, text: str) -> Optional[dict[str, Any]]:
        low = text.lower()
        for cat, data in KG_ENTRIES.items():
            for t in data["triggers"]:
                if t in low or fuzz.partial_ratio(t, low) > 92:
                    return data
        return None

    def _semantic_match(self, text: str, threshold: float = 0.55) -> Optional[dict[str, Any]]:
        emb = self.retriever.encode(text, convert_to_tensor=True)
        sims = util.cos_sim(emb, self.kg_embeddings)[0]
        top = sims.argmax().item()
        score = float(sims[top])
        if score < threshold:
            return None
        cat = self.kg_categories[top]
        out = dict(KG_ENTRIES[cat])
        out["_semantic_score"] = score
        return out

    def _bert_predict(self, text: str) -> tuple[str, float, dict[str, float]]:
        if not self.model_loaded:
            # Heuristic fallback when no model present
            kg = self._kg_match(text)
            if kg:
                if kg["severity"] == "Critical":
                    return "high", 0.7, {"high": 0.7}
                if kg["severity"] == "High":
                    return "medium", 0.6, {"medium": 0.6}
                if kg["severity"] == "Opportunity":
                    return "opportunity", 0.6, {"opportunity": 0.6}
            # default: heading-like = neutral, otherwise low
            short = len(text.strip()) < 80 and text.strip().isupper()
            return ("neutral" if short else "low"), 0.55, {"neutral" if short else "low": 0.55}

        with self._lock:
            inputs = self.tokenizer(
                [text], padding=True, truncation=True,
                max_length=512, return_tensors="pt",
            ).to(self.device)
            with torch.no_grad():
                logits = self.model(**inputs).logits
                probs = torch.softmax(logits, dim=-1)[0]
        idx = int(probs.argmax().item())
        risk = self.id2label.get(idx, "low")
        all_probs = {self.id2label.get(i, f"class_{i}"): float(probs[i]) for i in range(probs.size(0))}
        return risk, float(probs[idx]), all_probs

    # ── main API ─────────────────────────────────────────────────────────
    def analyze(self, clause: str, with_llm: bool = True) -> Dict[str, Any]:
        clause = clause.strip()
        risk_level, conf, all_probs = self._bert_predict(clause)

        # KG escalation
        kg = self._kg_match(clause)
        kg_match = None
        explanation_parts = ["Legal-BERT prediction"]
        if kg:
            kg_match = kg["category"]
            explanation_parts.append(
                f"KG match: {kg['severity']} – {kg['category'].replace('_', ' ').title()}"
            )
            if kg["severity"] == "Critical" and risk_level not in ("high",):
                risk_level = "high"
            elif kg["severity"] == "High" and risk_level in ("low", "neutral"):
                risk_level = "medium"
            elif kg["severity"] == "Opportunity" and risk_level == "neutral":
                risk_level = "opportunity"
            kg_suggestion = kg["suggestion"]
        else:
            sem = self._semantic_match(clause)
            if sem:
                kg_match = sem["category"]
                kg_suggestion = sem["suggestion"]
                explanation_parts.append(
                    f"Semantic match: {sem['category'].replace('_', ' ').title()} "
                    f"(cos={sem['_semantic_score']:.2f})"
                )
            else:
                kg_suggestion = "No specific KG/semantic match — review under standard contract heuristics."

        # LLM rewrite
        rewrite = ""
        risk_explanation = ""
        if with_llm and groq.enabled and risk_level != "neutral":
            template_key = kg_match if kg_match in PROMPT_TEMPLATES else f"_default_{risk_level}"
            template = PROMPT_TEMPLATES.get(template_key, PROMPT_TEMPLATES["_default_high"])
            llm_raw = groq.chat(
                template.format(clause=clause),
                system=REWRITE_SYSTEM,
                temperature=0.3,
                max_tokens=500,
            )
            rewrite, risk_explanation = parse_rewrite(llm_raw)

        if not rewrite:
            rewrite = clause if risk_level in ("opportunity", "neutral") else kg_suggestion
        if not risk_explanation:
            if risk_level == "high":
                risk_explanation = "Significant risk shifted to the contractor; renegotiate or qualify."
            elif risk_level == "medium":
                risk_explanation = "Moderate exposure — manageable but worth tightening in negotiation."
            elif risk_level == "low":
                risk_explanation = "Standard balanced provision; no material risk."
            elif risk_level == "opportunity":
                risk_explanation = "Contractor-favourable — defend and use as a negotiation anchor."
            else:
                risk_explanation = "Heading or boilerplate; no risk allocation."

        meta = LABEL_DISPLAY[risk_level]
        return {
            "clause": clause,
            "risk_level": risk_level,
            "risk_label": meta["label"],
            "risk_icon": meta["icon"],
            "risk_color": meta["color"],
            "confidence": round(conf * 100, 1),
            "all_probabilities": {k: round(v * 100, 1) for k, v in all_probs.items()},
            "clause_type": guess_clause_type(clause),
            "kg_match": kg_match,
            "kg_suggestion": kg_suggestion,
            "explanation": " | ".join(explanation_parts),
            "interpretation": risk_explanation,
            "suggested_rewrite": rewrite,
        }

    def analyze_batch(self, clauses: List[str], with_llm: bool = True) -> List[Dict[str, Any]]:
        return [self.analyze(c, with_llm=with_llm) for c in clauses]

    def status(self) -> Dict[str, Any]:
        return {
            "model_loaded": self.model_loaded,
            "model_dir": str(self.model_dir),
            "device": str(self.device),
            "labels": list(self.label2id.keys()),
            "llm_enabled": groq.enabled,
            "llm_model": groq.model if groq.enabled else None,
        }


# Module-level singleton (instantiated on first import in app startup)
engine: Optional[ZimKAGEngine] = None


def get_engine() -> ZimKAGEngine:
    global engine
    if engine is None:
        engine = ZimKAGEngine()
    return engine
