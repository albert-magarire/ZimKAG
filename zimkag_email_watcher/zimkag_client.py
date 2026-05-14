"""HTTP client for the ZimKAG webapp."""
from __future__ import annotations
import logging
import time
from typing import Any, Optional

import requests

from .config import settings

log = logging.getLogger(__name__)


class ZimKAGClient:
    """Thin wrapper around the ZimKAG webapp REST API.

    Workflow:
        1. POST /api/analyze/file → returns job_id
        2. Poll  /api/jobs/{id}    → wait for status == "done"
        3. GET   /api/jobs/{id}/report → PDF bytes
    """

    def __init__(self, base_url: Optional[str] = None) -> None:
        self.base_url = (base_url or settings.ZIMKAG_URL).rstrip("/")
        self.session = requests.Session()

    # ── Status ───────────────────────────────────────────────────────────
    def status(self) -> dict[str, Any]:
        r = self.session.get(f"{self.base_url}/api/status", timeout=10)
        r.raise_for_status()
        return r.json()

    def is_healthy(self) -> bool:
        try:
            s = self.status()
            return bool(s.get("ok"))
        except Exception as e:
            log.warning("ZimKAG webapp not reachable at %s: %s", self.base_url, e)
            return False

    # ── Analyse ──────────────────────────────────────────────────────────
    def analyse_file(self, filename: str, data: bytes, with_llm: bool = True) -> str:
        """Upload a contract and return the job_id."""
        files = {"file": (filename, data, "application/octet-stream")}
        params = {"with_llm": "true" if with_llm else "false"}
        r = self.session.post(
            f"{self.base_url}/api/analyze/file",
            files=files,
            data=params,
            timeout=60,
        )
        r.raise_for_status()
        job = r.json()
        return job["job_id"]

    def wait_for_job(
        self,
        job_id: str,
        poll_sec: float = 2.0,
        timeout_sec: Optional[int] = None,
    ) -> dict[str, Any]:
        """Block until job finishes or timeout. Returns final job dict.

        Resilient to transient connection drops (Windows tends to RST idle
        keep-alive sockets after ~50 reuses) — we retry a few times before
        giving up.
        """
        timeout_sec = timeout_sec or settings.ZIMKAG_TIMEOUT
        start = time.time()
        last_progress = -1
        consecutive_errors = 0
        MAX_CONSECUTIVE_ERRORS = 5

        while True:
            try:
                r = self.session.get(f"{self.base_url}/api/jobs/{job_id}", timeout=20)
                r.raise_for_status()
                job = r.json()
                consecutive_errors = 0  # success — clear the streak
            except Exception as e:
                consecutive_errors += 1
                log.warning(
                    "Transient error polling job %s (try %d/%d): %s",
                    job_id, consecutive_errors, MAX_CONSECUTIVE_ERRORS, e,
                )
                if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                    raise
                # Rebuild the session so we don't reuse a dead pooled socket
                try:
                    self.session.close()
                except Exception:
                    pass
                self.session = requests.Session()
                time.sleep(min(2 ** consecutive_errors, 8))  # backoff: 2,4,8,8,8s
                continue

            if job.get("progress", -1) != last_progress:
                last_progress = job["progress"]
                log.info(
                    "Job %s … %d%% (%d/%d)",
                    job_id, job["progress"], job["done"], job["total"],
                )
            if job.get("status") == "done":
                return job
            if time.time() - start > timeout_sec:
                raise TimeoutError(
                    f"ZimKAG job {job_id} did not complete within {timeout_sec}s"
                )
            time.sleep(poll_sec)

    def download_report(self, job_id: str) -> bytes:
        r = self.session.get(
            f"{self.base_url}/api/jobs/{job_id}/report",
            timeout=30,
            stream=True,
        )
        r.raise_for_status()
        return r.content

    # ── Convenience one-shot ─────────────────────────────────────────────
    def analyse_and_report(
        self,
        filename: str,
        data: bytes,
        with_llm: bool = True,
    ) -> tuple[dict[str, Any], bytes]:
        """Run an end-to-end analysis. Returns (results_job_dict, pdf_bytes)."""
        job_id = self.analyse_file(filename, data, with_llm=with_llm)
        log.info("Started ZimKAG job %s for %s", job_id, filename)
        job = self.wait_for_job(job_id)
        pdf = self.download_report(job_id)
        return job, pdf

    # ── Recent dashboard logging ─────────────────────────────────────────
    def log_processed_email(
        self,
        *,
        email: dict[str, Any],
        attachment: dict[str, Any],
        results: list[dict[str, Any]],
        pdf_bytes: bytes,
    ) -> Optional[str]:
        """Persist one processed email to the webapp's /recent dashboard.

        Returns the new row id on success, or None if logging failed (the
        watcher should not abort the whole pipeline on this).
        """
        import json
        try:
            metadata = json.dumps({
                "email": email,
                "attachment": attachment,
                "results": results,
            })
            r = self.session.post(
                f"{self.base_url}/api/recent",
                data={"metadata": metadata},
                files={"report": ("report.pdf", pdf_bytes, "application/pdf")},
                timeout=30,
            )
            r.raise_for_status()
            return r.json().get("id")
        except Exception as e:
            log.warning("Failed to log processed email to /recent: %s", e)
            # Reset session so the next request doesn't reuse a broken pooled
            # connection (Windows sometimes closes the socket after a 5xx).
            try:
                self.session.close()
            except Exception:
                pass
            self.session = requests.Session()
            return None
