# InferScale — Implementation Plan

> This plan builds the vision in [`plan.md`](plan.md) one piece at a time.
> **First the structure → then a simple working model → then features one at a time.**

---

## 1. How to Use This Plan

### Ground rules

1. **Every phase ends in a working, tested and tagged state.** Nothing is left half-built between phases.
2. **Don't start a phase until the previous phase's "Done when" checklist passes.**
3. **One feature branch per step**, e.g. `feat/p1-mock-worker`, merged into `develop`.
   At each milestone tag, merge `develop` into `main`.
4. **Tests ship in the same step as the feature**, not afterwards.
5. **Every tunable lives in config.** No magic numbers in code.
6. **Extend through interfaces instead of rewriting.** Routing strategies, queue backends and worker backends each sit behind an interface, so a new feature is a new class.

### Key architectural decisions

| Decision | Choice | Why |
|---|---|---|
| Language / tooling | Python 3.12, `uv`, `ruff`, `mypy`, `pytest` | Fast, modern, reproducible |
| Process layout | **One control-plane process** (gateway + queue + scheduler + router) and **separate worker processes** | Avoids a microservice split too early. The module boundaries still allow splitting later |
| Worker API | Mock workers speak the **same OpenAI-compatible API** as vLLM, Ollama and llama.cpp | Moving to real models only means changing a URL (plan.md §20) |
| Extensibility | `RoutingStrategy`, `QueueBackend` and `WorkerBackend` interfaces | Features are added, not rewritten |
| Local-first | Docker Compose → kind/k3d → optional GPU | ₹0 goal (plan.md §28) |

### Progress tracker

| Phase | Name | Tag | Status |
|---|---|---|---|
| 0 | Project skeleton | `v0.0` | ☐ |
| 1 | Simple working model (walking skeleton) | `v0.1` | ☐ |
| 2 | Multiple workers and basic routing | `v0.2` | ☐ |
| 3 | Queue, scheduling and gateway hardening | `v0.3` | ☐ |
| 4 | Observability and load testing → **Initial Milestone** | `v1.0` | ☐ |
| 5 | Kubernetes | `v1.1` | ☐ |
| 6 | Real model workers | `v1.2` | ☐ |
| 7 | Intelligent routing | `v1.3` | ☐ |
| 8 | Autoscaling | `v1.4` | ☐ |
| 9 | Fault tolerance and chaos | `v1.5` | ☐ |
| 10 | Benchmarking and write-up | `v2.0` | ☐ |

---

## 2. Target Repository Structure

This layout is created in **Phase 0**. Later phases fill in the folders.

```text
inferscale/
├── pyproject.toml              # uv project, ruff, mypy, pytest config
├── Makefile                    # dev, test, lint, up, down, load targets
├── README.md
├── plan.md                     # vision document
├── IMPLEMENTATION_PLAN.md      # this file
├── config/
│   ├── inferscale.yaml         # gateway / router / queue settings
│   └── models.yaml             # model registry + fallback chains
├── src/inferscale/
│   ├── common/                 # config loader, OpenAI schemas, logging, request IDs
│   ├── gateway/                # FastAPI app, routes, middleware (auth, rate limit, request ID)
│   ├── queue/                  # QueueBackend interface: memory.py, redis.py
│   ├── scheduler/              # dispatch loop: concurrency, timeouts, retries
│   ├── router/                 # registry.py, health.py, strategies/, classifier.py
│   ├── worker/                 # worker service: mock backend, OpenAI-proxy backend
│   ├── observability/          # Prometheus metrics, OpenTelemetry tracing
│   └── autoscaler/             # policy engine + Kubernetes scaler (Phase 8)
├── tests/
│   ├── unit/
│   ├── integration/            # gateway + mock workers in-process (ASGI transport)
│   └── e2e/                    # against docker compose / k8s
├── deploy/
│   ├── docker/                 # Dockerfile.gateway, Dockerfile.worker
│   ├── compose/                # docker-compose.yml (+ observability overlay)
│   ├── prometheus/             # prometheus.yml, alert rules
│   ├── grafana/                # provisioning + dashboard JSON
│   └── k8s/                    # manifests / kustomize (Phase 5)
├── loadtest/                   # Locust files, k6 scripts
├── benchmarks/                 # experiment scripts + results/*.md
└── .github/workflows/ci.yml    # lint + test
```

