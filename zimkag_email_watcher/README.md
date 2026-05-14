# 📧 ZimKAG Email Watcher

**Auto-analyse construction contracts received by email.** A background Python service that watches your Gmail inbox, detects PDF/DOCX/TXT attachments that look like construction contracts (using a keyword pre-filter), runs them through the ZimKAG analysis pipeline, and sends a beautifully-formatted summary email back into the inbox with the full PDF report attached.

> Companion service to the [ZimKAG webapp](../zimkag_webapp/) — same MSc Quantity Surveying research project, just triggered by email instead of by drag-and-drop.

---

## What it does

```
   📬 Email arrives                ☁️ ZimKAG webapp           📧 Reply lands in inbox
  ┌────────────────┐    keywords  ┌──────────────────┐  PDF  ┌────────────────────┐
  │ subject: "RFQ" │ ──► detected ──► /api/analyze/file ──► │ ZimKAG Risk Report │
  │ contract.pdf   │   ≥ 3 hits    │ Legal-BERT + KG    │     │ • 12 high risk    │
  └────────────────┘               └──────────────────┘      │ • 3 opportunities  │
                                                              │ • PDF attached    │
                                                              └────────────────────┘
```

Concretely the watcher will:

1. **Poll** your Gmail inbox every 30 s for unread messages with attachments.
2. **Pre-filter** each attachment: extract text and count distinct construction-contract keywords (variation, payment, retention, LDs, defects, force majeure, FIDIC, NEC4, JCT…). The default threshold is **≥ 3 distinct keywords**.
3. **Analyse** matching documents via your local ZimKAG webapp (`/api/analyze/file` → `/api/jobs/{id}`).
4. **Reply** with a self-contained HTML email summary (risk pills, top high-risk clauses, top opportunities, suggested rewrites) plus the **full PDF report attached**.
5. **Label** the original message `ZimKAG/Processed` (or `ZimKAG/Skipped`) so it is never analysed twice.

---

## Prerequisites

| Requirement              | Notes                                                    |
|--------------------------|----------------------------------------------------------|
| Python 3.10+             | Same as the webapp                                       |
| ZimKAG webapp **running** | Required — provides the analysis API                    |
| A Gmail account          | Personal Gmail or Google Workspace                       |
| Google Cloud project     | One-time OAuth setup (see [credentials/README.md](credentials/README.md)) |

---

## 🚀 Setup (one-time, ≈ 5 minutes)

### 1 · Set up Gmail OAuth credentials

Follow the step-by-step guide at **[`credentials/README.md`](credentials/README.md)** to:
- Create a Google Cloud project
- Enable the Gmail API
- Configure the OAuth consent screen
- Download `client_secret.json` and drop it into `credentials/`

### 2 · Make sure the ZimKAG webapp is running

```bat
cd ..\zimkag_webapp
run.bat
```

Confirm <http://127.0.0.1:18000/api/status> returns `"model_loaded": true`.

### 3 · Configure the watcher

```bat
cd ..\zimkag_email_watcher
copy .env.example .env
notepad .env
```

Key settings:

| Variable             | Default                     | Notes                                                 |
|----------------------|-----------------------------|-------------------------------------------------------|
| `ZIMKAG_URL`         | `http://127.0.0.1:18000`    | Where the webapp is listening                         |
| `MIN_KEYWORD_HITS`   | `3`                         | Lower → catch more; higher → fewer false positives   |
| `POLL_INTERVAL_SEC`  | `30`                        | How often Gmail is polled                             |
| `MAX_ATTACHMENT_MB`  | `25`                        | Skip oversized files                                  |
| `REPLY_TO_SENDER`    | `false`                     | `false` → report goes to **your** inbox (safer)       |
| `DRY_RUN`            | `false`                     | `true` → run analysis but don't send the email        |

### 4 · Start the watcher

```bat
run_watcher.bat
```

First run opens a browser to authorise Gmail access. After that the watcher runs silently and prints a one-line log per polled message:

```
2026-05-02 12:14:03 [INFO] zimkag.watcher: 📩 [supplier@acme.com] "Tender — Phase 2 Works" — 1 attachment(s)
2026-05-02 12:14:04 [INFO] zimkag.watcher:    ↳ Phase2_Contract.pdf — 18 keyword hits (contractor, payment, variation, …)
2026-05-02 12:14:05 [INFO] zimkag.watcher: Started ZimKAG job 7c3f88aa for Phase2_Contract.pdf
2026-05-02 12:14:42 [INFO] zimkag.watcher: Job 7c3f88aa … 100% (87/87)
2026-05-02 12:14:43 [INFO] zimkag.watcher:    ✅ Sent ZimKAG report to albertmagarire@gmail.com
```

Stop with **Ctrl + C** — the watcher finishes the current message cleanly first.

