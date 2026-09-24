# InferScale

> **A production-oriented, local-first LLM inference platform with intelligent routing, distributed workers, dynamic scaling, and observability.**

InferScale is a personal project for exploring the engineering problems behind **LLM inference infrastructure**.

Instead of building another chatbot or RAG application, InferScale focuses on the infrastructure underneath AI applications:

- How inference requests are received and validated
    
- How requests are queued and scheduled
    
- How the appropriate model is selected
    
- How requests are distributed across inference workers
    
- How workers execute model inference
    
- How overloaded workers are detected
    
- How the system scales horizontally
    
- How failures and model fallbacks are handled
    
- How latency, throughput, GPU utilization, and cost are measured
    
- How routing decisions can become latency-, cost-, and capacity-aware
    

The project is designed to be **local-first and potentially completely free to build**, using a personal machine instead of paid cloud infrastructure.

---

# 1. Why InferScale?

Modern AI applications increasingly depend on multiple models and inference workloads.

A company may have:

```text
                    AI Platform
                        │
        ┌───────────────┼────────────────┐
        ▼               ▼                ▼
  Customer Support   Coding Assistant   Document AI
        │               │                │
        ▼               ▼                ▼
     LLM A           LLM B             LLM C
```

Without an inference platform, every application has to independently deal with:

- Model deployment
    
- GPU allocation
    
- Load balancing
    
- Queuing
    
- Scaling
    
- Health checks
    
- Retries
    
- Failover
    
- Monitoring
    
- Cost management
    

InferScale aims to provide a common inference layer.

Applications simply send an inference request:

```text
Application
     │
     ▼
InferScale
     │
     ├── Model selection
     ├── Worker selection
     ├── Queueing
     ├── Load balancing
     ├── Fallback
     └── Observability
```

The application does not need to know which worker, model replica, or GPU ultimately processes the request.

---

# 2. Core Idea

The central idea is:

> **InferScale is a traffic-control and resource-management layer sitting in front of multiple LLM inference servers.**

The system separates two responsibilities:

### Control plane

InferScale manages:

- API gateway
    
- Request validation
    
- Authentication
    
- Rate limiting
    
- Request queues
    
- Model routing
    
- Worker selection
    
- Scheduling
    
- Priorities
    
- Retries
    
- Fallbacks
    
- Autoscaling
    
- Observability
    

### Inference plane

Existing inference engines perform the actual model execution.

For example:

- vLLM
    
- Other OpenAI-compatible inference servers
    
- Local inference engines
    

The architecture therefore looks like:

```text
                    Client
                      │
                      ▼
               ┌─────────────┐
               │ API Gateway │
               └──────┬──────┘
                      │
                      ▼
               ┌─────────────┐
               │ Request     │
               │ Queue       │
               └──────┬──────┘
                      │
                      ▼
               ┌─────────────┐
               │ Model       │
               │ Router      │
               └──────┬──────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
      Worker 1    Worker 2    Worker 3
          │           │           │
        vLLM        vLLM        vLLM
          │           │           │
        Model A      Model A      Model B
```

---

# 3. Request Lifecycle

A request passes through several stages.

## Step 1 — Client sends a request

A client might send:

```json
{
  "model": "auto",
  "messages": [
    {
      "role": "user",
      "content": "Write a Python function to detect cycles in a graph"
    }
  ]
}
```

The client does not necessarily specify the exact model.

It can request:

```text
model = auto
```

and let InferScale decide.

---

## Step 2 — API Gateway

The API Gateway is responsible for generic API concerns.

Responsibilities include:

- Authentication
    
- Authorization
    
- Rate limiting
    
- Request validation
    
- Request IDs
    
- Basic request normalization
    

Example metadata:

```json
{
  "request_id": "abc123",
  "user_id": "user42",
  "priority": "normal"
}
```

The gateway does **not** decide which GPU should process the request.

---

# 4. Request Queue

After validation, requests can enter a queue.

```text
API Gateway
     │
     ▼
┌────────────────────┐
│   Request Queue    │
│                    │
│ R101               │
│ R102               │
│ R103               │
│ R104               │
└─────────┬──────────┘
          │
          ▼
       Router
```

The queue provides a buffer when incoming traffic temporarily exceeds available inference capacity.

Without a queue:

```text
Traffic spike
     │
     ▼
All workers busy
     │
     ▼
Requests rejected
```

With a queue:

