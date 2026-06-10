"""Tareas Celery: el pipeline completo.

poll_email -> process_request -> chord(process_item x N) -> finalize_request
"""

from datetime import datetime, timezone

from celery import chord

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models import (
    ItemStatus, ParseMethod, QuoteItem, QuoteRequest, RequestStatus,
)
from app.services.agent.search_agent import run_search_agent
from app.services.parsing.dispatcher import parse_document
from app.services.ranker import rank_and_build_options
from app.services.report_builder import build_report
from app.workers.celery_app import celery_app

configure_logging()
log = get_logger(__name__)


@celery_app.task
def poll_email() -> list[str]:
    from app.services.email_poller import poll_inbox

    created = poll_inbox()
    for request_id in created:
        process_request.delay(request_id)
    return created


@celery_app.task(bind=True, max_retries=2)
def process_request(self, request_id: str) -> None:
    with SessionLocal() as db:
        req = db.get(QuoteRequest, request_id)
        if req is None:
            return
        req.status = RequestStatus.PARSING
        db.commit()

        try:
            with open(req.raw_document_path, "rb") as f:
                content = f.read()
            result = parse_document(req.original_filename or "documento.txt", content,
                                    request_id=request_id)
        except Exception as exc:
            req.status = RequestStatus.PARSE_ERROR
            req.error = str(exc)
            db.commit()
            log.error("parse_error", request_id=request_id, error=str(exc))
            return

        req.parse_method = ParseMethod(result.method)
        item_ids: list[str] = []
        for parsed in result.items:
            item = QuoteItem(
                request_id=req.id,
                name=parsed.name,
                description=parsed.description,
                quantity=parsed.quantity,
                preferred_brand=parsed.preferred_brand,
                specs=parsed.specs,
            )
            db.add(item)
            db.flush()
            item_ids.append(item.id)
        req.status = RequestStatus.SEARCHING
        db.commit()

    chord(process_item.s(item_id) for item_id in item_ids)(finalize_request.s(request_id))


@celery_app.task(bind=True, max_retries=1, soft_time_limit=900)
def process_item(self, item_id: str) -> str:
    with SessionLocal() as db:
        item = db.get(QuoteItem, item_id)
        if item is None:
            return item_id
        item.status = ItemStatus.SEARCHING
        db.commit()

        try:
            result = run_search_agent(item)
            options = rank_and_build_options(item.id, result.valid)
            for opt in options:
                db.add(opt)
            item.searches_used = result.searches_used
            if len(options) >= 4:
                item.status = ItemStatus.COMPLETED
            elif options:
                item.status = ItemStatus.PARTIAL
            else:
                item.status = ItemStatus.NO_RESULTS
            db.commit()
            log.info("item_done", item_id=item_id, status=item.status.value,
                     options=len(options), searches=result.searches_used)
        except Exception as exc:
            item.status = ItemStatus.FAILED
            db.commit()
            log.error("item_failed", item_id=item_id, error=str(exc))
            raise
    return item_id


@celery_app.task
def finalize_request(_item_ids: list[str], request_id: str) -> None:
    with SessionLocal() as db:
        req = db.get(QuoteRequest, request_id)
        if req is None:
            return
        req.report_path = build_report(req)
        req.status = RequestStatus.COMPLETED
        req.completed_at = datetime.now(timezone.utc)
        db.commit()

        if req.source.value == "EMAIL" and req.reply_to:
            try:
                from app.services.email_poller import send_report_reply
                send_report_reply(req)
            except Exception as exc:
                log.error("reply_failed", request_id=request_id, error=str(exc))
        log.info("request_completed", request_id=request_id, report=req.report_path)
