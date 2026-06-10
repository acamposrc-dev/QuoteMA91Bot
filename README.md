# QuoteBot

Sistema automatico de cotizaciones: recibe una lista de items (por correo o upload),
un agente de IA busca en la web opciones de compra que cumplan las especificaciones,
y devuelve las 4 opciones mas baratas por item priorizando Venezuela > EEUU > China > resto.

## Arquitectura

```
correo (poll 15 min) ─┐
                      ├─> parser (codigo primero, LLM si formato nuevo)
upload (POST /api)  ──┘        |
                               v
                    cola Celery (un job por item)
                               |
                               v
              LOOP AGENTICO por item y por tier:
              buscar -> resolver precios -> matcher LLM
                 ^                              |
                 └── reformular queries <── ¿faltan opciones?
                               |
                               v
              ranking (tier, luego precio USD) -> top 4
                               |
                               v
              Excel + respuesta al correo original
```

- **Parser**: plantilla oficial xlsx/csv parseada con codigo (`app/services/parsing/`).
  Formato desconocido => fallback LLM con salida estructurada validada.
- **Agente** (`app/services/agent/search_agent.py`): cascada ve -> us -> cn -> global,
  con hasta `MAX_REFORMULATIONS_PER_TIER` reformulaciones por tier y presupuesto duro
  de `MAX_SEARCHES_PER_ITEM` busquedas.
- **LLM agnostico**: LiteLLM + Instructor. Cada rol (parser_fallback, matcher,
  extractor_fallback, query_reformulator) apunta a cualquier modelo via `.env`
  (Anthropic, OpenAI, DeepSeek, Gemini, Ollama...). Costos por llamada en `llm_logs`.
- **Precios**: JSON-LD schema.org -> meta tags -> LLM (solo fallback).
  Moneda normalizada a USD (tasa BCV para bolivares, cache Redis 6h).

## Quickstart

```bash
cp .env.example .env          # completar SERPER_API_KEY y al menos una key de LLM
docker compose up -d postgres redis
pip install -e ".[dev]"
alembic revision --autogenerate -m "initial" && alembic upgrade head
uvicorn app.main:app --reload &
celery -A app.workers.celery_app worker -l info -Q items,requests,email &
celery -A app.workers.celery_app beat -l info &        # habilita el poll de correo

# probar con la plantilla de ejemplo
curl -F "file=@samples/plantilla_cotizacion.xlsx" localhost:8000/api/v1/requests/upload
curl localhost:8000/api/v1/requests/<id>               # estado e items
curl -OJ localhost:8000/api/v1/requests/<id>/report    # Excel final
```

## Gmail

Crear credenciales OAuth (scope `gmail.modify`), guardar `secrets/gmail_credentials.json`,
generar el token la primera vez con el flujo de `google-auth-oauthlib`, y configurar
`QUOTE_SUBJECT_KEYWORDS` / `QUOTE_SENDER_WHITELIST` en `.env`.

## Plantilla oficial de cotizacion

Columnas (fila 1): `item | descripcion | cantidad | marca_preferida | specs`
La columna specs admite `clave: valor; clave: valor`. Cualquier otro formato
(PDF, correo en prosa, Excel distinto) cae automaticamente al parser LLM.

## Tests

```bash
pytest tests/
```