### Module responsibilities

| Module | Responsibility | plan.md |
|---|---|---|
| `common` | Shared config, schemas, logging, IDs | — |
| `gateway` | Auth, rate limiting, validation, request IDs, normalisation | §3 Step 2 |
| `queue` | Buffering, priority, limits, expiry | §4 |
| `scheduler` | Pulls from the queue, dispatches when capacity exists, retries | §4, §23 Phase 3 |
| `router` | Model + worker selection, health, strategies, fallback | §5, §6, §12, §13 |
| `worker` | Runs inference (mock or real engine) | §7, §9, §19, §20 |
| `observability` | Metrics, traces, structured logs | §14, §15 |
| `autoscaler` | Scaling policy + Kubernetes API calls | §16 |

---

## 3. Phases

---

### Phase 0 — Project Skeleton (structure only)

**Goal:** an empty but correct project: tooling, layout, CI and stub services. No business logic.

**Architecture snapshot**
```text
gateway (stub)  ── GET /health → 200
worker  (stub)  ── GET /health → 200
```

**Steps**
1. `uv init`, then write `pyproject.toml`:
   - runtime: `fastapi`, `uvicorn[standard]`, `httpx`, `pydantic`, `pydantic-settings`, `pyyaml`, `structlog`
   - dev: `pytest`, `pytest-asyncio`, `ruff`, `mypy`
2. Create every package folder under `src/inferscale/` with an `__init__.py`.
3. `common/config.py` — typed settings (pydantic-settings) loaded from `config/inferscale.yaml` + environment overrides.
4. `common/logging.py` — structured JSON logging (structlog).
5. `common/schemas.py` — OpenAI-compatible `ChatCompletionRequest`, `ChatCompletionResponse`, `ChatCompletionChunk`, `Message`, `Usage`, plus InferScale metadata (`request_id`, `priority`).
6. `gateway/app.py` and `worker/app.py` — FastAPI app factories exposing only `GET /health`.
7. `Makefile` targets: `install`, `lint`, `format`, `typecheck`, `test`, `run-gateway`, `run-worker`.
8. `.github/workflows/ci.yml` — ruff + mypy + pytest.
9. `README.md` quickstart.

**Key files:** `pyproject.toml`, `Makefile`, `src/inferscale/common/*`, `src/inferscale/gateway/app.py`, `src/inferscale/worker/app.py`, `tests/unit/test_health.py`

**Done when**
- [ ] `make lint typecheck test` passes locally
- [ ] Both stubs start, and `curl localhost:8000/health` / `:9001/health` return `200`
- [ ] CI is green on GitHub

**Tag:** `v0.0`

---

### Phase 1 — Simple Working Model (walking skeleton)

**Goal:** the smallest end-to-end system that works: a real OpenAI-compatible request goes through the gateway to one mock worker and back, streaming included.

**Architecture snapshot**
```text
Client ──► Gateway ──► Mock Worker
   ◄──────── response / SSE stream
```

**Steps**
1. **Mock worker, non-streaming:** `POST /v1/chat/completions` waits `simulated_latency`, then returns a fake completion with realistic `usage` token counts.
   Configurable settings: `latency_ms`, `tokens_per_sec`, `failure_rate`, `model_name`.
2. **Mock worker, streaming:** when `stream: true`, emit SSE `data:` chunks token by token at `tokens_per_sec`, then `data: [DONE]`. This makes TTFT measurable later.
3. **Gateway forwarding:** `POST /v1/chat/completions` validates the request with the shared schemas and forwards it to **one** configured worker through a single shared `httpx.AsyncClient`. It supports non-streaming and streaming passthrough.
4. **Request-ID middleware:** read or create `X-Request-ID`, bind it to the log context, forward it to the worker and return it in the response headers.
5. **`GET /v1/models`** on the gateway, from static config.
6. **Error mapping:** worker errors and timeouts become OpenAI-style error JSON (`502`/`504`).
7. **Tests:**
   - unit: schemas, mock token generator
   - integration: gateway + mock worker in-process through `httpx.ASGITransport` (no network)
