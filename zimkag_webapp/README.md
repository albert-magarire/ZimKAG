# ZimKAG · Contract Risk &amp; Opportunity Analyser

**Development of a Supervised NLP Model to Assist in Identification of Risks and Opportunities in Bespoke Construction Contracts in Zimbabwe.**

A modern, production-ready web application that lets a quantity surveyor upload a JCT, NEC4, FIDIC or bespoke construction contract (PDF / DOCX / TXT) and receive a clause-by-clause classification into **High · Medium · Low · Opportunity · Neutral**, together with knowledge-graph guidance and an LLM-generated fairer rewrite for every risky clause.

> Robert T. Magarire · MSc Quantity Surveying · Faculty of Engineering and the Built Environment · University of Zimbabwe
> Supervised by W. Gumindoga &amp; T. Chihombori

---

## ✨ What's in the box

| Layer            | Tech                                                   |
|------------------|--------------------------------------------------------|
| Frontend         | HTML + Tailwind (CDN) + vanilla JS + Chart.js          |
| Backend          | FastAPI + Uvicorn (async, jobs polled by progress bar) |
| Classifier       | Fine-tuned `nlpaueb/legal-bert-base-uncased` (5-class) |
| Knowledge graph  | NetworkX + RapidFuzz triggers, semantic fallback       |
| Semantic search  | Sentence-Transformers `all-MiniLM-L6-v2`               |
| LLM rewrites     | Groq · `llama-3.3-70b-versatile`                       |
| Document parsing | `pdfplumber`, `python-docx`                            |
| PDF reports      | `fpdf2` with branded styling                           |

Features:

- 🎨 Modern UI — gradient hero, dark mode, drop-zone, animated progress, donut chart, search & filter
- 🧠 Hybrid analysis — Legal-BERT prediction + KG escalation + semantic fallback
- 🔁 Async job pipeline with live progress polling
- 📄 Branded PDF report download
- 🛡 Graceful degradation (KG-only mode if no model; canned suggestions if no LLM key)
- 🌍 Zimbabwe-aware triggers (RBZ, RTGS/ZiG, ZIMRA, EMA, NSSA, OHSACT, Arbitration Act 7:15)

---

## 🗂 Project layout

```
zimkag_webapp/
├── backend/
│   ├── app.py            # FastAPI routes, async job runner
│   ├── inference.py      # Legal-BERT + KG + semantic engine
│   ├── extraction.py     # PDF/DOCX/TXT → clauses
│   ├── llm.py            # Groq client + prompt templates
│   ├── reports.py        # Branded PDF report generator
│   └── config.py         # Settings (env-driven)
├── frontend/
│   ├── index.html        # Single-page UI
│   ├── style.css
│   └── app.js
├── models/               # ← put your trained model here
├── .env.example          # Copy to .env and fill in GROQ_API_KEY
├── requirements.txt
├── run.bat               # Windows launcher (auto-installs venv)
├── run.sh                # macOS / Linux launcher
└── README.md
```

---

## 🚀 Quick start (Windows)

### 1. Train the model (one time, in Google Colab)

1. Open `ZIMKAG.ipynb` in Colab.
2. Run cell 0 and upload `construction_contracts_dataset.csv` (the 10k-row file from this repo).
3. Run cells 1 → 5 sequentially. Cell 5 saves the trained model to:
   ```
   /content/drive/MyDrive/ZimKAG_Model/zimkag_legalbert_5class/
   ```
4. Download that folder to your laptop and drop it inside `zimkag_webapp/models/` so the path is:
   ```
   zimkag_webapp/models/zimkag_legalbert_5class/
       ├── config.json
       ├── model.safetensors
       ├── tokenizer.json (etc.)
       └── label_map.json
   ```

### 2. Configure the LLM key

```bat
copy .env.example .env
notepad .env
```