---

## 🧪 Try it without sending anything

```dotenv
DRY_RUN=true
```

The watcher will still authenticate, scan, pre-filter, run the analysis through the webapp, and log what it *would* have sent — but no email leaves your account.

---

## 📂 File layout

```
zimkag_email_watcher/
├── watcher.py            # Main polling loop + orchestration
├── gmail_client.py       # OAuth + Gmail API wrapper
├── zimkag_client.py      # HTTP client for the ZimKAG webapp
├── filters.py            # Construction keyword library + text extraction
├── email_builder.py      # HTML reply email composer
├── config.py             # .env-driven settings
├── credentials/
│   ├── README.md         # OAuth setup (5-minute guide)
│   ├── client_secret.json   # ← you provide (gitignored)
│   └── token.json           # written after first auth (gitignored)
├── .env.example
├── requirements.txt
├── run_watcher.bat       # Windows launcher (auto-installs venv)
├── run_watcher.sh        # macOS / Linux launcher
└── README.md
```

---

## 🔑 Keyword library

The pre-filter recognises **70+ construction-contract terms** grouped into:

| Group                | Examples                                                   |
|----------------------|------------------------------------------------------------|
| Parties & roles      | Contractor, Employer, Engineer, Quantity Surveyor          |
| Core concepts        | Variation, Payment, Retention, Liquidated Damages, Defects |
| Pricing & financial  | Contract Sum, BOQ, Interim Payment, Final Account          |
| Programme & site     | Programme, Completion Date, As-Built, Snagging             |
| Securities           | Performance Bond, Bank Guarantee, Advance Payment          |
| Contract standards   | JCT, NEC4, FIDIC (Red/Yellow/Silver Book)                  |
| Risk language        | Indemnify, Warranty, Breach, Set-off, Pay-when-paid        |

Each pattern is regex-based, case-insensitive, and word-bounded. **Synonyms collapse to a single label** (e.g. `EOT` and `extension of time` both count as one hit). Edit `filters.py` to expand or trim the library.

---

## 🛡️ Safety & privacy

| Concern                   | What ZimKAG does                                                                 |
|---------------------------|----------------------------------------------------------------------------------|
| Gmail access scope        | `gmail.modify` only — never `gmail.send` to other domains without your `REPLY_TO_SENDER=true` opt-in |
| Self-loop prevention      | Skips emails sent by the authenticated address                                   |
| Duplicate processing      | Uses `ZimKAG/Processed` and `ZimKAG/Skipped` labels as idempotency keys          |
| OAuth refresh tokens      | Stored locally in `credentials/token.json`, gitignored                           |
| Attachment confidentiality| Contracts are processed locally by your ZimKAG webapp; only clause text is sent to Groq (LLM) — and only for rewrite suggestions, not storage |
| Failed analyses           | Logged but the message is still labelled `ZimKAG/Skipped` so it doesn't re-process |

To revoke access at any time:
- **Locally:** delete `credentials/token.json`
- **Server-side:** <https://myaccount.google.com/permissions> → *ZimKAG Email Watcher* → Remove access

---

## 🐞 Troubleshooting

| Symptom                                              | Fix                                                                 |
|------------------------------------------------------|---------------------------------------------------------------------|
| `Missing OAuth client secret`                        | Follow `credentials/README.md` step-by-step.                        |
| `ZimKAG webapp is not reachable`                     | Start `..\zimkag_webapp\run.bat` first; check `ZIMKAG_URL`.        |
| Browser opens but says "Access blocked: app not verified" | You forgot to add your address as a *Test user* in the OAuth consent screen. Go back to step 3 of `credentials/README.md`. |
| Watcher runs but never picks up an email             | Check Gmail labels — if `ZimKAG/Processed` is already applied, remove it. The search query also requires the email to be **unread** and **have an attachment**. |
| Same message processed twice                         | Label creation failed — check the API error log; usually fixed by re-running. |
| Report email looks plain                             | Some clients (older Outlook, Gmail dark theme) tweak inline CSS. The PDF attachment is always fully formatted. |

---

## 🛣 Roadmap / extension ideas

- [ ] **Outlook variant** using Microsoft Graph (parallel `outlook_client.py` keeping the same abstractions)
- [ ] **Webhook push** instead of polling (Gmail watch + Pub/Sub)
- [ ] **Per-sender allow-list / block-list** to limit who triggers analyses
- [ ] **Dashboard** of historical analyses (Streamlit / FastAPI)
- [ ] **Slack / WhatsApp** notifications in parallel with the email reply
- [ ] **Auto-archive** the original email once a report has been sent

---

<div align="center">

Part of [**ZimKAG**](../README.md) · MSc Quantity Surveying · University of Zimbabwe

</div>