```text
Traffic spike
     │
     ▼
Requests queued
     │
     ▼
Workers process requests as capacity becomes available
```

The queue can eventually support:

- FIFO scheduling
    
- Priority queues
    
- Model-specific queues
    
- Backpressure
    
- Queue limits
    
- Request expiration
    
- Retry policies
    

---

# 5. Model Router

The router is one of the most important components of InferScale.

Its basic question is:

> **Which model and worker should handle this request?**

For example:

```text
Request
   │
   ├── simple query ──────► Small model
   │
   ├── reasoning query ───► Large model
   │
   └── coding query ──────► Coding model
```

The router can consider:

- Task type
    
- Model capability
    
- Model availability
    
- Worker load
    
- Latency
    
- Queue length
    
- Cost
    
- Priority
    
- Token requirements
    
- Failure state
    

---

# 6. Example Model Registry

InferScale can maintain metadata about available models:

```text
┌────────────┬──────────┬─────────┬──────────┐
│ Model      │ Type     │ Cost    │ Capacity │
├────────────┼──────────┼─────────┼──────────┤
│ Llama 8B   │ General  │ Low     │ High     │
│ Llama 70B  │ General  │ High    │ Low      │
│ Qwen Coder │ Coding   │ Medium  │ Medium   │
└────────────┴──────────┴─────────┴──────────┘
```

A coding request could therefore be routed to:

```text
Request
   │
   ▼
Router
   │
   │ task = coding
   ▼
Qwen Coder
```

---

# 7. What Is a Worker?

A worker is a **model-serving replica that performs the actual inference**.

A worker can be thought of as:

```text
┌─────────────────────────────┐
│          Worker             │
│                             │
│   Inference Server          │
│        │                    │
│        ▼                    │
│       vLLM                  │
│        │                    │
│        ▼                    │
│      LLM Model              │
│        │                    │
│        ▼                    │
│       GPU                   │
└─────────────────────────────┘
```

For example:

```text
Worker 1 → Llama 8B
Worker 2 → Llama 8B
Worker 3 → Qwen Coder
Worker 4 → Llama 70B
```

The worker is responsible for executing inference.

The router is responsible for deciding where the request should go.

This separation is fundamental:

```text
Router
  │
  │ "Where?"
  ▼
Worker
  │
  │ "Execute"
  ▼
Model
```

---

# 8. Is a Worker Similar to a Celery Worker?

Yes, conceptually — but they serve different purposes.

## Celery

A typical Celery architecture:

```text
Producer
   │
   ▼
Message Broker
   │
   ▼
Celery Worker
   │
   ▼
Task
```

The worker executes general background tasks:

```python
@celery.task
def resize_image(path):
    ...
```

## InferScale

InferScale:

```text
Client
   │
   ▼
InferScale
   │
   ▼
Router
   │
   ▼
Inference Worker
   │
   ▼
vLLM
   │
   ▼
LLM
```

The key difference is:

> **A Celery worker is a general-purpose task executor, whereas an InferScale worker is primarily a model-serving/inference process.**

The analogy is useful because both systems distribute work across workers.

However, InferScale workers are specialized around AI inference.

---

# 9. Worker vs Inference Engine

InferScale should **not reinvent the LLM inference engine**.

For example:

```text
InferScale
    │
    │ controls
    ▼
Worker
    │
    │ uses
    ▼
vLLM
    │
    │ executes
    ▼
LLM
```

vLLM handles difficult inference-level concerns such as:

- Token generation
    
- GPU execution
    
- KV cache management
    
- Continuous batching
    
- Concurrent sequences
    
- Model loading
    

InferScale focuses on the infrastructure around the inference engine.

---

# 10. Multiple Workers

Multiple workers provide horizontal scalability.

Suppose one worker can process approximately:

```text
20 requests/sec
```

and the application receives:

```text
100 requests/sec
```

InferScale can distribute requests:

```text
                 Router
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
       W1          W2          W3
       20          20          20 req/s
```

More replicas can be added:

```text
       W1
       W2
       W3
       W4
       W5
```

This is horizontal scaling.

---

# 11. Worker Load

Workers can expose telemetry such as:

```text
Worker 1
GPU utilization = 92%
Active requests = 8
Queue = 12
p95 latency = 850 ms

Worker 2
GPU utilization = 45%
Active requests = 2
Queue = 0
p95 latency = 180 ms

Worker 3
GPU utilization = 75%
Active requests = 5
Queue = 4
p95 latency = 400 ms
```

