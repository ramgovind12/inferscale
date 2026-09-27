# InferScale

A distributed LLM inference platform built incrementally: gateway → queue → scheduler → router → workers.
See [`plan.md`](plan.md) for the vision and [`IMPLEMENTATION_PLAN.md`](IMPLEMENTATION_PLAN.md) for the phased build.

## Quickstart

```bash
python -m venv myenv
source myenv/bin/activate          # Windows: myenv\Scripts\activate
pip install -r requirements-dev.txt

# in two terminals
python -m inferscale.worker        # :9001
python -m inferscale.gateway       # :8000

curl localhost:8000/health
curl localhost:8000/v1/chat/completions -H "Content-Type: application/json"   -d '{"model": "mock-model", "messages": [{"role": "user", "content": "hi"}]}'
# add "stream": true and curl -N for SSE token streaming
```

Or run the whole stack in Docker: `docker compose -f deploy/compose/docker-compose.yml up --build` (or `make up`).

### Using the OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="unused")
reply = client.chat.completions.create(
    model="mock-model", messages=[{"role": "user", "content": "hi"}]
)
```

With `make` available: `make install`, `make check` (lint + typecheck + test), `make run-worker`, `make run-gateway`.

## Configuration

Settings live in [`config/inferscale.yaml`](config/inferscale.yaml). Any key can be overridden with an
environment variable `INFERSCALE_<SECTION>__<KEY>`, e.g. `INFERSCALE_GATEWAY__WORKER_URL=http://worker:9001`.
Point at a different file with `INFERSCALE_CONFIG=path/to/file.yaml`.

Mock worker knobs (`worker.*`): `latency_ms` (time to first token), `tokens_per_sec`, `failure_rate`,
`default_max_tokens`, `model_name`, `seed`.

## Current capabilities

- **Phase 0:** project skeleton, typed config, structured JSON logging, gateway and worker `/health` stubs, CI.
- **Phase 1:** OpenAI-compatible `POST /v1/chat/completions` (normal + SSE streaming) and `GET /v1/models`
  through the gateway to one mock worker; `X-Request-ID` propagated to the worker, logs and response headers;
  OpenAI-style errors (`400`/`404`, worker failure → `502`, timeout → `504`); Dockerfiles + Compose.
