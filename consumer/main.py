import logging
import warnings
import json
import uuid
from uuid import UUID
import asyncio
from contextlib import asynccontextmanager
from typing import Any, Dict
import redis.asyncio as redis
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter as RateLimiterDepends
import asyncpg
import httpx
from fastapi import FastAPI, HTTPException, WebSocket, Depends, status
from fastapi.websockets import WebSocketDisconnect
from prometheus_fastapi_instrumentator import Instrumentator
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pybreaker import CircuitBreaker, CircuitBreakerError
from redis_cache import RedisCache
from telemetry import tracer
from schema import ProduceMessage
from auth import verify_api_key
from kafka_queue import KafkaQueue

# --- Configuration ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
warnings.simplefilter('ignore')

POSTGRES_URL = 'postgresql://yash:secret@db:5432/chatlogs'
WEBSOCKET_SECRET_KEY = "yksuthar@h46sg3qe7665"
RESPONSE_TIMEOUT = 30.0 # Timeout in seconds for waiting for a response
VLLM_REQUEST_TIMEOUT = 25.0 # Timeout for the HTTP call to vLLM itself

# --- New: Rate Limiter and Circuit Breaker Configuration ---
# Rate limiter instance (general, IP-based)
rate_limit = RateLimiterDepends(times=10000, seconds=1)

# Circuit breaker instance for vLLM calls
# Trips after 5 consecutive failures, resets after 30 seconds.
vllm_breaker = CircuitBreaker(fail_max=5, reset_timeout=30)
logger.info("✅ vLLM Circuit Breaker initialized.")


# --- Global State and Clients ---
cache = RedisCache()
kafka_queue = KafkaQueue()

# This dictionary holds asyncio.Queue objects for each request waiting for a response.
# Key: request_id (str), Value: asyncio.Queue
response_waiters: Dict[str, asyncio.Queue] = {}


async def kafka_worker():
    """Background task: consumes requests from Kafka, calls vLLM, and produces responses."""
    worker_queue = KafkaQueue()
    await worker_queue.start_consumer()
    await worker_queue.start_producer()
    logger.info("[Worker] Kafka worker started and listening for requests.")

    async for message in worker_queue.consume():
        logger.info(f"[Worker] Received message from Kafka: {message}")
        request_id = message.get("request_id")
        if not request_id:
            logger.error("[Worker] Received message without request_id, skipping.")
            continue

        try:
            payload = {
                "model": message.get("model"),
                "prompt": message.get("prompt"),
                "max_tokens": message.get("max_tokens"),
                "temperature": message.get("temperature"),
                "stream": True # Always stream from vLLM
            }
            
            async with httpx.AsyncClient(timeout=VLLM_REQUEST_TIMEOUT) as client:
                try:
                    # New: Define an async function to wrap the protected call.
                    # This is the correct way to use pybreaker.call() with async code.
                    async def call_vllm_api():
                        async with client.stream("POST", "http://vllm:8000/v1/completions", json=payload) as response:
                            response.raise_for_status()
                            full_response_chunks = []
                            async for line in response.aiter_lines():
                                if line.startswith("data: "):
                                    if line.strip() == "data: [DONE]":
                                        break
                                    try:
                                        data = json.loads(line[6:])
                                        response_payload = {
                                            "request_id": request_id,
                                            "data": data,
                                            "done": False
                                        }
                                        await worker_queue.push_to_queue(response_payload, topic=worker_queue.response_topic)
                                        full_response_chunks.append(data.get("choices", [{}])[0].get("text", ""))
                                    except json.JSONDecodeError:
                                        logger.warning(f"[Worker] Skipping malformed JSON line from vLLM: {line}")
                                        continue
                            
                            # Signal completion
                            await worker_queue.push_to_queue({"request_id": request_id, "done": True}, topic=worker_queue.response_topic)
                            logger.info(f"[Worker] Finished processing and sent DONE for request {request_id}")
                    
                    # New: Call the protected function using pybreaker's .call() method
                    await vllm_breaker.call(call_vllm_api)

                except CircuitBreakerError:
                    # The circuit is open, so we don't even try to call vLLM.
                    logger.error(f"[Worker] Circuit is OPEN. VLLM service is unavailable. Fast-failing for request {request_id}")
                    await worker_queue.push_to_queue({
                        "request_id": request_id,
                        "error": "vLLM service is unavailable.",
                        "done": True
                    }, topic=worker_queue.response_topic)
                
                except Exception as e:
                    # This catches any other errors from the VLLM call that pybreaker is monitoring
                    logger.error(f"[Worker] Error processing request {request_id}: {e}", exc_info=True)
                    await worker_queue.push_to_queue({
                        "request_id": request_id,
                        "error": str(e),
                        "done": True
                    }, topic=worker_queue.response_topic)

        except Exception as e:
            # This is the outer try-except block from your original code
            logger.error(f"[Worker] Critical error in worker loop processing message for {request_id}: {e}", exc_info=True)
            # You might want to handle this differently, possibly shutting down the worker.