A simple round-robin router might ignore this information.

InferScale can eventually use it.

For example:

```text
Worker 1 → overloaded
Worker 2 → healthy
Worker 3 → moderately loaded

              ↓

Send request → Worker 2
```

---

# 12. Routing Strategies

InferScale should progressively implement different routing strategies.

## 12.1 Round Robin

```text
R1 → W1
R2 → W2
R3 → W3
R4 → W1
R5 → W2
```

Simple baseline.

---

## 12.2 Least Connections

Suppose:

```text
W1 = 8 active requests
W2 = 2 active requests
W3 = 5 active requests
```

The next request goes to:

```text
W2
```

---

## 12.3 Latency-Aware Routing

Suppose:

```text
W1 → p95 = 900 ms
W2 → p95 = 200 ms
W3 → p95 = 400 ms
```

The router prefers:

```text
W2
```

---

## 12.4 Cost-Aware Routing

Different models may have different costs.

```text
Model A
quality = 8/10
cost = low
latency = low

Model B
quality = 9/10
cost = high
latency = high
```

A simple request may use Model A while a complex request may use Model B.

---

## 12.5 Priority-Aware Routing

Requests can have different priorities:

```text
HIGH
NORMAL
LOW
```

When capacity is constrained:

```text
HIGH
  ↓
processed first

NORMAL
  ↓
processed next

LOW
  ↓
processed when capacity exists
```

---

# 13. Fallback Models

InferScale should be resilient to model/worker failures.

Without fallback:

```text
Request
   │
   ▼
70B Worker
   │
   X
   │
   ▼
500 Error
```

With fallback:

```text
Request
   │
   ▼
70B Worker
   │
   X
   │
   ▼
Fallback Model
   │
   ▼
Response
```

Example:

```yaml
fallback:
  - llama-70b
  - llama-8b
```

Fallback policies can eventually consider:

- Worker failure
    
- Timeout
    
- Model overload
    
- GPU failure
    
- Capacity exhaustion
    

---

# 14. Observability

Every request should generate telemetry.

Example:

```text
Request ID: abc123

Gateway latency       = 4 ms
Routing latency       = 2 ms
Queue wait            = 120 ms
Model prefill         = 200 ms
TTFT                   = 322 ms
Generation             = 780 ms
Total latency          = 1.1 sec
Tokens generated       = 240
```

Important metrics include:

### Request metrics

- Requests/sec
    
- Error rate
    
- Request count
    
- Success rate
    

### Latency metrics

- p50 latency
    
- p95 latency
    
- p99 latency
    
- Queue time
    
- Routing latency
    
- TTFT
    

### Inference metrics

- Tokens/sec
    
- Input tokens
    
- Output tokens
    
- Total tokens
    
- GPU utilization
    
- GPU memory utilization
    

### Infrastructure metrics

- CPU utilization
    
- Memory utilization
    
- Worker count
    
- Queue length
    
- Active requests
    

### Cost metrics

- Cost/request
    
- Cost/1K tokens
    
- Cost/1M tokens
    

---

# 15. TTFT

**TTFT = Time To First Token.**

For streaming LLM applications, this is particularly important.

Example:

```text
User sends request
       │
       │
       ├──── 100 ms
       │
       ▼
First token appears
```

That initial delay is approximately the TTFT.

A system can therefore have:

```text
Request A
TTFT = 200 ms
Generation = 5 sec
```

and:

```text
Request B
TTFT = 2 sec
Generation = 3 sec
```

Both have different user-perceived performance characteristics.

InferScale should measure these independently.

---

# 16. Autoscaling

Suppose traffic increases:

```text
10 req/sec
      ↓
50 req/sec
      ↓
150 req/sec
```

Workers become overloaded:

```text
GPU utilization > 80%
Queue length increasing
p95 latency increasing
```

The system can scale:

```text
2 workers
    ↓
4 workers
    ↓
8 workers
```

When traffic falls:

```text
150 req/sec
      ↓
50 req/sec
      ↓
10 req/sec
```

the system can scale back down.

This reduces resource consumption.

---

# 17. Kubernetes

Kubernetes can manage the worker replicas.

Conceptually:

```text
                  Kubernetes
                      │
             ┌────────┴────────┐
             │ Model Deployment │
             └────────┬────────┘
                      │
          ┌───────────┼───────────┐
          ▼           ▼           ▼
       Worker 1    Worker 2    Worker 3
```

Kubernetes can provide:

- Replica management
    
