"""Update ZIMKAG.ipynb to use the new 10k dataset + 5-class schema."""
import json, copy

with open('ZIMKAG.ipynb', 'r', encoding='utf-8') as f:
    nb = json.load(f)

def make_code_cell(src):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src.splitlines(keepends=True)
    }

def make_md_cell(src):
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": src.splitlines(keepends=True)
    }

# ============================================================================
# Cell 0: Upload new dataset
# ============================================================================
nb['cells'][0]['source'] = [
    "from google.colab import files\n",
    "uploaded = files.upload()  # Upload construction_contracts_dataset.csv\n"
]

# ============================================================================
# Cell 1: Load + map new 10k dataset → 5 classes
# ============================================================================
cell1 = '''# =============================================================================
# STAGE 1: Load the new 10k construction contracts dataset (5-class schema)
# Schema: text, risk_level, clause_type, one_sided, jurisdiction, contract_type, notes
# risk_level ∈ {high, medium, low, opportunity, neutral}
# =============================================================================
import pandas as pd

# Load the new dataset
df = pd.read_csv("construction_contracts_dataset.csv")
print("Dataset shape:", df.shape)
print("\\nColumns:", df.columns.tolist())
print("\\nRisk level distribution:")
print(df['risk_level'].value_counts())
print("\\nContract type distribution:")
print(df['contract_type'].value_counts())

# Drop exact duplicates of clause text
df = df.drop_duplicates(subset=['text']).reset_index(drop=True)
print(f"\\nAfter dedup: {len(df)} rows")

# Map 5-class risk_level → integer labels for the model
LABEL2ID = {
    "high":        0,
    "medium":      1,
    "low":         2,
    "opportunity": 3,
    "neutral":     4,
}
ID2LABEL = {v: k for k, v in LABEL2ID.items()}

df['label'] = df['risk_level'].map(LABEL2ID)
assert df['label'].isna().sum() == 0, "Some risk_level values failed to map"

# Quick sanity check
print("\\nLabel distribution:")
print(df[['risk_level', 'label']].value_counts())

# Save the model-ready CSV for downstream cells
df[['text', 'label', 'risk_level', 'clause_type', 'one_sided',
    'jurisdiction', 'contract_type', 'notes']].to_csv(
    "zimkag_training_data.csv", index=False
)
print("\\n✅ Saved 'zimkag_training_data.csv' — used by all subsequent cells.")
'''
nb['cells'][1] = make_code_cell(cell1)

# ============================================================================
# Cell 2: Install + imports
# ============================================================================
cell2 = '''# =============================================================================
# ZIMKAG AI — CLEAN RESTART WITH KNOWLEDGE AUGMENTATION (5-class)
# =============================================================================
!pip install -q transformers datasets accelerate scikit-learn pandas matplotlib seaborn gradio sentence-transformers networkx

import torch
import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from transformers import (
    AutoTokenizer, AutoModelForSequenceClassification,
    Trainer, TrainingArguments, DataCollatorWithPadding
)
from datasets import Dataset
import matplotlib.pyplot as plt
import seaborn as sns

# Reload the prepared dataset
df = pd.read_csv("zimkag_training_data.csv")
print(f"Loaded {len(df)} clauses across {df['label'].nunique()} classes")
print(df['risk_level'].value_counts())

NUM_LABELS = 5
LABEL2ID = {"high":0, "medium":1, "low":2, "opportunity":3, "neutral":4}
ID2LABEL = {v:k for k,v in LABEL2ID.items()}
'''
nb['cells'][2] = make_code_cell(cell2)

# ============================================================================
# Cell 3: Train/val/test split + tokenize
# ============================================================================
cell3 = '''# =============================================================================
# Train/Val/Test split (stratified) + tokenization
# =============================================================================
train_df, temp_df = train_test_split(
    df, test_size=0.3, stratify=df['label'], random_state=42
)
val_df, test_df = train_test_split(
    temp_df, test_size=0.5, stratify=temp_df['label'], random_state=42
)
print(f"Train: {len(train_df)} | Val: {len(val_df)} | Test: {len(test_df)}")

model_name = "nlpaueb/legal-bert-base-uncased"
tokenizer = AutoTokenizer.from_pretrained(model_name)

def tokenize_function(examples):
    return tokenizer(
        examples["text"],
        padding="max_length",
        truncation=True,
        max_length=512
    )

train_dataset = Dataset.from_pandas(train_df[['text', 'label']]).map(tokenize_function, batched=True)
val_dataset   = Dataset.from_pandas(val_df[['text', 'label']]).map(tokenize_function, batched=True)
test_dataset  = Dataset.from_pandas(test_df[['text', 'label']]).map(tokenize_function, batched=True)

print("✅ Tokenization complete.")
'''
nb['cells'][3] = make_code_cell(cell3)