8. **Containers:** `deploy/docker/Dockerfile.gateway`, `Dockerfile.worker`, `deploy/compose/docker-compose.yml` (gateway + 1 worker).

**Key files:** `worker/mock.py`, `worker/app.py`, `gateway/routes/chat.py`, `gateway/middleware/request_id.py`, `gateway/client.py`, `tests/integration/test_chat_e2e.py`

**Done when**
- [ ] `curl` gets a completion through the gateway
- [ ] The official `openai` Python SDK, with `base_url` set to the gateway, works for normal and streaming calls
- [ ] The same request ID appears in gateway logs, worker logs and response headers
- [ ] `docker compose up` brings up the whole stack

**Tag:** `v0.1` 🎉 *First working model*

---

### Phase 2 — Multiple Workers and Basic Routing

**Goal:** spread traffic across several workers and route around unhealthy ones.

**Architecture snapshot**
```text
Client ──► Gateway ──► Router ──┬── Worker 1
                                ├── Worker 2
                                └── Worker 3
```

**Steps**
1. **Worker registry** (`router/registry.py`): an in-memory record per worker (`id`, `url`, `model`, `status`, `active_requests`, `max_concurrency`), seeded from config.
2. **Health checker** (`router/health.py`): a background asyncio task that polls `/health` every N seconds. A worker is marked `UNHEALTHY` after `fail_threshold` failures and `HEALTHY` again after `recover_threshold` successes.
3. **`RoutingStrategy` interface:** `select(request, candidates) -> Worker`.
   - `RoundRobinStrategy`
   - `LeastConnectionsStrategy`
   - The strategy is chosen in `inferscale.yaml` (`router.strategy`).
4. **Active-request tracking:** the gateway increments and decrements `active_requests` around each call (in a `try/finally`, streaming included).
5. **Worker stats:** the mock worker exposes `GET /stats` (active requests and simulated GPU utilisation, which grows with load).
6. **No healthy worker** → `503` with a clear error.
7. **Compose:** 3 mock workers, each with different latency settings.

**Key files:** `router/registry.py`, `router/health.py`, `router/strategies/base.py`, `router/strategies/round_robin.py`, `router/strategies/least_connections.py`

**Done when**
- [ ] Unit tests show that round-robin cycles evenly and least-connections picks the least-loaded worker
- [ ] `docker stop worker-2` → it is removed from rotation within the health interval, and traffic carries on
- [ ] Restarting it → it rejoins automatically

**Tag:** `v0.2`

---

### Phase 3 — Queue, Scheduling and Gateway Hardening

**Goal:** absorb bursts, respect capacity, prioritise, apply backpressure and protect the gateway.

**Architecture snapshot**
```text
Client ──► Gateway (auth, rate limit) ──► Queue ──► Scheduler ──► Router ──► Workers
```

**Steps**
1. **`QueueBackend` interface** + `MemoryQueue` (asyncio). The gateway enqueues a job and awaits a future. A **scheduler loop** dispatches jobs only while a worker has spare capacity (`active < max_concurrency`).
2. **Priority queue:** `HIGH` / `NORMAL` / `LOW`, set through the `X-Priority` header or the `priority` body field. FIFO within a priority level.
3. **Queue limits and backpressure:** a queue at `max_size` gets `429 Too Many Requests` with `Retry-After`.
4. **Deadlines:** each request carries `deadline = now + timeout`. Expired jobs are dropped before dispatch (`504`).
5. **Retries:** on retryable errors (connection error, 502/503, timeout), retry with exponential backoff on a **different** worker, up to `max_retries`.
6. **`RedisQueue`** backend (Redis added to compose), so several gateway replicas can share one queue.
7. **API-key auth:** `Authorization: Bearer <key>`, with keys from config or env (a Secret later). Missing or invalid key → `401`.
8. **Rate limiting:** a per-key token bucket, in memory at first and then in Redis. Over the limit → `429`.

**Key files:** `queue/base.py`, `queue/memory.py`, `queue/redis.py`, `scheduler/dispatcher.py`, `scheduler/retry.py`, `gateway/middleware/auth.py`, `gateway/middleware/rate_limit.py`

