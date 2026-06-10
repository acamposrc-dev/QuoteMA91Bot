import hashlib
import os

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import QuoteRequest, RequestSource, RequestStatus
from app.schemas.quote import RequestCreated, RequestOut
from app.workers.tasks import process_request

router = APIRouter()

ALLOWED_EXT = (".xlsx", ".xlsm", ".csv", ".tsv", ".pdf", ".docx", ".txt", ".eml")


@router.post("/requests/upload", response_model=RequestCreated, status_code=202)
async def upload_document(file: UploadFile, db: Session = Depends(get_db)):
    if not file.filename or not file.filename.lower().endswith(ALLOWED_EXT):
        raise HTTPException(415, f"Formato no soportado. Permitidos: {ALLOWED_EXT}")

    content = await file.read()
    if not content:
        raise HTTPException(400, "Archivo vacio")
    doc_hash = hashlib.sha256(content).hexdigest()

    duplicate = (
        db.query(QuoteRequest)
        .filter(QuoteRequest.document_hash == doc_hash,
                QuoteRequest.status != RequestStatus.PARSE_ERROR)
        .first()
    )
    if duplicate:
        return RequestCreated(id=duplicate.id, status=f"DUPLICATED:{duplicate.status.value}")

    os.makedirs(os.path.join(settings.storage_dir, "uploads"), exist_ok=True)
    path = os.path.join(settings.storage_dir, "uploads", f"{doc_hash[:16]}_{file.filename}")
    with open(path, "wb") as f:
        f.write(content)

    req = QuoteRequest(
        source=RequestSource.UPLOAD,
        document_hash=doc_hash,
        raw_document_path=path,
        original_filename=file.filename,
    )
    db.add(req)
    db.commit()

    process_request.delay(req.id)
    return RequestCreated(id=req.id, status=req.status.value)


@router.get("/requests/{request_id}", response_model=RequestOut)
def get_request(request_id: str, db: Session = Depends(get_db)):
    req = db.get(QuoteRequest, request_id)
    if req is None:
        raise HTTPException(404, "Request no encontrado")
    return req


@router.get("/requests/{request_id}/report")
def download_report(request_id: str, db: Session = Depends(get_db)):
    req = db.get(QuoteRequest, request_id)
    if req is None or not req.report_path or not os.path.exists(req.report_path):
        raise HTTPException(404, "Reporte no disponible (todavia)")
    return FileResponse(
        req.report_path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=os.path.basename(req.report_path),
    )