# ============================================================================
# Cell 4: Train the model with 5 classes
# ============================================================================
cell4 = '''# =============================================================================
# Train Legal-BERT for 5-class clause risk classification
# =============================================================================
def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {"f1": f1_score(labels, preds, average="weighted")}

model = AutoModelForSequenceClassification.from_pretrained(
    model_name,
    num_labels=NUM_LABELS,
    id2label=ID2LABEL,
    label2id=LABEL2ID,
)

training_args = TrainingArguments(
    output_dir="./zimkag_legalbert",
    eval_strategy="epoch",
    learning_rate=2e-5,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=16,
    num_train_epochs=4,
    weight_decay=0.01,
    fp16=True,
    save_strategy="epoch",
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    greater_is_better=True,
    report_to="none",
    logging_steps=50,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_dataset,
    eval_dataset=val_dataset,
    tokenizer=tokenizer,
    compute_metrics=compute_metrics,
    data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
)

trainer.train()
print("✅ Training complete.")

# Held-out test evaluation
preds = trainer.predict(test_dataset)
y_true = preds.label_ids
y_pred = np.argmax(preds.predictions, axis=-1)
print("\\n=== Held-out Test Set ===")
print(classification_report(y_true, y_pred, target_names=[ID2LABEL[i] for i in range(NUM_LABELS)]))

cm = confusion_matrix(y_true, y_pred)
plt.figure(figsize=(7,6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=[ID2LABEL[i] for i in range(NUM_LABELS)],
            yticklabels=[ID2LABEL[i] for i in range(NUM_LABELS)])
plt.xlabel('Predicted'); plt.ylabel('True'); plt.title('Confusion Matrix (5-class)')
plt.tight_layout(); plt.show()
'''
nb['cells'][4] = make_code_cell(cell4)

# ============================================================================
# Cell 5 (save model) — keep but ensure label maps are saved
# ============================================================================
cell5 = '''# =============================================================================
# 1. SAVE TRAINED MODEL TO GOOGLE DRIVE
# =============================================================================
import os, json
from google.colab import drive

drive.mount('/content/drive')

SAVE_PATH = "/content/drive/MyDrive/ZimKAG_Model/zimkag_legalbert_5class"
os.makedirs(SAVE_PATH, exist_ok=True)

trainer.save_model(SAVE_PATH)
tokenizer.save_pretrained(SAVE_PATH)

# also save label maps for the web app
with open(os.path.join(SAVE_PATH, "label_map.json"), "w") as f:
    json.dump({"label2id": LABEL2ID, "id2label": ID2LABEL}, f, indent=2)

print(f"✅ Model + label_map.json saved to: {SAVE_PATH}")
'''
nb['cells'][5] = make_code_cell(cell5)

# ============================================================================
# Cell 7: Verify saved model
# ============================================================================
cell7 = '''# =============================================================================
# 2. VERIFY SAVED MODEL
# =============================================================================
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch, json, os

SAVE_PATH = "/content/drive/MyDrive/ZimKAG_Model/zimkag_legalbert_5class"

tokenizer_v = AutoTokenizer.from_pretrained(SAVE_PATH, local_files_only=True)
model_v = AutoModelForSequenceClassification.from_pretrained(SAVE_PATH, local_files_only=True)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model_v.to(device).eval()

with open(os.path.join(SAVE_PATH, "label_map.json")) as f:
    lmap = json.load(f)
ID2LABEL = {int(k): v for k, v in lmap["id2label"].items()}

test_clauses = [
    "The Contractor shall pay liquidated damages of 5% of the Contract Sum per day of delay, uncapped.",
    "The Employer shall release retention upon Practical Completion.",
    "SECTION 4 – PAYMENT",
    "Payment applications shall be submitted by the 25th of each month.",
    "Where the Engineer fails to certify on time, the Contractor's quotation is treated as accepted.",
]
for t in test_clauses:
    enc = tokenizer_v(t, return_tensors="pt", truncation=True, max_length=512).to(device)
    with torch.no_grad():
        probs = torch.softmax(model_v(**enc).logits, dim=-1)[0]
    p = probs.argmax().item()
    print(f"[{ID2LABEL[p]:>11s}  {probs[p]*100:.1f}%]  {t[:90]}")
'''
nb['cells'][7] = make_code_cell(cell7)

