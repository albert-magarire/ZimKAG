"""FastAPI application entrypoint for the ZimKAG web interface."""
from __future__ import annotations
import asyncio
import logging
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, Form
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .config import settings
from .extraction import extract_text, split_clauses
from .inference import get_engine
from .reports import build_report
from . import storage

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("zimkag")

# In-memory job store for async analysis (good enough for single-user MSc demo;
# swap for Redis if you ever go multi-user).
JOBS: Dict[str, Dict[str, Any]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting ZimKAG…")
    log.info("Model dir: %s", settings.MODEL_DIR)
    storage.init_db()
    try:
        get_engine()
        log.info("Engine ready.")
    except FileNotFoundError as e:
        log.warning("%s", e)
    yield
    log.info("Shutting down.")


app = FastAPI(
    title="ZimKAG – Contract Risk Analyser",
    description="Supervised NLP for Risk & Opportunity detection in bespoke "
                "construction contracts (MSc Quantity Surveying, UZ).",
    version="1.0.0",
    lifespan=lifespan,
)


# ── API models ───────────────────────────────────────────────────────────────

class TextAnalyzeRequest(BaseModel):
    text: str
    with_llm: bool = True


class ClauseAnalyzeRequest(BaseModel):
    clause: str
    with_llm: bool = True


# ── Routes ───────────────────────────────────────────────────────────────────

@app.get("/api/status")
async def status() -> Dict[str, Any]:
    try:
        eng = get_engine()
        return {
            "ok": True,
            **eng.status(),
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
            "max_clauses": settings.MAX_CLAUSES,
        }
    except Exception as e:
        return {"ok": False, "error": str(e), "model_dir": str(settings.MODEL_DIR)}


@app.post("/api/analyze/clause")
async def analyze_clause(req: ClauseAnalyzeRequest) -> Dict[str, Any]:
    if not req.clause.strip():
        raise HTTPException(400, "clause is empty")
    eng = get_engine()
    return eng.analyze(req.clause, with_llm=req.with_llm)


def _start_job(clauses: List[str], filename: str, with_llm: bool) -> str:
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {
        "id": job_id,
        "filename": filename,
        "total": len(clauses),
        "done": 0,
        "results": [],
        "status": "running",
        "started": time.time(),
        "report_path": None,
        "error": None,
    }

    async def run():
        eng = get_engine()
        for i, c in enumerate(clauses):
            try:
                JOBS[job_id]["results"].append(eng.analyze(c, with_llm=with_llm))
            except Exception as e:
                log.exception("analysis failed for clause %d", i)
                JOBS[job_id]["results"].append({
                    "clause": c, "risk_level": "low", "risk_label": "Error",
                    "risk_icon": "⚠️", "risk_color": "#6b7280",
                    "confidence": 0.0, "all_probabilities": {},
                    "clause_type": "administrative", "kg_match": None,
                    "kg_suggestion": "", "explanation": f"Error: {e}",
                    "interpretation": "Analysis failed for this clause.",
                    "suggested_rewrite": c,
                })
            JOBS[job_id]["done"] = i + 1
            # Yield control every few clauses so progress polls stay snappy
            if (i + 1) % 3 == 0:
                await asyncio.sleep(0)
        try:
            path = await asyncio.to_thread(build_report, JOBS[job_id]["results"], filename)
            JOBS[job_id]["report_path"] = str(path)
        except Exception as e:
            log.exception("report generation failed")
            JOBS[job_id]["error"] = f"Report generation failed: {e}"
        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["finished"] = time.time()

    asyncio.create_task(run())
    return job_id


@app.post("/api/analyze/file")
async def analyze_file(file: UploadFile = File(...), with_llm: str = Form("true")) -> Dict[str, Any]:
    data = await file.read()
    size_mb = len(data) / (1024 * 1024)
    if size_mb > settings.MAX_FILE_SIZE_MB:
        raise HTTPException(413, f"File too large ({size_mb:.1f} MB > {settings.MAX_FILE_SIZE_MB} MB)")

    try:
        raw = extract_text(file.filename, data)
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        log.exception("extraction failed")
        raise HTTPException(500, f"Could not parse {file.filename}: {e}")

    clauses = split_clauses(raw)
    if not clauses:
        raise HTTPException(400, "No clauses could be extracted from the document.")

    use_llm = with_llm.lower() == "true"
    job_id = _start_job(clauses, file.filename, use_llm)
    return {"job_id": job_id, "filename": file.filename, "total_clauses": len(clauses)}


@app.post("/api/analyze/text")
async def analyze_text(req: TextAnalyzeRequest) -> Dict[str, Any]:
    if not req.text.strip():
        raise HTTPException(400, "text is empty")
    clauses = split_clauses(req.text)
    if not clauses:
        raise HTTPException(400, "No clauses could be extracted from the supplied text.")
    job_id = _start_job(clauses, "Pasted text", req.with_llm)
    return {"job_id": job_id, "filename": "Pasted text", "total_clauses": len(clauses)}


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str) -> Dict[str, Any]:
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return {
        "id": job["id"],
        "filename": job["filename"],
        "status": job["status"],
        "total": job["total"],
        "done": job["done"],
        "progress": round(100 * job["done"] / max(job["total"], 1), 1),
        "results": job["results"] if job["status"] == "done" else None,
        "report_available": job["status"] == "done" and bool(job["report_path"]),
        "error": job["error"],
    }


