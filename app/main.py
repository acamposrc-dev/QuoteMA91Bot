from fastapi import FastAPI

from app.api.routes import router
from app.core.logging import configure_logging

configure_logging()

app = FastAPI(title="QuoteBot", version="0.1.0")
app.include_router(router, prefix="/api/v1")


@app.get("/health")
def health():
    return {"status": "ok"}