# ============================================================================
# Cell 8: Updated ZimKAGModel class for 5 classes
# ============================================================================
cell8 = '''# =============================================================================
# ZIMKAG AI — INFERENCE CLASS (5-class + Knowledge Graph + Semantic Retrieval)
# =============================================================================
import torch, os, json
import networkx as nx
from sentence_transformers import SentenceTransformer, util
from transformers import AutoTokenizer, AutoModelForSequenceClassification

LABEL_DISPLAY = {
    "high":        "🚨 HIGH RISK",
    "medium":      "🟠 MEDIUM RISK",
    "low":         "🟡 LOW RISK",
    "opportunity": "✅ OPPORTUNITY",
    "neutral":     "⚪ NEUTRAL",
}

class ZimKAGModel:
    def __init__(self, model_path="/content/drive/MyDrive/ZimKAG_Model/zimkag_legalbert_5class"):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"Model not found at: {model_path}")
        print(f"✅ Loading model from: {model_path}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_path, local_files_only=True)
        self.model.to(self.device).eval()

        # Load label map saved alongside the model
        lm_path = os.path.join(model_path, "label_map.json")
        if os.path.exists(lm_path):
            with open(lm_path) as f:
                lmap = json.load(f)
            self.id2label = {int(k): v for k, v in lmap["id2label"].items()}
        else:
            # fall back to model config
            self.id2label = {int(k): v for k, v in self.model.config.id2label.items()}

        self.semantic_retriever = SentenceTransformer('all-MiniLM-L6-v2')
        self.kg, self.knowledge_dict = self._build_knowledge_graph()
        self.knowledge_embeddings = self.semantic_retriever.encode(
            [d["suggestion"] for d in self.knowledge_dict.values()]
        )
        print("✅ ZimKAG (5-class + KG + Semantic Retrieval) ready.\\n")

    def _build_knowledge_graph(self):
        G = nx.DiGraph()
        entries = {
            "currency_risk": {
                "triggers": ["currency", "hyperinflation", "exchange rate", "rbz", "convertibility", "forex", "usd", "rtgs", "zig"],
                "severity": "Critical",
                "suggestion": "Add a currency-adjustment clause indexed to the official RBZ interbank rate, with cost-escalation protection for imported materials."
            },
            "penalty_risk": {
                "triggers": ["penalty", "liquidated damages", "0.5% per day", "2.5%", "uncapped", "without limit"],
                "severity": "High",
                "suggestion": "Cap LADs at no more than 5% of the Contract Sum, link to actual loss, and exclude employer-caused delays."
            },
            "indemnity_risk": {
                "triggers": ["indemnify", "hold harmless", "bear all risk", "waive all rights", "unlimited liability", "consequential loss"],
                "severity": "Critical",
                "suggestion": "Replace with proportional fault-based liability and a contract-value cap; exclude consequential loss."
            },
            "termination_risk": {
                "triggers": ["terminate at will", "without cause", "no claim for loss of profit", "step in"],
                "severity": "High",
                "suggestion": "Negotiate termination-for-convenience compensation including loss of profit on remaining works."
            },
            "ground_conditions_risk": {
                "triggers": ["unforeseeable", "ground conditions", "physical conditions", "site information", "howsoever arising"],
                "severity": "High",
                "suggestion": "Preserve compensation event for unforeseeable physical conditions (NEC4 60.1(12) / FIDIC 4.12)."
            },
            "payment_risk": {
                "triggers": ["set off", "withhold payment", "pay-when-paid", "no advance payment", "verification"],
                "severity": "High",
                "suggestion": "Limit set-off to ascertained sums; ensure HGCRA-compliant payment notice mechanism; negotiate advance payment."
            },
            "opportunity_fair": {
                "triggers": ["fair compensation", "extension of time", "deemed accepted", "right to suspend", "interest on overdue", "loss of profit on omission"],
                "severity": "Opportunity",
                "suggestion": "Reinforce in negotiation and ensure clear procedural mechanism to invoke."
            },
            "force_majeure_protection": {
                "triggers": ["force majeure", "exceptional event", "prevention event", "epidemic", "pandemic", "civil unrest"],
                "severity": "Opportunity",
                "suggestion": "Include forex unavailability, hyperinflation and government action as relief events with time + cost recovery."
            },
        }
        for cat, data in entries.items():
            G.add_node(cat, **data)
            for t in data["triggers"]:
                G.add_node(t, type="trigger")
                G.add_edge(t, cat, relation="activates")
        return G, entries

    def analyze(self, clause: str):
        # 1. Legal-BERT prediction
        inputs = self.tokenizer([clause], padding=True, truncation=True,
                                max_length=512, return_tensors="pt").to(self.device)
        with torch.no_grad():
            probs = torch.softmax(self.model(**inputs).logits, dim=-1)
        pred_idx = probs.argmax(dim=-1).item()
        conf = probs[0][pred_idx].item()
        risk_level = self.id2label[pred_idx]
        all_probs = {self.id2label[i]: float(probs[0][i]) for i in range(probs.size(-1))}

        # 2. Knowledge-graph trigger matching
        lower = clause.lower()
        adjustment = "No major adjustment recommended."
        explanation = "Legal-BERT prediction"
        kg_match = None
        for cat, data in self.knowledge_dict.items():
            if any(t in lower for t in data["triggers"]):
                adjustment = data["suggestion"]
                explanation = f"KG match: {data['severity']} – {cat.replace('_', ' ').title()}"
                kg_match = cat
                # KG can escalate risk_level if model under-predicts
                if data["severity"] == "Critical" and risk_level not in ("high",):
                    risk_level = "high"; pred_idx = 0
                elif data["severity"] == "High" and risk_level in ("low", "neutral"):
                    risk_level = "medium"
                break

        # 3. Semantic retrieval fallback
        if kg_match is None:
            q = self.semantic_retriever.encode(clause)
            sims = util.cos_sim(q, self.knowledge_embeddings)[0]
            if sims.max() > 0.65:
                idx = sims.argmax().item()
                adjustment = list(self.knowledge_dict.values())[idx]["suggestion"]
                explanation = f"Semantic match (cos={sims.max():.2f})"

        return {
            "clause": clause,
            "risk_level": risk_level,
            "prediction": LABEL_DISPLAY.get(risk_level, risk_level),
            "confidence": f"{conf*100:.1f}%",
            "all_probabilities": all_probs,
            "explanation": explanation,
            "adjustment_suggestion": adjustment,
            "kg_match": kg_match,
        }


# Initialize and quick test
zimkag = ZimKAGModel()
for t in [
    "The Contractor shall pay liquidated damages of 0.5% per day, uncapped, regardless of cause.",
    "The Employer shall give the Contractor possession of the Site on the agreed date.",
    "SECTION 9 – DISPUTE RESOLUTION",
    "Where the Engineer fails to respond within 28 days the Contractor's quotation is deemed accepted.",
]:
    r = zimkag.analyze(t)
    print(f"[{r['prediction']:>20s} {r['confidence']:>5s}] {t[:90]}")
    print(f"   → {r['adjustment_suggestion'][:120]}\\n")
'''
nb['cells'][8] = make_code_cell(cell8)

# ============================================================================
# Cell 37: Replace the Gradio app with a pointer to the new web app
# ============================================================================
cell37 = '''# =============================================================================
# 🎉 NEW WEB INTERFACE
# =============================================================================
# The full interactive web app has been moved out of this notebook into a
# standalone FastAPI + modern HTML/JS application. To run it locally:
#
#   1. Train the model in cells 1–5 above and save to Google Drive.
#   2. Download the saved folder (zimkag_legalbert_5class) to your machine
#      and place it at:  zimkag_webapp/models/zimkag_legalbert_5class/
#   3. cd zimkag_webapp
#      pip install -r requirements.txt
#      Add your GROQ_API_KEY to .env  (copy .env.example)
#      python -m backend.app
#   4. Open http://localhost:8000 in your browser.
#
# See zimkag_webapp/README.md for full instructions.
# =============================================================================
print("👉 Run the web app locally — see zimkag_webapp/README.md")
'''
nb['cells'][37] = make_code_cell(cell37)

# Save updated notebook
with open('ZIMKAG.ipynb', 'w', encoding='utf-8') as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print("✅ Notebook updated successfully.")
print(f"   Total cells: {len(nb['cells'])}")
