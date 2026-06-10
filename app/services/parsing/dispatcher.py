"""Orquestador de parsing: codigo primero, LLM como fallback para formatos nuevos.

Orden:
  1. Cada DocumentParser registrado que declare can_handle() intenta parsear.
  2. Si todos fallan (UnrecognizedFormat) o ninguno aplica -> parser LLM.
"""

from app.core.logging import get_logger
from app.services.parsing.base import ParseResult, UnrecognizedFormat
from app.services.parsing.llm_fallback import parse_with_llm
from app.services.parsing.template_csv import TemplateCsvParser
from app.services.parsing.template_xlsx import TemplateXlsxParser

log = get_logger(__name__)

PARSERS = [TemplateXlsxParser(), TemplateCsvParser()]


def parse_document(filename: str, content: bytes, request_id: str | None = None) -> ParseResult:
    for parser in PARSERS:
        if not parser.can_handle(filename, content):
            continue
        try:
            result = parser.parse(filename, content)
            log.info("parsed_deterministic", method=parser.method, items=len(result.items))
            return result
        except UnrecognizedFormat as exc:
            log.info("template_mismatch", parser=parser.method, reason=str(exc))

    log.info("falling_back_to_llm", filename=filename)
    return parse_with_llm(filename, content, request_id=request_id)
