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
```

With `make` available: `make install`, `make check` (lint + typecheck + test), `make run-worker`, `make run-gateway`.

## Configuration

Settings live in [`config/inferscale.yaml`](config/inferscale.yaml). Any key can be overridden with an
environment variable `INFERSCALE_<SECTION>__<KEY>`, e.g. `INFERSCALE_GATEWAY__WORKER_URL=http://worker:9001`.
Point at a different file with `INFERSCALE_CONFIG=path/to/file.yaml`.

## Current capabilities

- **Phase 0:** project skeleton, typed config, structured JSON logging, gateway and worker `/health` stubs, CI.
