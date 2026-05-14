"""ZimKAG Email Watcher — main polling loop.

For every unread inbox message:
  1. Inspect attachments
  2. For each PDF/DOCX/TXT under the size cap, extract text and count keywords
  3. If ≥ MIN_KEYWORD_HITS distinct construction keywords are found:
       a. Upload to the ZimKAG webapp for analysis
       b. Wait for the analysis job to finish
       c. Download the branded PDF report
       d. Reply (or send) an HTML summary email with the PDF attached
       e. Apply Gmail label 'ZimKAG/Processed'
  4. Otherwise apply 'ZimKAG/Skipped'.

Run:  python -m zimkag_email_watcher.watcher
"""
from __future__ import annotations
import logging
import re
import signal
import sys
import time
from datetime import datetime, timezone
from email.utils import parseaddr
from typing import Optional

from .config import settings
from .filters import extract_text, is_likely_contract, is_supported
from .gmail_client import GmailClient, extract_attachments_meta, header
from .zimkag_client import ZimKAGClient
from .email_builder import build_html, build_subject

log = logging.getLogger("zimkag.watcher")

# Sentinel for clean shutdown
_shutdown = False


def _install_signal_handlers() -> None:
    def _handle(signum, _frame):
        global _shutdown
        log.info("Received signal %s — shutting down after current message.", signum)
        _shutdown = True

    signal.signal(signal.SIGINT, _handle)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _handle)


def _sender_name(from_header: str) -> str:
    name, addr = parseaddr(from_header or "")
    if name:
        return name
    # fallback: local-part of email
    return re.split(r"[._+@]", addr or "")[0].title()


def _sender_address(from_header: str) -> str:
    _, addr = parseaddr(from_header or "")
    return addr


def _process_message(
    gmail: GmailClient,
    zk: ZimKAGClient,
    msg_id: str,
    processed_label_id: str,
    skipped_label_id: str,
    my_address: str,
) -> None:
    """Analyse a single message; label it on success or failure."""
    msg = gmail.get_message(msg_id)
    subject = header(msg, "Subject")
    from_h = header(msg, "From")
    sender_addr = _sender_address(from_h)
    sender_name = _sender_name(from_h)
    thread_id = msg.get("threadId")
    message_id_h = header(msg, "Message-ID") or None

    # Don't process emails the watcher itself sent (avoid feedback loops)
    if sender_addr.lower() == my_address.lower():
        log.debug("Skipping self-sent message id=%s", msg_id)
        gmail.add_label(msg_id, skipped_label_id)
        return

    attachments = extract_attachments_meta(msg)
    if not attachments:
        log.debug("No attachments on msg id=%s subject=%r", msg_id, subject[:60])
        gmail.add_label(msg_id, skipped_label_id)
        return

    log.info("📩 [%s] %r — %d attachment(s)", sender_addr or "unknown", subject[:60], len(attachments))

    analysed_any = False
    for att in attachments:
        fname = att["filename"]
        if not is_supported(fname):
            log.info("   ↳ skip %s (unsupported extension)", fname)
            continue
        size_mb = att["size"] / (1024 * 1024)
        if size_mb > settings.MAX_ATTACHMENT_MB:
            log.info("   ↳ skip %s (%.1f MB > %d MB cap)", fname, size_mb, settings.MAX_ATTACHMENT_MB)
            continue

        try:
            data = gmail.get_attachment_bytes(msg_id, att["attachment_id"])
        except Exception as e:
            log.warning("   ↳ download failed for %s: %s", fname, e)
            continue

        text = extract_text(fname, data)
        if not text or len(text) < 200:
            log.info("   ↳ skip %s (could not extract text)", fname)
            continue

        looks_like_contract, hits, labels = is_likely_contract(
            text, min_hits=settings.MIN_KEYWORD_HITS
        )
        log.info("   ↳ %s — %d keyword hits (%s)", fname, hits, ", ".join(labels[:6]))
        if not looks_like_contract:
            continue

        # ── Hand off to the ZimKAG webapp ────────────────────────────────
        try:
            job, pdf_bytes = zk.analyse_and_report(
                fname, data, with_llm=settings.ZIMKAG_USE_LLM
            )
        except Exception as e:
            log.error("   ↳ ZimKAG analysis failed for %s: %s", fname, e)
            continue

        # ── Compose reply ────────────────────────────────────────────────
        html_body = build_html(
            sender_name=sender_name,
            contract_filename=fname,
            keyword_hits=hits,
            matched_keywords=labels,
            job=job,
        )
        reply_to = sender_addr if settings.REPLY_TO_SENDER else my_address
        reply_subject = build_subject(subject, fname)
        report_name = f"ZimKAG_{re.sub(r'[^a-zA-Z0-9_.-]', '_', fname).rsplit('.', 1)[0]}.pdf"
        attachments_out = [(report_name, pdf_bytes, "application/pdf")]

        if settings.DRY_RUN:
            log.info(
                "   ↳ DRY_RUN: would send to %s subject=%r (PDF %.1f KB)",
                reply_to, reply_subject, len(pdf_bytes) / 1024,
            )
        else:
            try:
                gmail.send_reply(
                    to=reply_to,
                    subject=reply_subject,
                    html_body=html_body,
                    in_reply_to_msg_id=message_id_h,
                    thread_id=thread_id,
                    attachments=attachments_out,
                )
                log.info("   ✅ Sent ZimKAG report to %s", reply_to)
            except Exception as e:
                log.exception("   ↳ Failed to send report email: %s", e)
                continue

        # Persist to the /recent dashboard (best effort — failure here
        # doesn't roll back the email reply that was just sent).
        rid = zk.log_processed_email(
            email={
                "sender_address": sender_addr,
                "sender_name": sender_name,
                "subject": subject,
                "message_id": message_id_h,
                "thread_id": thread_id,
                "received_at": datetime.now(timezone.utc).isoformat(),
            },
            attachment={
                "filename": fname,
                "size_bytes": int(att["size"]),
                "keyword_hits": hits,
                "matched_keywords": labels,
            },
            results=job.get("results", []) or [],
            pdf_bytes=pdf_bytes,
        )
        if rid:
            log.info("   📊 Logged to /recent dashboard (id=%s)", rid)

        analysed_any = True

    label_to_apply = processed_label_id if analysed_any else skipped_label_id
    try:
        gmail.add_label(msg_id, label_to_apply)
    except Exception as e:
        log.warning("Could not label message %s: %s", msg_id, e)


