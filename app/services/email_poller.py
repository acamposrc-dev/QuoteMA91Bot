"""Poller de la casilla de la empresa (Gmail API), corre cada 15 min via Celery Beat.

Filtro SIN LLM: asunto con keywords configurables + remitente en whitelist (si hay)
+ adjunto presente o cuerpo con contenido. Deduplicacion por Message-ID (unique en DB)
y por hash del adjunto.
"""

import base64
import hashlib
import os
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models import QuoteRequest, RequestSource, RequestStatus

log = get_logger(__name__)
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


def _gmail_service():
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build

    creds = Credentials.from_authorized_user_file(settings.gmail_token_json, SCOPES)
    return build("gmail", "v1", credentials=creds)


def _matches_filters(subject: str, sender: str) -> bool:
    subject_l = subject.lower()
    if not any(k in subject_l for k in settings.subject_keywords):
        return False
    whitelist = [s.strip().lower() for s in settings.quote_sender_whitelist.split(",") if s.strip()]
    if whitelist and not any(w in sender.lower() for w in whitelist):
        return False
    return True


def poll_inbox() -> list[str]:
    """Devuelve los IDs de QuoteRequest creados en esta pasada."""
    service = _gmail_service()
    query = "in:inbox is:unread has:attachment"
    resp = service.users().messages().list(userId="me", q=query, maxResults=20).execute()
    created: list[str] = []

    for ref in resp.get("messages", []):
        msg = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        subject = headers.get("subject", "")
        sender = headers.get("from", "")
        message_id = headers.get("message-id", ref["id"])

        if not _matches_filters(subject, sender):
            continue

        attachment = _first_attachment(service, msg)
        if attachment is None:
            continue
        filename, content = attachment
        doc_hash = hashlib.sha256(content).hexdigest()

        with SessionLocal() as db:
            exists = db.query(QuoteRequest).filter(
                (QuoteRequest.email_message_id == message_id)
                | (QuoteRequest.document_hash == doc_hash)
            ).first()
            if exists:
                continue

            os.makedirs(os.path.join(settings.storage_dir, "uploads"), exist_ok=True)
            path = os.path.join(settings.storage_dir, "uploads", f"{doc_hash[:16]}_{filename}")
            with open(path, "wb") as f:
                f.write(content)

            req = QuoteRequest(
                source=RequestSource.EMAIL,
                status=RequestStatus.RECEIVED,
                email_message_id=message_id,
                email_thread_id=msg.get("threadId"),
                reply_to=sender,
                document_hash=doc_hash,
                raw_document_path=path,
                original_filename=filename,
            )
            db.add(req)
            db.commit()
            created.append(req.id)
            log.info("email_request_created", request_id=req.id, subject=subject)

        service.users().messages().modify(
            userId="me", id=ref["id"], body={"removeLabelIds": ["UNREAD"]}
        ).execute()

    return created


def _first_attachment(service, msg) -> tuple[str, bytes] | None:
    for part in msg["payload"].get("parts", []) or []:
        filename = part.get("filename")
        body = part.get("body", {})
        if filename and body.get("attachmentId"):
            att = service.users().messages().attachments().get(
                userId="me", messageId=msg["id"], id=body["attachmentId"]
            ).execute()
            return filename, base64.urlsafe_b64decode(att["data"])
    return None


def send_report_reply(request: QuoteRequest) -> None:
    """Responde al hilo original con el Excel adjunto."""
    service = _gmail_service()
    mime = MIMEMultipart()
    mime["To"] = request.reply_to
    mime["Subject"] = "Re: Cotizacion procesada"
    mime.attach(MIMEText(
        "Adjuntamos la cotizacion con las mejores opciones encontradas por item.\n"
        "Los items con menos de 4 opciones o sin resultados estan marcados en el archivo.",
        "plain",
    ))
    with open(request.report_path, "rb") as f:
        part = MIMEApplication(f.read(), _subtype="xlsx")
    part.add_header("Content-Disposition", "attachment",
                    filename=os.path.basename(request.report_path))
    mime.attach(part)

    service.users().messages().send(
        userId="me",
        body={"raw": base64.urlsafe_b64encode(mime.as_bytes()).decode(),
              "threadId": request.email_thread_id},
    ).execute()
    log.info("report_reply_sent", request_id=request.id)
