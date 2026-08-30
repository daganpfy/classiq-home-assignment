# Quantum Circuit Task API

Async job service for submitting QASM3 circuits, running them on Qiskit Aer, and polling for results.

The HTTP contract matches the Classiq home assignment. Architecture around it is a durable queue plus a persisted job state machine, so a worker crash does not drop work.

## Quick start

```bash
docker compose up --build
```

API listens on `http://localhost:8000`.

### Health

```bash
curl -s http://localhost:8000/health
```

### Submit (Hadamard, 1024 shots)

```bash
curl -s -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"qc":"OPENQASM 3.0;\ninclude \"stdgates.inc\";\nbit[1] c;\nqubit[1] q;\nh q[0];\nc[0] = measure q[0];\n"}'
```

### Poll

Replace the id from the submit response:

```bash
curl -s http://localhost:8000/tasks/<task_id>
```

### Submit and poll in one shot

First GET is often `pending`. After a few seconds, GET should be `completed` with counts summing to 1024.

```bash
TASK_ID=$(curl -s -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"qc":"OPENQASM 3.0;\ninclude \"stdgates.inc\";\nbit[1] c;\nqubit[1] q;\nh q[0];\nc[0] = measure q[0];\n"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['task_id'])")

echo "task_id=$TASK_ID"
curl -s "http://localhost:8000/tasks/$TASK_ID"
sleep 3
curl -s "http://localhost:8000/tasks/$TASK_ID"
```

### Bell pair

```bash
curl -s -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"qc":"OPENQASM 3.0;\ninclude \"stdgates.inc\";\nbit[2] c;\nqubit[2] q;\nh q[0];\ncx q[0], q[1];\nc[0] = measure q[0];\nc[1] = measure q[1];\n"}'
```

### Negative paths

```bash
# unknown id
curl -s -w "\nHTTP %{http_code}\n" \
  http://localhost:8000/tasks/00000000-0000-0000-0000-000000000000

# invalid QASM
curl -s -w "\nHTTP %{http_code}\n" -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{"qc":"not-a-circuit"}'

# missing qc
curl -s -w "\nHTTP %{http_code}\n" -X POST http://localhost:8000/tasks \
  -H 'Content-Type: application/json' \
  -d '{}'
```

### Metrics

```bash
curl -s http://localhost:8000/metrics | grep tasks_
curl -s http://localhost:9090/metrics | grep tasks_
```

Tear down:

```bash
docker compose down -v
```

## API

### `POST /tasks`

Accepts `{"qc": "<qasm3>"}`. Validates QASM3, persists the job as `pending`, publishes `task_id` to the queue, returns immediately.

```json
{
  "task_id": "3f1c0a5e-2d4b-4c1a-9e7a-1c2d3e4f5a6b",
  "message": "Task submitted successfully."
}
```

HTTP `202 Accepted`.

Negative paths:

| Input | HTTP | Body |
|---|---|---|
| Missing `qc` | 422 | FastAPI validation error |
| Empty `qc` | 422 | FastAPI validation error |
| Invalid QASM3 | 400 | `{"status":"error","message":"Invalid QASM3 circuit: ..."}` |
| Broker unavailable after persist | 503 | `{"status":"error","message":"Failed to enqueue task."}` |

Invalid circuits never enter the queue.

### `GET /tasks/{id}`

| State | HTTP | Body |
|---|---|---|
| Completed | 200 | `{"status":"completed","result":{"0":512,"1":512}}` |
| Still running | 200 | `{"status":"pending","message":"Task is still in progress."}` |
| Unknown id | 404 | `{"status":"error","message":"Task not found."}` |
| Failed (extension) | 200 | `{"status":"failed","message":"..."}` |

`failed` is an extension of the assignment contract. The worker uses it when retries are exhausted or the circuit is unexecutable after enqueue. Documented here so clients can distinguish a poison job from “still running.”

Simulation always uses **1024 shots**, as in the assignment snippet.

## Architecture

```text
Client
  │
  ▼
POST /tasks ── FastAPI (api container)
  │              validate QASM3
  │              INSERT tasks (pending)
  │              publish task_id
  │
  ▼
RabbitMQ queue `tasks`     (durable, ack after success)
  │  dead-letter exchange ──► queue `tasks.dead`
  ▼
Celery worker (worker container)
  │  load job from Postgres
  │  qasm3.loads → transpile → AerSimulator.run
  │  UPDATE completed | failed
  │  ack  /  nack→DLQ
  ▼
GET /tasks/{id} ── FastAPI reads Postgres
```

Four Compose services:

| Service | Role | AWS analogue |
|---|---|---|
| `api` | HTTP, validation, enqueue | ALB + API process |
| `worker` | Circuit execution | ECS consumer |
| `rabbitmq` | Durable work queue + DLQ | SQS + SQS DLQ |
| `postgres` | Client-visible job state | RDS |

The queue message is only `task_id`. The circuit payload lives in Postgres. Redelivery cannot lose or diverge from the stored program.

### Why not run Aer in the request

