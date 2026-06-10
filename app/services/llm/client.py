"""Capa LLM agnostica de proveedor.

El resto de la aplicacion NUNCA importa anthropic/openai/litellm directamente.
Cada llamada se hace por *rol* (parser_fallback, matcher, extractor_fallback,
query_reformulator) y el modelo concreto se resuelve desde settings/.env, lo
que permite mezclar Anthropic, OpenAI, DeepSeek, Gemini, Ollama, etc.
"""

from typing import TypeVar

import instructor
import litellm
from litellm import completion, completion_cost
from pydantic import BaseModel

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)

litellm.drop_params = True  # ignora params no soportados por algun proveedor

_structured_client = instructor.from_litellm(completion)

T = TypeVar("T", bound=BaseModel)


def _track(role: str, model: str, response, request_id: str | None, item_id: str | None) -> None:
    """Persiste tokens y costo de la llamada en llm_logs (best effort)."""
    try:
        usage = getattr(response, "usage", None)
        cost = 0.0
        try:
            cost = completion_cost(completion_response=response) or 0.0
        except Exception:
            pass
        from app.db.session import SessionLocal
        from app.models.quote import LLMLog

        with SessionLocal() as db:
            db.add(
                LLMLog(
                    request_id=request_id,
                    item_id=item_id,
                    role=role,
                    model=model,
                    tokens_in=getattr(usage, "prompt_tokens", 0) or 0,
                    tokens_out=getattr(usage, "completion_tokens", 0) or 0,
                    cost_usd=cost,
                )
            )
            db.commit()
    except Exception:
        log.warning("llm_log_failed", role=role, model=model)


def structured(
    role: str,
    messages: list[dict],
    schema: type[T],
    *,
    request_id: str | None = None,
    item_id: str | None = None,
    max_retries: int = 2,
) -> T:
    """Llamada con salida estructurada validada por Pydantic, en cualquier proveedor."""
    model = settings.model_for(role)
    result, raw = _structured_client.chat.completions.create_with_completion(
        model=model,
        messages=messages,
        response_model=schema,
        max_retries=max_retries,
    )
    _track(role, model, raw, request_id, item_id)
    return result


def text(
    role: str,
    messages: list[dict],
    *,
    request_id: str | None = None,
    item_id: str | None = None,
) -> str:
    model = settings.model_for(role)
    resp = completion(model=model, messages=messages)
    _track(role, model, resp, request_id, item_id)
    return resp.choices[0].message.content or ""