def run() -> None:
    """Main entry — run forever, polling Gmail every POLL_INTERVAL_SEC seconds."""
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    _install_signal_handlers()

    log.info("Booting ZimKAG Email Watcher v1.0…")
    log.info("ZimKAG webapp: %s", settings.ZIMKAG_URL)
    log.info("Poll interval: %ds  ·  Min keyword hits: %d  ·  Max attachment: %d MB",
             settings.POLL_INTERVAL_SEC, settings.MIN_KEYWORD_HITS, settings.MAX_ATTACHMENT_MB)
    log.info("Reply-to-sender: %s  ·  Dry-run: %s",
             settings.REPLY_TO_SENDER, settings.DRY_RUN)

    # Pre-flight checks
    gmail = GmailClient()
    my_addr = gmail.me()
    log.info("✅ Authenticated as %s", my_addr)

    zk = ZimKAGClient()
    if not zk.is_healthy():
        log.error(
            "ZimKAG webapp is not reachable at %s. "
            "Start it (run.bat) and ensure ZIMKAG_URL in .env is correct.",
            settings.ZIMKAG_URL,
        )
        sys.exit(1)
    s = zk.status()
    log.info("✅ ZimKAG online — model_loaded=%s, llm_enabled=%s",
             s.get("model_loaded"), s.get("llm_enabled"))

    processed_id = gmail.get_or_create_label(settings.LABEL_PROCESSED)
    skipped_id = gmail.get_or_create_label(settings.LABEL_SKIPPED)

    log.info("──── Watching inbox · Ctrl+C to stop ────")
    while not _shutdown:
        try:
            msg_ids = gmail.list_candidate_messages()
            if msg_ids:
                log.info("Found %d candidate message(s) this poll.", len(msg_ids))
            for mid in msg_ids:
                if _shutdown:
                    break
                try:
                    _process_message(gmail, zk, mid, processed_id, skipped_id, my_addr)
                except Exception:
                    log.exception("Unhandled error processing message id=%s", mid)
        except Exception:
            log.exception("Polling cycle failed; will retry in %ds.", settings.POLL_INTERVAL_SEC)

        if _shutdown:
            break
        # Sleep but stay responsive to signals
        for _ in range(settings.POLL_INTERVAL_SEC):
            if _shutdown:
                break
            time.sleep(1)

    log.info("Watcher stopped cleanly.")


if __name__ == "__main__":
    run()
