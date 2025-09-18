# Inferno: High-Traffic Inference Platform

Inferno is a scalable, production-grade inference system designed for high-traffic AI workloads. It provides a robust PaaS for AI model serving, secure API management, and a real-time chat application, all orchestrated with Kubernetes for reliability and scalability.

---

## Table of Contents
- [Overview](#overview)
- [Architecture](#architecture)
- [Components](#components)
- [Data Flow](#data-flow)
- [Deployment](#deployment)
- [Monitoring & Observability](#monitoring--observability)
- [Security](#security)
- [Development](#development)
- [Directory Structure](#directory-structure)
- [Contributing](#contributing)

---

## Overview
Inferno is built to handle high-throughput AI inference requests, supporting both REST and WebSocket APIs. It enables:
- **PaaS for AI Inference:** Serve and manage LLMs and other AI models via secure APIs.
- **Chat Application:** Real-time, authenticated chat with AI, including user and API key management.
- **Scalability:** Kubernetes-native, supports horizontal scaling and robust failover.
- **Observability:** Integrated monitoring, tracing, and logging for production reliability.

---

## Architecture
Inferno follows a microservices architecture, with each service containerized and deployed on Kubernetes or Docker Compose. All external traffic flows through NGINX.

```mermaid
graph TD;
  User["User / Client"] -->|HTTP/WS| NGINX
  NGINX -->|/ (SPA)| Frontend
  NGINX -->|/api/backend/...| Backend
  NGINX -->|/api/consumer/...| Consumer
  Backend -->|SQLAlchemy| Postgres[(PostgreSQL)]
  Consumer -->|HTTP(S)| vLLM["vLLM Inference Service"]
  Consumer -->|Redis| Redis[(Redis)]
  Consumer -->|SQL (asyncpg)| Postgres
  Consumer <--> Kafka[(Kafka)]
  Kafka --- Zookeeper
  Backend -->|Prometheus| Monitoring
  Consumer -->|Prometheus| Monitoring
  Backend -->|Tracing (OTLP)| Jaeger
  Consumer -->|Tracing (OTLP)| Jaeger
```

### Key Flows
- **User Auth & Chat:** User signs up/logs in via frontend, backend issues JWT, chat requests routed to consumer for inference.
- **API PaaS:** External clients use API keys (managed by backend) to access inference endpoints via consumer.
- **Caching:** Redis caches prompt/response pairs for low-latency, high-throughput workloads.
- **Monitoring:** Prometheus scrapes metrics, Jaeger traces requests end-to-end.

### Routing (via NGINX)
- `/` → frontend SPA
- `/api/backend/...` → backend FastAPI (auth, tokens, feedback)
- `/api/consumer/...` → consumer FastAPI (inference REST & WebSocket)
- `/grafana/`, `/prometheus/`, `/jaeger/` → observability UIs

---

## Components
### 1. Frontend (React)
- User interface for chat, API key management, and dashboards.
- Built with Create React App for rapid development and production builds.
- Implements authentication (signup, login) with JWT cookies.
- Features a real-time chat UI, protected routes, and user dashboards.
- Integrates with backend for user management and with consumer for AI inference.
- Modern component structure: Navbar, Login, Signup, Dashboard, API key modal, ProtectedRoute, and more.

### 2. Backend (FastAPI)
- Handles user management, authentication (JWT), and API key issuance.
- Provides REST endpoints for signup, login, token management, and batch feedback.
- Stores user and token data in PostgreSQL.
- Exposes Prometheus metrics for monitoring.

### 3. Consumer (FastAPI)
- Handles all inference requests (REST & WebSocket) and streams results.
- Authenticates API keys, logs requests, and manages caching with Redis.
- **Uses Kafka for robust, token-to-token streaming:**
  - Requests are enqueued to Kafka if not cached.
  - A background worker consumes requests, calls vLLM, and streams tokens/chunks to a Kafka response topic.
  - REST/WebSocket endpoints stream these tokens to the client in real time.
- Communicates with vLLM inference service for model completions.
- Exposes Prometheus metrics and tracing.
  - WebSocket access is protected by a shared secret token (`WEBSOCKET_SECRET_KEY`) sent as `?token=...`.

### 4. Module (Inferno Python Library)
- LangChain-style Python wrapper for programmatic access to the inference API.
- Main class: `ChatInferno` in `module/Inferno.py`.
- Allows developers to interact with the Inferno PaaS using a familiar, chainable interface.
- Supports prompt completion, model selection, token/temperature configuration, and request tracing.
- Example usage:
  ```python
  from Inferno import ChatInferno
  client = ChatInferno(api_key="YOUR_API_KEY", model="your-model")
  result = client.invoke("Hello, world!")
  print(result)
  ```
- Used for custom integrations, automation, and advanced client applications.

### 5. Infrastructure
- **PostgreSQL:** Stores user, API key, and inference log data.
- **Redis:** Caches prompt/response pairs for speed and efficiency.
- **Kafka + Zookeeper:** Asynchronous request/response streaming. Topics default to `inferno-queue` (requests) and `inferno-response-queue` (responses).
- **Kubernetes:** Orchestrates all services for high availability and scaling.
- **Prometheus, Grafana, Jaeger:** Monitoring, visualization, and tracing.

---

## Data Flow
1. **User/Client** authenticates via frontend (JWT cookies) or API key (for PaaS).
2. **Frontend** sends chat/inference requests to **consumer** (WebSocket/REST).
3. **Consumer** checks cache (Redis), authenticates, and logs request (Postgres).
4. If cache miss, **consumer** enqueues request to **Kafka**; a background worker consumes, calls **vLLM**, and streams tokens/chunks to a Kafka response topic.
5. **Consumer** streams tokens to the client as soon as they arrive from Kafka (token-to-token streaming).
6. **Consumer** caches the full response in Redis and logs in Postgres.
7. **Prometheus** scrapes metrics from backend and consumer; **Jaeger** traces requests.

Notes:
- WebSocket chat uses a shared secret token. REST access uses per-user API keys issued by the backend.

---

## Deployment
- All services are containerized with Docker.
- Kubernetes manifests in `k8s/` for each service (backend, consumer, frontend, etc.).
- Secrets and configs managed via Kubernetes secrets/configmaps.
- Supports horizontal scaling and rolling updates.

### Quickstart (Docker Compose)
1) Prerequisites
   - Docker Desktop (with GPU passthrough for NVIDIA if you plan to run `vllm` locally)
   - NVIDIA Container Toolkit installed and working (for GPU)
2) Create `.env` at repository root for vLLM (at minimum):
   ```
   HUGGINGFACE_TOKEN=your_hf_token
   ```
3) Start the stack
   - Build and run: `docker-compose up --build -d`
   - NGINX entrypoint: `http://localhost` (frontend)
   - Observability UIs: `http://localhost/grafana/`, `http://localhost/prometheus/`, `http://localhost/jaeger/`
4) Databases are auto-initialized by `init-multi-db.sh` (creates `users` and `chatlogs`).

### Test the APIs
- Issue a user token via the frontend (Signup → Login → API page → Create API Key), then:
  - REST (non-streaming) completion via consumer:
    ```bash
    curl -s -X POST \
      -H "Authorization: Bearer YOUR_API_KEY" \
      -H "Content-Type: application/json" \
      http://localhost/api/consumer/v1/completions \
      -d '{"prompt":"Hello, world","model":"my-quantized-model","max_tokens":64,"temperature":0.7,"stream":false}'
    ```
- WebSocket chat (used by the dashboard) connects to `/api/consumer/v1/completions?token=WEBSOCKET_SECRET`.

---

## Monitoring & Observability
- **Prometheus:** Metrics endpoint exposed by backend and consumer for real-time monitoring.
- **Grafana:** Dashboards for system health and traffic.
- **Jaeger:** Distributed tracing for debugging and performance analysis.
- **Loki:** Centralized logging (optional).

Default URLs via NGINX:
- Grafana: `/grafana/`
- Prometheus: `/prometheus/`
- Jaeger UI: `/jaeger/`

---

## Security
- JWT-based authentication for users.
- API key management for PaaS clients.
- Secure password hashing and HTTP-only cookies.
- CORS restricted to trusted origins.
- Secrets managed via Kubernetes.

---

## Development
- See each service's README for setup and usage.
- Use Docker Compose for local development, or deploy to Kubernetes for production.
- Example commands:
  - `docker-compose up` (local dev)
  - `docker-compose up --build` (rebuild after changes)
  - `kubectl apply -f k8s/` (Kubernetes deploy)

### Client Library (Python)
Use the bundled `module/Inferno.py` to call the API programmatically:
```python
from Inferno import ChatInferno

client = ChatInferno(
    api_key="YOUR_API_KEY",
    model="my-quantized-model",
    base_url="localhost/api/consumer",  # NGINX route
)

print(client.invoke("Hello, Inferno!"))
```

---

## Directory Structure
```
kafka-grpc-based-setup/
  backend/      # FastAPI backend (auth, API, user management)
  consumer/     # FastAPI consumer (inference, caching, API key auth, Kafka streaming)
  frontend/     # React frontend (UI, chat, dashboard)
  module/       # Inferno Python client library
  k8s/          # Kubernetes manifests for all services
  monitoring/   # Prometheus, Grafana, Loki configs
  nginx/        # Reverse proxy config
  terraform/    # (Optional) Infrastructure as code
  vllm/         # vLLM server Dockerfile and config
  docker-compose.yml
  init-multi-db.sh
```

---

## Contributing
Contributions are welcome! Please open issues or pull requests for improvements, bug fixes, or new features.

---

## License
MIT License 