**Done when**
- [ ] A burst above capacity is queued and completes instead of failing
- [ ] A full queue returns `429` with `Retry-After`
- [ ] Test: with the queue saturated, `HIGH` requests are served before `LOW`
- [ ] Killing a worker mid-load → its requests are retried on other workers
- [ ] Requests without a valid key → `401`, and requests over the rate limit → `429`
- [ ] Switching `queue.backend: redis` works with 2 gateway replicas

**Tag:** `v0.3`

---

### Phase 4 — Observability and Load Testing (**Initial Milestone**)

**Goal:** measure everything (plan.md §14, §15). This phase completes the plan.md §32 Initial Milestone.

**Architecture snapshot**
```text
Gateway / Workers ──► /metrics ──► Prometheus ──► Grafana
        └──────────── OTel traces ──► Jaeger / Tempo
Locust ──► Gateway
```

**Steps**
1. **Prometheus metrics** (`observability/metrics.py`), exposed on `/metrics`:
   - `inferscale_requests_total{model,worker,status}`
   - `inferscale_request_latency_seconds` (histogram → p50/p95/p99)
   - `inferscale_queue_wait_seconds`, `inferscale_routing_latency_seconds`
   - `inferscale_ttft_seconds`, `inferscale_tokens_total{direction=in|out}`, `inferscale_tokens_per_second`
   - `inferscale_queue_length{priority}`, `inferscale_active_requests{worker}`, `inferscale_healthy_workers`
2. **Worker metrics:** simulated `gpu_utilization` and `gpu_memory_used`, plus real CPU/memory.
3. **Compose observability overlay:** Prometheus + Grafana with provisioned datasource and dashboard JSON:
   - latency percentiles, TTFT, throughput, error rate, queue length/wait, per-worker load, tokens/sec
4. **OpenTelemetry tracing:** spans for gateway → queue → scheduler → router → worker, exported to Jaeger (or Tempo). The request ID is attached as a span attribute.
5. **Load testing:** `loadtest/locustfile.py` with *steady*, *ramp* and *spike* profiles, plus an optional `loadtest/k6/script.js`.
6. **Baseline benchmark:** run each profile and record the results in `benchmarks/results/00-baseline.md`.

**Key files:** `observability/metrics.py`, `observability/tracing.py`, `deploy/prometheus/prometheus.yml`, `deploy/grafana/dashboards/inferscale.json`, `loadtest/locustfile.py`

**Done when**
- [ ] A Locust run is visible live in Grafana
- [ ] One request can be followed end to end in Jaeger by its request ID
- [ ] The baseline numbers (p50/p95/p99, TTFT, throughput, error rate) are recorded

**Tag:** `v1.0` 🏁 *Initial Milestone (plan.md §32)*

---

### Phase 5 — Kubernetes (kind / k3d)

**Goal:** run the platform on a local cluster with self-healing and replica management (plan.md §17).

**Architecture snapshot**
```text
kind cluster
 ├── Deployment: gateway   (Service: ClusterIP / NodePort)
 ├── Deployment: worker    (headless Service → endpoint discovery)
 ├── StatefulSet/Deployment: redis
 └── Prometheus + Grafana
```

**Steps**
1. **Manifests** (`deploy/k8s/`, kustomize base + overlays):
   - Deployments + Services for the gateway, workers and Redis
   - ConfigMap (`inferscale.yaml`, `models.yaml`), Secret (API keys)
   - Resource requests/limits
   - Readiness and liveness probes wired to `/health`
2. **Dynamic worker discovery:** the router reads endpoints of the worker headless Service through the Kubernetes API (or DNS). It replaces the static list, behind a `DiscoveryProvider` interface (`static` / `kubernetes`).
3. **Observability on k8s:** kube-prometheus-stack (Helm) or plain manifests, with ServiceMonitors for the gateway and workers.
4. **`make k8s-up` / `make k8s-down`:** create the cluster, build and load the images, and apply the manifests.

**Key files:** `deploy/k8s/base/*.yaml`, `router/discovery/kubernetes.py`, `Makefile`

**Done when**
- [ ] `kubectl delete pod <worker>` → Kubernetes replaces it, and clients see no failures beyond retried ones
- [ ] `kubectl scale deploy/worker --replicas=5` → the router starts using the new pods automatically
- [ ] Grafana on k8s shows the same dashboards