@app.get("/api/jobs/{job_id}/report")
async def job_report(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    if job["status"] != "done":
        raise HTTPException(409, "Job still running")
    if not job["report_path"]:
        raise HTTPException(500, job.get("error") or "Report unavailable")
    fname = Path(job["filename"]).stem or "contract"
    return FileResponse(
        job["report_path"],
        media_type="application/pdf",
        filename=f"ZimKAG_{fname}.pdf",
    )


# ── Recent dashboard (watcher-processed emails) ──────────────────────────────

@app.post("/api/recent")
async def log_processed(
    metadata: str = Form(...),
    report: UploadFile = File(...),
) -> Dict[str, Any]:
    """Called by the email-watcher after a successful analysis.

    `metadata` is a JSON string with shape:
        { "email": {...}, "attachment": {...}, "results": [...] }
    `report` is the PDF file produced by the webapp for that analysis.
    """
    import json as _json
    try:
        meta = _json.loads(metadata)
    except _json.JSONDecodeError as e:
        raise HTTPException(400, f"metadata is not valid JSON: {e}")

    if "email" not in meta or "attachment" not in meta or "results" not in meta:
        raise HTTPException(400, "metadata must contain email, attachment, results")
    if not isinstance(meta["results"], list):
        raise HTTPException(400, "metadata.results must be a list")

    pdf_bytes = await report.read()
    if len(pdf_bytes) == 0:
        raise HTTPException(400, "report file is empty")

    rid = storage.insert_processed(
        email=meta["email"] or {},
        attachment=meta["attachment"] or {},
        results=meta["results"] or [],
        pdf_bytes=pdf_bytes,
    )
    return {"id": rid, "ok": True}


@app.get("/api/recent")
async def list_recent(
    limit: int = 20,
    offset: int = 0,
    q: Optional[str] = None,
    risk: Optional[str] = None,
) -> Dict[str, Any]:
    limit = max(1, min(100, int(limit)))
    offset = max(0, int(offset))
    rows, total = storage.list_recent(limit=limit, offset=offset, q=q, risk=risk)
    return {
        "items": rows,
        "total": total,
        "limit": limit,
        "offset": offset,
        "stats": storage.summary_stats(),
    }


@app.get("/api/recent/{rid}")
async def get_recent_detail(rid: str) -> Dict[str, Any]:
    row = storage.get_recent(rid)
    if not row:
        raise HTTPException(404, "Not found")
    return row


@app.get("/api/recent/{rid}/report")
async def get_recent_report(rid: str):
    p = storage.report_path(rid)
    if not p:
        raise HTTPException(404, "Report file missing")
    row = storage.get_recent(rid)
    stem = (row["filename"] if row else "contract").rsplit(".", 1)[0] or "contract"
    return FileResponse(str(p), media_type="application/pdf",
                        filename=f"ZimKAG_{stem}.pdf")


# ── Static frontend ──────────────────────────────────────────────────────────

if settings.FRONTEND_DIR.exists():
    app.mount(
        "/static",
        StaticFiles(directory=str(settings.FRONTEND_DIR)),
        name="static",
    )

    @app.get("/", response_class=HTMLResponse)
    async def index():
        idx = settings.FRONTEND_DIR / "index.html"
        if not idx.exists():
            return HTMLResponse("<h1>frontend/index.html missing</h1>", status_code=500)
        return HTMLResponse(idx.read_text(encoding="utf-8"))

    @app.get("/recent", response_class=HTMLResponse)
    async def recent_page():
        page = settings.FRONTEND_DIR / "recent.html"
        if not page.exists():
            return HTMLResponse("<h1>frontend/recent.html missing</h1>", status_code=500)
        return HTMLResponse(page.read_text(encoding="utf-8"))


@app.exception_handler(Exception)
async def global_handler(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(status_code=500, content={"detail": str(exc)})


# ── CLI entry ────────────────────────────────────────────────────────────────

def main() -> None:
    import uvicorn
    uvicorn.run(
        "backend.app:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()
