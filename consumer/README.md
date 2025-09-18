# Consumer Service

This service acts as a bridge between the frontend, Redis, Kafka, and the vLLM inference backend. It provides both REST and WebSocket APIs for real-time and batch AI completions, with authentication, caching, and monitoring.

## Architecture Overview
- **Framework:** FastAPI
- **Database:** PostgreSQL (for API keys and inference logs)
- **Cache:** Redis (for prompt/response caching)
- **Queue:** Kafka (for streaming message queue, with request and response topics)
- **AI Backend:** vLLM (via HTTP)
- **Authentication:** API key-based
- **Monitoring:** Prometheus metrics, OpenTelemetry tracing

## Key Components
- `main.py`: FastAPI app, WebSocket and REST endpoints, DB setup, and core logic
- `auth.py`: API key verification and token management
- `redis_cache.py`: Redis caching utility
- `kafka_queue.py`: Kafka queue utility (async, used for streaming, supports request and response topics)
- `telemetry.py`: OpenTelemetry tracing setup
- `schema.py`: Pydantic models for request validation

## Streaming Flow (Token-to-Token)
- **Cache Hit:**
  - If the prompt is cached in Redis, the response is streamed directly from cache to the client (REST or WebSocket).
- **Cache Miss:**
  1. The request is enqueued to a Kafka request topic.
  2. A background worker consumes the request, calls vLLM with `stream=True`, and as each token/chunk is received, it is immediately produced to a Kafka response topic.
  3. The REST/WebSocket endpoint streams these tokens/chunks to the client in real time, as soon as they arrive from Kafka.
  4. When the stream is complete, the full response is cached in Redis and logged in PostgreSQL.

**Result:** Clients experience true token-to-token streaming, with minimal latency, just as before.

## Main Endpoints
- `POST /v1/completions`: vLLM-compatible completion endpoint (REST, streaming)
- `WebSocket /v1/completions`: Real-time streaming completions
- `GET /health`: Health check

## Database
- Stores API keys and inference logs in PostgreSQL
- Tables are auto-created on startup if missing

## Caching & Queueing
- Uses Redis to cache prompt/response pairs for efficiency
- Uses Kafka for robust, scalable streaming queue in REST and WebSocket APIs
- Background worker consumes requests from Kafka, calls vLLM, and streams responses to Kafka response topic

## Security
- API key required for all completion endpoints
- API keys are stored and validated against the database

## Monitoring & Tracing
- Prometheus metrics via FastAPI Instrumentator
- Distributed tracing with OpenTelemetry

## Usage
- Start with `uvicorn main:app --reload`
- Configure DB, Redis, Kafka, and vLLM URLs as needed in `main.py` and environment variables

---
For more details, see the code and comments in each file. 