**Tag:** `v1.1`

---

### Phase 6 — Real Model Workers

**Goal:** replace mock inference with real engines while the control plane stays unchanged (plan.md §20).

**Architecture snapshot**
```text
Router ──┬── Worker (MockBackend)
         ├── Worker (OpenAIProxyBackend) ──► Ollama / llama.cpp (CPU)
         └── Worker (OpenAIProxyBackend) ──► vLLM (GPU, optional)
```

**Steps**
1. **`WorkerBackend` interface** in the worker: `generate()` / `stream()`.
   - `MockBackend` (the existing logic, moved here)
   - `OpenAIProxyBackend`, which forwards to any OpenAI-compatible engine (vLLM, Ollama, llama.cpp server)
2. **Local models:** a small quantised general model (e.g. Qwen2.5-0.5B/1.5B) and a small coder model on CPU through Ollama or llama.cpp. Use vLLM if a GPU is available.
3. **Real telemetry:** read real `usage` token counts from responses. Take GPU metrics from `nvidia-smi` / DCGM exporter when present, and fall back gracefully otherwise.
4. **Mixed pool:** mock and real workers registered side by side, labelled by model.

**Key files:** `worker/backends/base.py`, `worker/backends/mock.py`, `worker/backends/openai_proxy.py`, `deploy/compose/docker-compose.models.yml`

**Done when**
- [ ] Client code from Phase 1 works against real models **unchanged**
- [ ] The TTFT and tokens/sec dashboards show real numbers
- [ ] The mixed mock + real pool routes correctly by model

**Tag:** `v1.2`

---

### Phase 7 — Intelligent Routing

**Goal:** choose the right model and the best worker automatically (plan.md §5, §6, §12, §13).

**Architecture snapshot**
```text
Request ──► Task classifier ──► Model selection ──► Worker selection ──► Worker
                                     │ failure
                                     ▼
                               Fallback chain
```

**Steps**
1. **Model registry** (`config/models.yaml`): per model `capabilities` (general / coding / reasoning), `cost_per_1k_tokens`, `context_length`, `quality`, `fallback` chain. Move it to **PostgreSQL** later, together with a `request_log` table (latency, tokens, cost, model, worker).
2. **`model: "auto"`** support with a `TaskClassifier` interface:
   - v1: keyword/heuristic rules (code fences, "function", "bug" → coding, etc.)
   - v2 (optional): a small-model classifier
3. **New strategies**, one class each:
   - `CapabilityAware` — filters to models that can handle the task
   - `LatencyAware` — prefers workers with the lowest EWMA of recent latency
   - `CostAware` — cheapest model that meets the quality bar
   - `TokenAware` — prompt length vs context length and worker capacity
   - `PriorityAware` — reserves capacity or better workers for `HIGH`
4. **Composite scorer** that combines these with configurable weights.
5. **Fallback chains:** on worker failure, timeout, overload or capacity exhaustion, try the next model in the chain.
6. **Cost metrics:** cost/request, cost/1K tokens and cost/1M tokens, in Prometheus and in the request log.
7. **Explainability:** log each routing decision with its reason, and optionally return it in the `X-InferScale-Route` header.

**Key files:** `router/model_registry.py`, `router/classifier.py`, `router/strategies/*.py`, `router/scorer.py`, `router/fallback.py`

**Done when**
- [ ] Coding prompts with `model: auto` route to the coder model
- [ ] Killing the primary model's workers → requests fall back cleanly to the next model
- [ ] Routing decisions and costs are visible in logs and in Grafana

**Tag:** `v1.3`

---

### Phase 8 — Autoscaling

**Goal:** scale workers with demand (plan.md §16, §23 Phase 6).

**Architecture snapshot**
```text
Prometheus ──► Autoscaler (policy loop) ──► Kubernetes API ──► worker replicas
```

**Steps**
1. **Autoscaler control loop** (`autoscaler/`): query Prometheus every N seconds for queue length, p95 latency, request rate and GPU utilisation.
2. **Policy engine:** threshold rules (e.g. `gpu > 80% AND queue > threshold → +1`), with **cooldown**, **min/max replicas** and **hysteresis** to prevent flapping.
3. **Scaler:** patches the worker Deployment's `replicas` through the Kubernetes Python client, behind a `Scaler` interface (a `DockerScaler` is optional for compose).
4. **Comparison:** the same scenario driven by HPA or KEDA on custom metrics.
5. **Optional:** predictive scaling from recent request-rate trends.