`POST /tasks` must return a `task_id` without waiting on simulation. The worker is a **separate process and container**, which is the “components for asynchronous task processing” deliverable.

### Task integrity (no lost jobs)

Same rules as SQS visibility timeout:

1. Persist `pending` **before** publish.
2. If publish fails, mark `failed` and return 503 — no silent pending row with no message.
3. Worker uses `acks_late=True` and `task_reject_on_worker_lost=True` (ack **after** the DB write, not on receive).
4. `worker_prefetch_multiplier=1` so an in-flight task is not hoarded.
5. Worker crash before ack → RabbitMQ redelivers → job stays `pending` → retry.
6. Processing is idempotent: already `completed` / `failed` is a no-op ack.

## Job state machine

Implemented in `app/domain/task.py`. Transitions are guarded; illegal ones raise `InvalidTransitionError`.

```text
        submit
          │
          ▼
      PENDING ──success──► COMPLETED
          │
          ├── worker died / transient error ──► PENDING (redeliver, retry_count++)
          └── max retries or permanent error ──► FAILED
                                                + message to DLQ

COMPLETED and FAILED are terminal.
```

`GET` maps `PENDING` / `COMPLETED` to the assignment JSON. `FAILED` is the extra status above.

## Dead-letter queue

Queue `tasks` is declared with:

- `x-dead-letter-exchange: tasks.dlx`
- `x-dead-letter-routing-key: tasks.dead`

After `CELERY_MAX_RETRIES` (default 3), the worker:

1. Marks the row `failed` in Postgres (if the row exists).
2. `Reject(requeue=False)` so RabbitMQ dead-letters the message to `tasks.dead`.

Inspect it in the RabbitMQ UI: [http://localhost:15672](http://localhost:15672) (`guest` / `guest`) → Queues → `tasks.dead`.

Poison messages do not block the main queue.

## Observability / KPIs

Structured JSON logs (`task_id`, `status`, `reason`, durations).

| Endpoint | What |
|---|---|
| `GET /health` | Postgres + RabbitMQ checks |
| `GET /metrics` (api :8000) | HTTP metrics + task counters |
| `http://localhost:9090/metrics` (worker) | processing histogram, retries, DLQ |

Custom metrics:

- `tasks_submitted_total`
- `tasks_completed_total`
- `tasks_failed_total{reason}`
- `tasks_retried_total`
- `tasks_dlq_total`
- `task_processing_duration_seconds`
- `queue_publish_errors_total`

KPIs to watch: submit vs complete lag, DLQ rate, retry rate, p95 `task_processing_duration_seconds`, `/health` degraded.

## Project layout

```text
app/
  main.py                 FastAPI composition root
  routers/tasks.py        HTTP adapter (controller)
  routers/health.py
  schemas.py              request/response models
  services/               application use-cases
    task_service.py       submit + get
    task_processor.py     worker-side execution
    circuit_executor.py   Qiskit only
  domain/task.py          status enum + transitions
  repositories/           Postgres mapping
  queue/                  Celery app, publisher, DLQ topology
  worker/tasks.py         Celery consumer
  interfaces.py           Protocols (DIP)
  container.py            wiring
  metrics.py
tests/
  unit/                   state machine, services, Qiskit
  integration/            live POST → worker → GET
```

Routers depend on `TaskService`. `TaskService` / `TaskProcessor` depend on Protocols, not FastAPI, Celery, or SQLAlchemy. Qiskit is isolated behind `CircuitRunner`.

## Tests

Unit tests (no Docker):

```bash
pip install -r requirements.txt
pytest tests/unit -v
```

Full stack, including integration tests:

```bash
docker compose up --build -d
docker compose --profile test run --rm tests
```

Integration coverage:

- submit → process → retrieve counts summing to 1024
- unknown `task_id` → assignment error body
- invalid QASM3 → 400
- missing `qc` → 422
- `/health` against real Postgres and RabbitMQ

## Design notes

- **Python 3.11**, FastAPI, Celery, RabbitMQ, Postgres — all started by Compose.
- **Qiskit Aer** is the simulator from the assignment snippet (`transpile` + `AerSimulator`, 1024 shots). QASM3 via `qiskit.qasm3`.
- RabbitMQ over Redis-as-broker: messages survive broker restart with durable queues; closer to SQS than an in-memory map.
- Celery result backend is unused. Postgres is the source of truth for `GET /tasks/{id}`.
- HTTP 202 / 404 are unspecified in the PDF; they are the usual async-job mapping. Bodies for the three required states match the spec exactly.

## Configuration

| Variable | Default | Meaning |
|---|---|---|
| `DATABASE_URL` | Compose Postgres (`postgresql+psycopg://...`) | SQLAlchemy URL |
| `BROKER_URL` | Compose RabbitMQ | AMQP URL |
| `SHOTS` | `1024` | Aer shots |
| `CELERY_MAX_RETRIES` | `3` | then DLQ |
| `LOG_LEVEL` | `INFO` | JSON logs |
| `METRICS_PORT` | `9090` | worker Prometheus |