Set `GROQ_API_KEY=…` (free key from https://console.groq.com/keys).

> ⚠ **Security note:** the Groq key that was previously hard-coded in `ZIMKAG.ipynb` cell 37 is now exposed publicly. **Rotate it now** at the link above and use the fresh one in `.env`.

### 3. Launch

```bat
run.bat
```

The first run creates a virtual environment, installs dependencies (~4 GB with PyTorch), and starts the server. Open <http://127.0.0.1:8000> in your browser.

### Quick start (macOS / Linux)

```bash
chmod +x run.sh
./run.sh
```

---

## 🔧 Configuration (`.env`)

| Variable          | Default                                  | Notes                                              |
|-------------------|------------------------------------------|----------------------------------------------------|
| `GROQ_API_KEY`    | _(required for LLM rewrites)_            | Free at console.groq.com/keys                      |
| `GROQ_MODEL`      | `llama-3.3-70b-versatile`                | Any Groq-hosted chat model                         |
| `MODEL_DIR`       | `./models/zimkag_legalbert_5class`       | Path (absolute or relative) to the trained model   |
| `ALLOW_NO_MODEL`  | `0`                                      | Set to `1` to start in KG-only mode for demos      |
| `HOST` / `PORT`   | `127.0.0.1` / `8000`                     | Bind address                                       |

---

## 🧠 How a clause is analysed

1. **Document parsing** (`extraction.py`) — file is parsed and split into clause-sized units. Headings, all-caps section markers and numbered clauses are preserved as standalone units; long prose lines are split on sentence boundaries.
2. **Legal-BERT prediction** (`inference.py`) — the fine-tuned 5-class model returns `risk_level` + confidence + the full probability distribution.
3. **Knowledge-graph match** — exact + fuzzy trigger matching against eight Zimbabwe-aware risk categories (currency, penalty, indemnity, termination, ground conditions, payment, opportunity, force-majeure protection). A `Critical` KG hit upgrades the risk_level if the model under-predicted.
4. **Semantic fallback** — if no KG trigger matches, a sentence-transformer embedding is compared against the suggestions; matches above cosine 0.55 surface KG guidance.
5. **LLM rewrite** — for `high` / `medium` clauses, Groq is called with a category-specific prompt (penalty, currency, indemnity, etc.) that returns a fairer rewrite + a one-sentence risk explanation.
6. **Aggregation** — all clauses are returned, summarised, charted, and packaged into a downloadable PDF report.

---

## 🌐 API

| Method | Path                          | Purpose                                      |
|-------:|-------------------------------|----------------------------------------------|
| GET    | `/api/status`                 | Engine + model + LLM availability            |
| POST   | `/api/analyze/file`           | Upload `multipart/form-data` (`file`)        |
| POST   | `/api/analyze/text`           | JSON `{text, with_llm}`                      |
| POST   | `/api/analyze/clause`         | JSON `{clause, with_llm}` — single clause    |
| GET    | `/api/jobs/{job_id}`          | Poll progress / fetch results                |
| GET    | `/api/jobs/{job_id}/report`   | Download PDF report (after job completes)    |

Interactive docs at <http://127.0.0.1:8000/docs>.

---

## 📊 Dataset schema

The model is trained on `construction_contracts_dataset.csv`:

| column          | type    | values                                                              |
|-----------------|---------|---------------------------------------------------------------------|
| `text`          | string  | Raw clause text                                                     |
| `risk_level`    | enum    | `high · medium · low · opportunity · neutral`                       |
| `clause_type`   | enum    | payment, delay, indemnity, variation, termination, dispute, …      |
| `one_sided`     | bool    | `true` / `false`                                                    |
| `jurisdiction`  | string  | `UK` / `ZW` / `PH`                                                  |
| `contract_type` | string  | `JCT` / `NEC4` / `FIDIC` / `bespoke`                                |
| `notes`         | string  | Annotator rationale                                                 |

---

## 🔒 Production checklist (if deploying beyond local demo)

- [ ] Rotate the exposed Groq key and store the new one in a secrets manager
- [ ] Replace the in-memory `JOBS` dict with Redis or SQLite
- [ ] Add CORS middleware if hosting frontend separately
- [ ] Put the app behind nginx / Caddy with HTTPS
- [ ] Run with `gunicorn -k uvicorn.workers.UvicornWorker -w 2 backend.app:app` for multiple workers (note: model weights are loaded per worker)
- [ ] Replace the Tailwind CDN with a built CSS bundle for offline / faster loads

---

## 📜 Licence

Academic use only — part of an MSc thesis. Not for redistribution without permission.