**Key files:** `autoscaler/loop.py`, `autoscaler/policy.py`, `autoscaler/scalers/kubernetes.py`, `deploy/k8s/autoscaler.yaml`

**Done when**
- [ ] A Locust ramp scales replicas up, and they scale back down after the load stops
- [ ] No flapping during a steady load
- [ ] Scaling events are visible in Grafana

**Tag:** `v1.4`

---

### Phase 9 — Fault Tolerance and Chaos

**Goal:** stay correct under failure (plan.md §25).

**Steps**
1. **Circuit breaker per worker** (closed → open → half-open), plus **outlier ejection** for slow workers.
2. **Failure-injection API** on the mock worker: `POST /chaos` with `crash`, `slow`, `error_rate` and `hang`.
3. **Scripted scenarios** (`benchmarks/chaos/`): worker crash, model unavailable, GPU unavailable, queue overload, network failure (e.g. toxiproxy), inference timeout, request burst, slow worker and failed health check.
4. **Graceful shutdown:** workers and the gateway stop accepting work, drain in-flight requests, then exit (via a k8s `preStop` hook).

**Key files:** `router/circuit_breaker.py`, `worker/chaos.py`, `benchmarks/chaos/*.py`

**Done when**
- [ ] Every scenario has a script and a recorded result: **recovery time, error rate, request loss**
- [ ] Rolling restarts complete with zero dropped requests

**Tag:** `v1.5`

---

### Phase 10 — Benchmarking and Write-up

**Goal:** back every claim with numbers (plan.md §24).

**Experiments** (scripts in `benchmarks/`, results in `benchmarks/results/`)
1. **Routing:** round robin vs least connections vs latency-aware
2. **Scaling:** fixed workers vs autoscaling
3. **Queueing:** effect of queue size, concurrency, priority and backpressure
4. **Failure:** recovery time, error rate, request loss and fallback performance
5. **Model routing:** single large model vs multiple specialised models

**Deliverables**
- The baseline-vs-optimised table (p50/p95/p99, throughput, TTFT, GPU utilisation, queue time, error rate, cost/1M tokens)
- A README update with the architecture diagram, results, a demo guide and lessons learned

**Tag:** `v2.0` 🚀

---

## 4. Cross-cutting Conventions

| Area | Convention |
|---|---|
| Testing | Unit tests for strategy and queue logic. Integration tests in-process with `httpx.ASGITransport`. E2E tests against compose/k8s. |
| Config | All tunables in `config/*.yaml`, overridable through env vars (`INFERSCALE_...`) |
| Logging | Structured JSON, always including `request_id` |
| Errors | OpenAI-style error bodies with correct HTTP codes (401, 429, 502, 503, 504) |
| Docs | Each phase updates the README "Current capabilities" section and ticks the progress tracker |
| Git | Feature branch per step → `develop`. Milestone tag → merge to `main` |
| Out of scope (for now) | Cloud deployment, a web UI, multi-tenant billing, model training |

---

## 5. Phase → plan.md Traceability

| Phase | Implements plan.md sections |
|---|---|
| 0 | §27 (tech stack), §31 (philosophy: build incrementally) |
| 1 | §3 (request lifecycle), §19 (mock workers), §23 Phase 1 |
| 2 | §7, §10, §11, §12.1, §12.2, §23 Phase 2 |
| 3 | §3 Step 2 (gateway), §4 (queue), §12.5 (priority), §23 Phase 3 |
| 4 | §14 (observability), §15 (TTFT), §23 Phase 4, **§32 Initial Milestone** |
| 5 | §17 (Kubernetes), §18 (local-first), §23 Phase 5 |
| 6 | §9 (worker vs engine), §20 (real workers) |
| 7 | §5, §6 (router + registry), §12.3, §12.4, §12.5, §13 (fallback), §23 Phase 7 |
| 8 | §16 (autoscaling), §23 Phase 6 |
| 9 | §25 (failure scenarios) |
| 10 | §24 (benchmarking), §30 (final vision) |
