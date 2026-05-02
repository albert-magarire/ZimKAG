"""Rebuild ZIMKAG.ipynb as a clean, focused training & evaluation notebook.

Keeps only the cells needed to:
  1. Load the new 10k dataset
  2. Train Legal-BERT (5-class)
  3. Evaluate (held-out + 5-fold CV with full metrics + plots)
  4. Save model + label_map to Drive
  5. Sanity-check inference

All Gradio / web-app code is removed — that lives in zimkag_webapp/.
"""
import json

KERNEL = {
    "kernelspec": {"name": "python3", "display_name": "Python 3"},
    "language_info": {"name": "python"},
}

def code(src: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": src.splitlines(keepends=True),
    }

def md(src: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": src.splitlines(keepends=True)}


cells = []

# ── 0: Title / intro ──────────────────────────────────────────────────────
cells.append(md(
"""# 🏗️ ZimKAG — Legal-BERT Training Notebook

**Development of a Supervised NLP Model to Assist in Identification of Risks and Opportunities in Bespoke Construction Contracts in Zimbabwe**

Robert T. Magarire · MSc Quantity Surveying · University of Zimbabwe
Supervised by W. Gumindoga & T. Chihombori

---

This notebook trains a 5-class Legal-BERT classifier on the 10 000-clause
construction-contract dataset and saves it to Google Drive. The interactive
web interface lives in **`zimkag_webapp/`** and is run locally — see
`zimkag_webapp/README.md`.

**Run order:** execute every cell top-to-bottom. The full pipeline takes
roughly 15–25 min on a Colab T4 GPU.
"""))

# ── 1: Setup ──────────────────────────────────────────────────────────────
cells.append(md("## 1 · Environment setup"))
cells.append(code(
"""# Install dependencies (run once per Colab session)
!pip install -q transformers==4.45.2 datasets==3.0.1 accelerate==0.34.2 \\
               sentence-transformers==3.2.0 scikit-learn==1.5.2 \\
               matplotlib seaborn networkx==3.3 rapidfuzz==3.10.0

import torch
print('CUDA available:', torch.cuda.is_available())
print('Device:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU')
"""))

# ── 2: Upload dataset ─────────────────────────────────────────────────────
cells.append(md(
"""## 2 · Upload the dataset

Upload `construction_contracts_dataset.csv` (10 000 rows, 7 columns).
"""))
cells.append(code(
"""from google.colab import files
uploaded = files.upload()  # → construction_contracts_dataset.csv
"""))

# ── 3: Load + prepare ─────────────────────────────────────────────────────
cells.append(md(
"""## 3 · Load and prepare data

Schema: `text · risk_level · clause_type · one_sided · jurisdiction · contract_type · notes`

The 5-class `risk_level` is mapped to integer labels for the model:
"""))
cells.append(code(
"""import pandas as pd

df = pd.read_csv("construction_contracts_dataset.csv")
print("Shape:", df.shape)
print("\\nColumns:", df.columns.tolist())
print("\\nRisk level distribution:")
print(df['risk_level'].value_counts())
print("\\nContract type distribution:")
print(df['contract_type'].value_counts())

# Drop exact duplicate clauses
df = df.drop_duplicates(subset=['text']).reset_index(drop=True)
print(f"\\nAfter dedup: {len(df)} rows")

# 5-class label map
LABEL2ID = {"high": 0, "medium": 1, "low": 2, "opportunity": 3, "neutral": 4}
ID2LABEL = {v: k for k, v in LABEL2ID.items()}
NUM_LABELS = len(LABEL2ID)

df['label'] = df['risk_level'].map(LABEL2ID)
assert df['label'].isna().sum() == 0, "Some risk_level values failed to map"

print("\\nFinal label counts:")
print(df['label'].value_counts().sort_index().rename(index=ID2LABEL))
"""))

# ── 4: Train/val/test split ───────────────────────────────────────────────
cells.append(md("## 4 · Stratified train / validation / test split"))
cells.append(code(
"""from sklearn.model_selection import train_test_split
from datasets import Dataset
from transformers import AutoTokenizer

train_df, temp_df = train_test_split(df, test_size=0.30, stratify=df['label'], random_state=42)
val_df,  test_df  = train_test_split(temp_df, test_size=0.50, stratify=temp_df['label'], random_state=42)
print(f"Train {len(train_df)}  |  Val {len(val_df)}  |  Test {len(test_df)}")

MODEL_NAME = "nlpaueb/legal-bert-base-uncased"
tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)

def tokenize(batch):
    return tokenizer(batch["text"], padding="max_length", truncation=True, max_length=512)

train_ds = Dataset.from_pandas(train_df[['text','label']]).map(tokenize, batched=True)
val_ds   = Dataset.from_pandas(val_df[['text','label']]).map(tokenize,   batched=True)
test_ds  = Dataset.from_pandas(test_df[['text','label']]).map(tokenize,  batched=True)
print("✅ Tokenisation complete.")
"""))

# ── 5: Train ──────────────────────────────────────────────────────────────
cells.append(md("## 5 · Fine-tune Legal-BERT (5-class)"))
cells.append(code(
"""import numpy as np
from sklearn.metrics import f1_score
from transformers import (AutoModelForSequenceClassification, Trainer,
                          TrainingArguments, DataCollatorWithPadding)

def compute_metrics(eval_pred):
    logits, labels = eval_pred
    preds = np.argmax(logits, axis=-1)
    return {"f1": f1_score(labels, preds, average="weighted")}

model = AutoModelForSequenceClassification.from_pretrained(
    MODEL_NAME,
    num_labels=NUM_LABELS,
    id2label=ID2LABEL,
    label2id=LABEL2ID,
)

training_args = TrainingArguments(
    output_dir="./zimkag_legalbert",
    eval_strategy="epoch",
    save_strategy="epoch",
    learning_rate=2e-5,
    per_device_train_batch_size=16,
    per_device_eval_batch_size=16,
    num_train_epochs=4,
    weight_decay=0.01,
    fp16=torch.cuda.is_available(),
    load_best_model_at_end=True,
    metric_for_best_model="f1",
    greater_is_better=True,
    report_to="none",
    logging_steps=50,
)

trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=train_ds,
    eval_dataset=val_ds,
    tokenizer=tokenizer,
    compute_metrics=compute_metrics,
    data_collator=DataCollatorWithPadding(tokenizer=tokenizer),
)

trainer.train()
print("✅ Training complete.")
"""))

# ── 6: Held-out test evaluation ───────────────────────────────────────────
cells.append(md("## 6 · Held-out test-set evaluation"))
cells.append(code(
"""import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (classification_report, confusion_matrix,
                             precision_recall_fscore_support, accuracy_score)

preds = trainer.predict(test_ds)
y_true = preds.label_ids
y_pred = np.argmax(preds.predictions, axis=-1)
labels_in_order = [ID2LABEL[i] for i in range(NUM_LABELS)]

print(f"\\nAccuracy : {accuracy_score(y_true, y_pred):.4f}")
prec, rec, f1, _ = precision_recall_fscore_support(y_true, y_pred, average='weighted')
print(f"Weighted F1: {f1:.4f}  |  Precision: {prec:.4f}  |  Recall: {rec:.4f}")

print("\\n=== Classification report ===")
print(classification_report(y_true, y_pred, target_names=labels_in_order, digits=4))

cm = confusion_matrix(y_true, y_pred)
plt.figure(figsize=(8, 6))
sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
            xticklabels=labels_in_order, yticklabels=labels_in_order,
            cbar_kws={'label': 'Count'})
plt.title('ZimKAG · Confusion Matrix (held-out test set)', fontsize=13)
plt.xlabel('Predicted'); plt.ylabel('True')
plt.tight_layout(); plt.show()
"""))

# ── 7: Per-class metrics chart ────────────────────────────────────────────
cells.append(md("## 7 · Per-class precision / recall / F1"))
cells.append(code(
"""prec, rec, f1, supp = precision_recall_fscore_support(y_true, y_pred, average=None,
                                                       labels=list(range(NUM_LABELS)))

metrics_df = pd.DataFrame({
    'class':     labels_in_order,
    'precision': prec,
    'recall':    rec,
    'f1':        f1,
    'support':   supp,
})
print(metrics_df.to_string(index=False))

ax = metrics_df.set_index('class')[['precision','recall','f1']].plot(
    kind='bar', figsize=(9, 5),
    color=['#1a5f7a', '#ffc107', '#2e7d64'], width=0.8, edgecolor='white',
)
ax.set_title('Per-class metrics on held-out test set')
ax.set_ylim(0, 1.05); ax.set_ylabel('Score'); ax.set_xlabel('')
ax.legend(loc='lower right'); ax.grid(axis='y', alpha=0.3)
for c in ax.containers: ax.bar_label(c, fmt='%.2f', fontsize=8, padding=2)
plt.xticks(rotation=0); plt.tight_layout(); plt.show()
"""))

# ── 8: 5-fold CV ──────────────────────────────────────────────────────────
cells.append(md(
"""## 8 · 5-fold stratified cross-validation

This block fine-tunes a fresh Legal-BERT on each fold and reports per-fold
F1, mean F1 and 95 % confidence intervals. **It takes ~1 hour on a T4** —
skip it if you only need the deployed model.
"""))
cells.append(code(
"""# OPTIONAL: 5-fold cross-validation for thesis statistics
from sklearn.model_selection import StratifiedKFold

RUN_CV = True   # ← set to False to skip
if RUN_CV:
    skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    fold_f1, fold_acc = [], []
    X = df['text'].values; y = df['label'].values

    for fold, (tr_idx, va_idx) in enumerate(skf.split(X, y), 1):
        print(f"\\n━━━━━━━━━━ Fold {fold}/5 ━━━━━━━━━━")
        tr_df = df.iloc[tr_idx]; va_df = df.iloc[va_idx]
        tr_ds = Dataset.from_pandas(tr_df[['text','label']]).map(tokenize, batched=True)
        va_ds = Dataset.from_pandas(va_df[['text','label']]).map(tokenize, batched=True)

        m = AutoModelForSequenceClassification.from_pretrained(
            MODEL_NAME, num_labels=NUM_LABELS, id2label=ID2LABEL, label2id=LABEL2ID,
        )
        ta = TrainingArguments(
            output_dir=f"./cv_fold_{fold}",
            num_train_epochs=3,
            per_device_train_batch_size=16,
            per_device_eval_batch_size=16,
            learning_rate=2e-5,
            weight_decay=0.01,
            fp16=torch.cuda.is_available(),
            eval_strategy="epoch",
            save_strategy="no",
            report_to="none",
            logging_steps=100,
        )
        tr = Trainer(model=m, args=ta, train_dataset=tr_ds, eval_dataset=va_ds,
                     tokenizer=tokenizer, compute_metrics=compute_metrics,
                     data_collator=DataCollatorWithPadding(tokenizer=tokenizer))
        tr.train()
        p = tr.predict(va_ds)
        yt = p.label_ids; yp = np.argmax(p.predictions, axis=-1)
        f = f1_score(yt, yp, average='weighted'); a = accuracy_score(yt, yp)
        print(f"Fold {fold}: F1 = {f:.4f}  Acc = {a:.4f}")
        fold_f1.append(f); fold_acc.append(a)

        del m, tr; torch.cuda.empty_cache()

    fold_f1 = np.array(fold_f1); fold_acc = np.array(fold_acc)
    ci = 1.96 * fold_f1.std() / np.sqrt(len(fold_f1))
    print("\\n=== 5-fold CV summary ===")
    print(f"Weighted F1 : {fold_f1.mean():.4f} ± {fold_f1.std():.4f}  (95% CI ±{ci:.4f})")
    print(f"Accuracy    : {fold_acc.mean():.4f} ± {fold_acc.std():.4f}")
    print(f"Per-fold F1 : {[f'{x:.4f}' for x in fold_f1]}")

    plt.figure(figsize=(7, 4))
    plt.bar(range(1, 6), fold_f1, color='#1a5f7a', edgecolor='white')
    plt.axhline(fold_f1.mean(), color='#ffc107', ls='--', label=f'mean = {fold_f1.mean():.3f}')
    plt.title('5-fold CV · weighted F1 per fold'); plt.xlabel('Fold'); plt.ylabel('F1')
    plt.ylim(0, 1.05); plt.legend(); plt.tight_layout(); plt.show()
else:
    print("Skipping 5-fold CV (RUN_CV=False).")
"""))

# ── 9: Save model + label_map ─────────────────────────────────────────────
cells.append(md(
"""## 9 · Save the trained model to Google Drive

After this cell completes, **download the entire `zimkag_legalbert_5class/`
folder** from your Drive and drop it into:

```
zimkag_webapp/models/zimkag_legalbert_5class/
```
"""))
cells.append(code(
"""import os, json
from google.colab import drive

drive.mount('/content/drive')

SAVE_PATH = "/content/drive/MyDrive/ZimKAG_Model/zimkag_legalbert_5class"
os.makedirs(SAVE_PATH, exist_ok=True)

trainer.save_model(SAVE_PATH)
tokenizer.save_pretrained(SAVE_PATH)

with open(os.path.join(SAVE_PATH, "label_map.json"), "w") as f:
    json.dump({"label2id": LABEL2ID, "id2label": ID2LABEL}, f, indent=2)

print(f"✅ Saved model + label_map.json → {SAVE_PATH}")
print("Files:")
for f in sorted(os.listdir(SAVE_PATH)):
    size = os.path.getsize(os.path.join(SAVE_PATH, f)) / (1024*1024)
    print(f"  {f}  ({size:.1f} MB)")
"""))

# ── 10: Verify saved model ────────────────────────────────────────────────
cells.append(md("## 10 · Verify the saved model with sample clauses"))
cells.append(code(
"""from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch, json, os

SAVE_PATH = "/content/drive/MyDrive/ZimKAG_Model/zimkag_legalbert_5class"

tk = AutoTokenizer.from_pretrained(SAVE_PATH, local_files_only=True)
mdl = AutoModelForSequenceClassification.from_pretrained(SAVE_PATH, local_files_only=True)
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
mdl.to(device).eval()

with open(os.path.join(SAVE_PATH, "label_map.json")) as f:
    lmap = json.load(f)
ID2LABEL_LOADED = {int(k): v for k, v in lmap["id2label"].items()}

samples = [
    "The Contractor shall pay liquidated damages of 5% of the Contract Sum per day of delay, uncapped.",
    "The Employer shall release retention upon Practical Completion.",
    "SECTION 4 – PAYMENT",
    "Payment applications shall be submitted by the 25th of each month.",
    "Where the Engineer fails to certify on time, the Contractor's quotation is treated as accepted.",
    "All payments shall be made in United States Dollars; payment in RTGS shall not discharge the obligation.",
    "The Contractor shall indemnify the Employer against all third-party claims, whether or not caused by the Contractor's negligence.",
]
print(f"{'PREDICTION':>12s} | {'CONF':>5s} | CLAUSE")
print("─" * 110)
for t in samples:
    enc = tk(t, return_tensors="pt", truncation=True, max_length=512).to(device)
    with torch.no_grad():
        probs = torch.softmax(mdl(**enc).logits, dim=-1)[0]
    p = int(probs.argmax().item())
    print(f"{ID2LABEL_LOADED[p]:>12s} | {probs[p]*100:>4.1f}% | {t[:90]}")
"""))

# ── 11: Next steps ────────────────────────────────────────────────────────
cells.append(md(
"""## 11 · Next: launch the web interface

The web app is a **standalone application** — no Colab required. From your
local machine:

1. Download the entire `zimkag_legalbert_5class/` folder from Google Drive.
2. Place it inside the project at: `zimkag_webapp/models/zimkag_legalbert_5class/`
3. Copy `zimkag_webapp/.env.example` → `zimkag_webapp/.env` and add your
   `GROQ_API_KEY` (free key from <https://console.groq.com/keys>).
4. Double-click `zimkag_webapp/run.bat` (Windows) or `./run.sh` (macOS / Linux).
5. Open <http://127.0.0.1:8000> in your browser.

See `zimkag_webapp/README.md` for full documentation, API reference and
production-deployment notes.
"""))


nb = {
    "cells": cells,
    "metadata": KERNEL,
    "nbformat": 4,
    "nbformat_minor": 5,
}

with open("ZIMKAG.ipynb", "w", encoding="utf-8") as f:
    json.dump(nb, f, indent=1, ensure_ascii=False)

print(f"OK · rebuilt ZIMKAG.ipynb with {len(cells)} clean cells")