- Service discovery
    
- Health checks
    
- Restarting failed workers
    
- Readiness probes
    
- Liveness probes
    
- Resource limits
    
- Scheduling
    
- Autoscaling
    
- Rolling deployments
    

For example, deliberately killing:

```bash
kubectl delete pod worker-1
```

should result in Kubernetes creating a replacement worker.

---

# 18. Local-First Architecture

InferScale is intentionally designed so that development does not require paid cloud infrastructure.

The entire platform can run on a personal machine.

```text
                     Personal Laptop
                           │
                    Docker / Kubernetes
                           │
          ┌────────────────┼────────────────┐
          ▼                ▼                ▼
     API Gateway        Router           Workers
                                             │
                                            LLM
          │                                  │
          └──────────────┬───────────────────┘
                         ▼
                    Prometheus
                         │
                         ▼
                      Grafana
```

Potentially free components:

|Component|Technology|
|---|---|
|API|FastAPI|
|Containers|Docker|
|Cluster|Kind / Minikube / k3d|
|Queue|Redis|
|Database|PostgreSQL|
|Metrics|Prometheus|
|Dashboard|Grafana|
|Tracing|OpenTelemetry|
|Inference|vLLM / local inference|
|Testing|pytest|
|Load testing|Locust / k6|
|Version control|Git / GitHub|

The project does not require cloud GPUs to demonstrate the core engineering concepts.

---

# 19. Mock Workers

A particularly useful development technique is to initially create **mock inference workers**.

Instead of loading an actual LLM:

```python
async def inference(request):
    await asyncio.sleep(simulated_latency)
    return response
```

This allows InferScale to test:

- Routing
    
- Queuing
    
- Concurrency
    
- Backpressure
    
- Load balancing
    
- Retries
    
- Autoscaling logic
    
- Failure handling
    
- Benchmarking
    

without requiring a GPU.

The architecture remains:

```text
Client
  │
  ▼
Gateway
  │
  ▼
Queue
  │
  ▼
Router
  │
  ├── Mock Worker 1
  ├── Mock Worker 2
  └── Mock Worker 3
```

Real model serving can be introduced later.

---

# 20. Real Model Workers

Once the platform works with mock workers, replace them with actual inference servers.

```text
                 InferScale
                     │
                     ▼
                  Router
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
       Worker 1   Worker 2   Worker 3
          │          │          │
        vLLM        vLLM        vLLM
          │          │          │
       Model A     Model A     Model B
```

The control plane remains mostly unchanged.

Only the worker implementation changes from:

```text
Mock inference
```

to:

```text
Real inference
```

This separation makes the architecture easier to develop and test.

---

# 21. Example Production Scenario

Imagine an organization has:

```text
100,000 users
```

and applications including:

```text
Customer support
Coding assistant
Document analysis
Search
Summarization
AI agents
```

Instead of every application managing its own inference infrastructure:

```text
Application
     │
     ▼
InferScale
     │
     ├── Model selection
     ├── Worker selection
     ├── Queuing
     ├── Scaling
     ├── Fallback
     └── Monitoring
```

InferScale becomes a centralized internal AI inference platform.

---

# 22. Project Architecture

The target architecture is:

```text
                         CLIENTS
                            │
                            ▼
                  ┌──────────────────┐
                  │    API Gateway   │
                  │                  │
                  │ Auth             │
                  │ Rate Limit       │
                  │ Validation       │
                  │ Request ID       │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  Request Queue   │
                  │                  │
                  │ Priority         │
                  │ Backpressure     │
                  └────────┬─────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │  MODEL ROUTER    │
                  │                  │
                  │ Task type        │
                  │ Model capability │
                  │ Latency          │
                  │ Cost             │
                  │ Load             │
                  │ Priority         │
                  │ Fallback         │
                  └────────┬─────────┘
                           │
             ┌─────────────┼─────────────┐
             │             │             │
             ▼             ▼             ▼
        ┌─────────┐   ┌─────────┐   ┌─────────┐
        │ Model A │   │ Model B │   │ Model C │
        │ Worker  │   │ Worker  │   │ Worker  │
        │ vLLM    │   │ vLLM    │   │ vLLM    │
        └────┬────┘   └────┬────┘   └────┬────┘
             │             │             │
             └─────────────┼─────────────┘
                           │
                           ▼
                  ┌──────────────────┐
                  │   OBSERVABILITY  │
                  │                  │
                  │ Prometheus       │
                  │ OpenTelemetry    │
                  │ Logs             │
                  │ Traces           │
                  └────────┬─────────┘
                           │
             ┌─────────────┼─────────────┐
             ▼             ▼             ▼
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │ Grafana  │  │ Router   │  │Autoscaler│
        │Dashboard │  │ Feedback │  │          │
        └──────────┘  └──────────┘  └────┬─────┘
                                         │
                                         ▼
                                  Kubernetes API
                                         │
                                         ▼
                                  Scale Workers
```