async def response_dispatcher():
    """
    Background task: consumes from the response topic and dispatches
    messages to the correct waiting request handler via an asyncio.Queue.
    """
    dispatcher_queue = KafkaQueue()
    # Use a unique group_id for the dispatcher so it gets all messages
    dispatcher_queue.group_id = f"dispatcher-group-{uuid.uuid4()}"
    await dispatcher_queue.start_consumer(topic=dispatcher_queue.response_topic)
    logger.info("[Dispatcher] Response dispatcher started.")

    async for message in dispatcher_queue.consume():
        request_id = message.get("request_id")
        if request_id in response_waiters:
            await response_waiters[request_id].put(message)
        else:
            logger.warning(f"[Dispatcher] Received message for unknown or timed-out request_id: {request_id}")


# --- FastAPI Lifespan ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("[LIFESPAN] FastAPI app starting up...")

    # Connect to PostgreSQL and create tables using asyncpg
    try:
        conn = await asyncpg.connect(POSTGRES_URL)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id SERIAL PRIMARY KEY, token UUID UNIQUE NOT NULL, created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        logger.info("✅ PostgreSQL 'api_keys' table checked/created successfully.")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS inference_logs (
                id SERIAL PRIMARY KEY, request_id UUID, prompt TEXT, response TEXT, model TEXT,
                temperature REAL, max_tokens INT, created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        logger.info("✅ PostgreSQL 'inference_logs' table checked/created successfully.")
        await conn.close()
    except Exception as e:
        logger.error(f"❌ Failed to connect to PostgreSQL or create tables: {e}", exc_info=True)
        raise RuntimeError(f"Database initialization failed: {e}")

    # New: Initialize the rate limiter with Redis
    try:
        redis_conn = redis.from_url("redis://redis:6379", encoding="utf-8", decode_responses=True)
        await FastAPILimiter.init(redis_conn)
        logger.info("✅ Redis for rate limiting initialized.")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Redis for rate limiting: {e}", exc_info=True)
        raise RuntimeError(f"Rate limiter initialization failed: {e}")

    # Start background tasks
    worker_task = asyncio.create_task(kafka_worker())
    dispatcher_task = asyncio.create_task(response_dispatcher())

    yield

    # Clean shutdown
    logger.info("[LIFESPAN] Shutting down...")
    worker_task.cancel()
    dispatcher_task.cancel()
    await asyncio.gather(worker_task, dispatcher_task, return_exceptions=True)
    # New: Close the rate limiter connection on shutdown
    await FastAPILimiter.close()
    logger.info("[LIFESPAN] Rate limiter shut down.")
    logger.info("[LIFESPAN] Background tasks cancelled.")


# --- FastAPI App and Middleware ---

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Be more specific in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

instrumentator = Instrumentator()
instrumentator.instrument(app).expose(app)


# --- Database Logic ---

async def save_to_postgres(prompt: str, response: str, request_id: str, model: str, temperature: float, max_tokens: int):
    """Asynchronously saves logs to PostgreSQL using asyncpg."""
    with tracer.start_as_current_span("save_inference") as span:
        span.set_attribute("request.request_id", request_id)
        try:
            conn = await asyncpg.connect(POSTGRES_URL)
            await conn.execute(
                """INSERT INTO inference_logs (request_id, prompt, response, model, temperature, max_tokens)
                   VALUES ($1, $2, $3, $4, $5, $6)""",
                UUID(request_id), prompt, response, model, temperature, max_tokens
            )
            await conn.close()
            logger.info(f"[DB] Logged inference for request_id: {request_id}")
        except Exception as e:
            span.record_exception(e)
            logger.error(f"[DB] Error logging inference for request_id {request_id}: {e}")


# --- Streaming Logic for Endpoints ---

async def stream_from_kafka(request_id: str, model: str):
    """
    Handles the logic of waiting for and streaming responses for a given request_id.
    This is an async generator used by both HTTP and WebSocket endpoints.
    """
    response_queue = asyncio.Queue()
    response_waiters[request_id] = response_queue

    try:
        while True:
            try:
                # Wait for a message with a timeout
                message = await asyncio.wait_for(response_queue.get(), timeout=RESPONSE_TIMEOUT)

                if message.get("error"):
                    logger.error(f"[Streamer] Received error for {request_id}: {message['error']}")
                    break

                if message.get("done"):
                    break # Graceful end of stream

                # Reconstruct the OpenAI-compatible chunk
                vllm_data = message.get("data", {})
                chunk = {
                    "id": request_id,
                    "object": "text_completion",
                    "choices": vllm_data.get("choices", []),
                    "model": model
                }
                yield chunk

            except asyncio.TimeoutError:
                logger.error(f"[Streamer] Timeout waiting for response for request_id: {request_id}")
                break
    finally:
        # Crucial cleanup step to prevent memory leaks
        if request_id in response_waiters:
            del response_waiters[request_id]
        logger.info(f"[Streamer] Cleaned up waiter for request_id: {request_id}")


# --- API Endpoints ---

@app.post('/v1/completions', tags=['vLLM Compatible'])
async def vllm_completions(
    request: ProduceMessage,
    authenticated: Any = Depends(verify_api_key),
    # New: Apply the rate limit to this endpoint
    rate_limiter: Any = Depends(rate_limit),
):
    request_id = str(request.request_id or uuid.uuid4())
    logger.info(f"[API] Received /v1/completions request: {request_id}")

    with tracer.start_as_current_span("/v1/completions") as span:
        span.set_attribute("request.request_id", request_id)
        span.set_attribute("request.model", request.model)

        # 1. Check Redis cache
        with tracer.start_as_current_span("cache_check"):
            cached = cache.get_cached_response(request.prompt, request.model, request.max_tokens, request.temperature)

        if cached:
            span.set_attribute("cache.hit", True)
            logger.info(f"[API] Cache hit for request_id: {request_id}")
            def cached_stream():
                chunk = {
                    "id": request_id, "object": "text_completion",
                    "choices": [{"text": cached["response"], "index": 0, "finish_reason": "stop"}],
                    "model": request.model
                }
                yield f"data: {json.dumps(chunk)}\n\n"
                yield "data: [DONE]\n\n"
            return StreamingResponse(cached_stream(), media_type="text/event-stream")

        # 2. If cache miss, push to Kafka
        span.set_attribute("cache.hit", False)
        logger.info(f"[API] Cache miss for request_id: {request_id}. Enqueuing to Kafka.")
        kafka_message = request.dict()
        kafka_message["request_id"] = request_id
        await kafka_queue.push_to_queue(kafka_message)

        # 3. Handle response based on the 'stream' flag
        try:
            # --- IF STREAM IS TRUE ---
            if request.stream:
                async def http_streamer():
                    full_response = ""
                    # This loop will terminate when stream_from_kafka stops yielding (due to DONE or timeout)
                    async for chunk in stream_from_kafka(request_id, request.model):
                        choices = chunk.get("choices", [])
                        if choices and "text" in choices[0]:
                            full_response += choices[0]["text"]
                        yield f"data: {json.dumps(chunk)}\n\n"

                    # If no response was accumulated, it implies a timeout or error from backend
                    if not full_response:
                        logger.warning(f"Streaming request {request_id} timed out or failed. Sending error chunk.")
                        error_chunk = {
                            "id": request_id,
                            "object": "error",
                            "message": "Server is busy, please try again."
                        }
                        yield f"data: {json.dumps(error_chunk)}\n\n"

                    yield "data: [DONE]\n\n"

                    # Save to DB after the stream is complete
                    if full_response:
                        with tracer.start_as_current_span("db_save"):
                            await save_to_postgres(request.prompt, full_response, request_id, request.model, request.temperature, request.max_tokens)

                return StreamingResponse(http_streamer(), media_type="text/event-stream")

            # --- IF STREAM IS FALSE ---
            else:
                full_response = ""
                chunks_received = 0

                async for chunk in stream_from_kafka(request_id, request.model):
                    chunks_received += 1
                    choices = chunk.get("choices", [])
                    if choices and "text" in choices[0]:
                        full_response += choices[0]["text"]
                
                # If no chunks were received, it means a timeout or error occurred in the backend
                if chunks_received == 0:
                    raise HTTPException(
                        status_code=503,
                        detail="Server is busy, please try again."
                    )

                logger.info(f"[API] Assembled full response for non-streaming request {request_id}")

                if full_response:
                    with tracer.start_as_current_span("cache_save"):
                        cache.cache_response(request.prompt, request.model, request.max_tokens, request.temperature, full_response, request_id)
                
                response_payload = {
                    "id": request_id,
                    "object": "text_completion",
                    "model": request.model,
                    "choices": [{"text": full_response, "index": 0, "finish_reason": "stop"}]
                }
                return response_payload
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[API] Error during response processing for {request_id}: {e}", exc_info=True)
            raise HTTPException(
                status_code=500,
                detail="An internal server error occurred."
            )


@app.websocket("/v1/completions")
async def websocket_completions(
    websocket: WebSocket,
):
    if WEBSOCKET_SECRET_KEY and websocket.query_params.get("token") != WEBSOCKET_SECRET_KEY:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid auth token")
        return
    await websocket.accept()

    try:
        while True:
            try:
                # New: Timeout for receiving the *next* prompt from the client
                data = await asyncio.wait_for(websocket.receive_text(), timeout=RESPONSE_TIMEOUT)
                body = json.loads(data)
                message = ProduceMessage(**body)
                request_id = str(message.request_id or uuid.uuid4())

                with tracer.start_as_current_span("/ws/completions") as span:
                    span.set_attribute("request.request_id", request_id)
                    span.set_attribute("request.model", message.model)

                    # 1. Check Redis cache
                    with tracer.start_as_current_span("cache_check"):
                        cached = cache.get_cached_response(message.prompt, message.model, message.max_tokens, message.temperature)

                    if cached:
                        span.set_attribute("cache.hit", True)
                        logger.info(f"[WS] Cache hit for request_id: {request_id}")
                        chunk = {
                            "id": request_id, "object": "text_completion",
                            "choices": [{"text": cached["response"], "index": 0, "finish_reason": "stop"}],
                            "model": message.model
                        }
                        await websocket.send_text(json.dumps(chunk))
                        await websocket.send_text("[DONE]")
                        continue

                    # 2. If cache miss, push to Kafka
                    span.set_attribute("cache.hit", False)
                    logger.info(f"[WS] Cache miss for request_id: {request_id}. Enqueuing to Kafka.")
                    kafka_message = message.dict()
                    kafka_message["request_id"] = request_id
                    await kafka_queue.push_to_queue(kafka_message)

                    # 3. Stream from Kafka
                    full_response = ""
                    async for chunk in stream_from_kafka(request_id, message.model):
                        choices = chunk.get("choices", [])
                        if choices and "text" in choices[0]:
                            full_response += choices[0]["text"]
                        await websocket.send_text(json.dumps(chunk))

                    # If no response was accumulated, it implies a timeout or error from backend
                    if not full_response:
                        logger.warning(f"WebSocket request {request_id} timed out or failed. Sending error frame.")
                        error_frame = {
                            "id": request_id,
                            "object": "error",
                            "message": "Server is busy, please try again."
                        }
                        await websocket.send_text(json.dumps(error_frame))

                    await websocket.send_text("[DONE]")

                    # 4. Save to cache and DB after the stream
                    if full_response:
                        with tracer.start_as_current_span("cache_save"):
                            cache.cache_response(message.prompt, message.model, message.max_tokens, message.temperature, full_response, request_id)

            except asyncio.TimeoutError:
                logger.warning("WebSocket client inactive or backend response timeout. Closing connection.")
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Client inactive or backend busy")
                break
            except WebSocketDisconnect:
                logger.info("WebSocket disconnected gracefully.")
                break
    except Exception as e:
        logger.error(f"[WebSocket] Error: {e}", exc_info=True)
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason=str(e))
        except RuntimeError:
            pass # Connection might already be closed


@app.get('/health', tags=['Health'])
async def health():
    ok = await KafkaQueue.health_check()
    if ok:
        return {"status": "ok"}
    else:
        return {"status": "error", "detail": "Kafka not reachable"}