---

# 23. Development Roadmap

InferScale should be developed incrementally.

## Phase 0 — Understand the system

Before writing infrastructure code, understand:

- HTTP request lifecycle
    
- Async Python
    
- FastAPI
    
- Processes vs threads
    
- Queues
    
- Concurrency
    
- Docker
    
- Basic LLM inference
    

---

## Phase 1 — Single Inference Server

Build:

```text
Client
  │
  ▼
FastAPI
  │
  ▼
Inference Server
  │
  ▼
Model
```

Objectives:

- OpenAI-compatible API
    
- Request/response handling
    
- Streaming
    
- Basic metrics
    

---

## Phase 2 — Multiple Workers

Build:

```text
Client
  │
  ▼
Gateway
  │
  ▼
Router
  │
  ├── Worker 1
  ├── Worker 2
  └── Worker 3
```

Implement:

- Worker registry
    
- Worker health
    
- Round-robin routing
    
- Least-connections routing
    

---

## Phase 3 — Queue and Scheduling

Introduce:

```text
Gateway
   │
   ▼
Queue
   │
   ▼
Scheduler
   │
   ▼
Workers
```

Implement:

- FIFO
    
- Priority queues
    
- Queue limits
    
- Backpressure
    
- Request timeout
    
- Retries
    

---

## Phase 4 — Observability

Add:

```text
Prometheus
Grafana
OpenTelemetry
```

Measure:

- p50
    
- p95
    
- p99
    
- TTFT
    
- Throughput
    
- Queue time
    
- Tokens/sec
    
- GPU utilization
    
- Error rate
    

---

## Phase 5 — Kubernetes

Containerize the platform.

Introduce:

- Kubernetes
    
- Deployments
    
- Services
    
- ConfigMaps
    
- Secrets
    
- Readiness probes
    
- Liveness probes
    
- Replica management
    

---

## Phase 6 — Autoscaling

Build scaling policies.

Example:

```text
IF

GPU utilization > 80%
AND
queue length > threshold

THEN

increase replicas
```

Eventually experiment with more sophisticated policies using:

- Queue length
    
- p95 latency
    
- Request rate
    
- GPU utilization
    
- Predicted traffic
    

---

## Phase 7 — Intelligent Routing

Implement:

```text
Task classification
        ↓
Model selection
        ↓
Worker selection
```

Add:

- Capability-aware routing
    
- Latency-aware routing
    
- Cost-aware routing
    
- Token-aware routing
    
- Priority-aware routing
    
- Fallback models
    

---

# 24. Benchmarking

A major goal is to **measure the system rather than simply claim that it works**.

For example:

```text
                    Baseline       Optimized

p50 latency           X ms            Y ms
p95 latency           X ms            Y ms
p99 latency           X ms            Y ms
throughput            X req/s         Y req/s
TTFT                  X ms            Y ms
GPU utilization       X %             Y %
queue time            X ms            Y ms
error rate            X %             Y %
cost / 1M tokens      X               Y
```

The actual numbers should come from experiments.

Potential experiments:

### Experiment 1 — Routing

Compare:

```text
Round Robin
vs
Least Connections
vs
Latency-Aware
```

### Experiment 2 — Scaling

Compare:

```text
Fixed workers
vs
Autoscaling
```

### Experiment 3 — Queueing

Measure the effect of:

```text
Queue size
Concurrency
Priority
Backpressure
```

### Experiment 4 — Failure

Deliberately kill workers and measure:

```text
Recovery time
Error rate
Request loss
Fallback performance
```

### Experiment 5 — Model routing

Compare:

```text
Single large model
vs
Multiple specialized models
```

---

# 25. Failure Scenarios

InferScale should eventually be tested against failures such as:

```text
Worker crash
Model unavailable
GPU unavailable
Queue overload
Network failure
Inference timeout
High request burst
Slow worker
Failed health check
```

For example:

```text
Worker 1
    │
    X
    │
    ▼
Health check fails
    │
    ▼
Router removes Worker 1
    │
    ▼
Requests routed elsewhere
    │
    ▼
Kubernetes creates replacement
```

This is an important part of making the system production-oriented.

---

# 26. What InferScale Is Not

InferScale is intentionally **not**:

- A chatbot
    
- A RAG application
    
- A prompt engineering project
    
- A model-training project
    
- A replacement for vLLM
    
- A replacement for Kubernetes
    

Instead, it sits around inference infrastructure.

The goal is to understand:

> **How do we efficiently operate AI inference workloads at scale?**

---

# 27. Technology Stack

The initial technology stack can be:

```text
Language
    Python

API
    FastAPI

Inference
    vLLM
    Local/quantized models

Containerization
    Docker

Orchestration
    Kubernetes
    Kind / Minikube / k3d

Queue
    Redis

Database / Metadata
    PostgreSQL

Metrics
    Prometheus

Visualization
    Grafana

Tracing
    OpenTelemetry

Testing
    pytest

Load Testing
    Locust / k6

Version Control
    Git / GitHub
```

The exact stack can evolve as the architecture develops.

---

# 28. Local-First / ₹0 Goal

InferScale is intentionally designed to be developed without cloud expenditure.

Most of the project can run entirely on a personal machine:

```text
Laptop
  │
  ├── Docker
  │
  ├── Kubernetes
  │
  ├── Redis
  │
  ├── PostgreSQL
  │
  ├── Prometheus
  │
  ├── Grafana
  │
  ├── Mock workers
  │
  └── Small local LLM
```

Cloud GPU infrastructure is optional.

A cloud deployment can be documented as a future extension rather than a requirement.

---

# 29. Why Mock Workers Are Important

A common mistake would be to start by trying to run several large LLMs.

That is unnecessary.

The first objective is to understand the **distributed system**.

Mock workers allow experiments such as:

```text
100 requests/sec
500 requests/sec
1000 requests/sec
```

without requiring expensive GPU resources.

The mock worker can simulate:

```text
Inference latency
GPU utilization
Failures
Queueing
Token generation
Model capacity
```

Once the control plane is stable, real LLM workers can replace the mocks.

---

# 30. Final Vision

The long-term vision is:

```text
                    APPLICATIONS
                         │
                         ▼
                ┌─────────────────┐
                │    InferScale   │
                │                 │
                │ API Gateway     │
                │ Queue           │
                │ Router          │
                │ Scheduler       │
                │ Autoscaler      │
                │ Observability   │
                └────────┬────────┘
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       Model A         Model B        Model C
       Workers         Workers        Workers
          │              │              │
          └──────────────┼──────────────┘
                         ▼
                    GPUs / CPUs
```

The goal is not simply:

> "I deployed an LLM."

The goal is:

> **"I designed and implemented a distributed platform for routing, scheduling, scaling, monitoring, and reliably serving heterogeneous AI inference workloads."**

That distinction is the core of InferScale.

---

# 31. Project Philosophy

InferScale follows five principles:

### 1. Build the infrastructure, not another chatbot

Focus on the system underneath AI applications.

### 2. Measure everything

Performance claims should be backed by benchmarks.

### 3. Build incrementally

Start with a single worker and progressively introduce complexity.

### 4. Use existing systems where appropriate

Use vLLM for inference and Kubernetes for orchestration rather than reinventing them.

### 5. Local-first

The project should remain useful even without cloud GPUs or paid infrastructure.

---

# 32. Initial Milestone

The first meaningful version should be:

```text
Client
  │
  ▼
FastAPI Gateway
  │
  ▼
Request Queue
  │
  ▼
Model Router
  │
  ├── Worker 1
  ├── Worker 2
  └── Worker 3
  │
  ▼
Metrics
  │
  ▼
Prometheus
  │
  ▼
Grafana
```

with:

- Mock inference workers
    
- Round-robin routing
    
- Basic health checks
    
- Request queue
    
- Request IDs
    
- Prometheus metrics
    
- Grafana dashboard
    
- Load-testing scripts
    
- Automated tests
    
- Docker Compose/local deployment
    

Only after this works should the project move toward:

```text
Kubernetes
      ↓
vLLM
      ↓
Real models
      ↓
Intelligent routing
      ↓
Autoscaling
      ↓
Fault tolerance
      ↓
Benchmarking
```

This keeps the project achievable while leaving a clear path toward a genuinely production-oriented AI inference platform.