# SmartDocs AI

A serverless assistant that answers questions about your own PDFs. Upload a document, ask in plain English,
and Claude (on Amazon Bedrock) answers using only passages retrieved from that document. This is
retrieval-augmented generation (RAG) built from primitives instead of a managed service, so every moving part is visible.

| | |
| --- | --- |
| **Status** | ⬜ Rebuild in progress. Code and tests are done; the AWS runs are what the phase pages document |
| **Region** | ap-south-2 (Hyderabad) |
| **Time budget** | about 7 to 8 hours in one sitting |
| **Running cost** | close to zero when idle. Bedrock tokens are the only real spend; the API key secret is about $0.40/month |
| **Models** | Claude on Bedrock (chat), Amazon Titan Text Embeddings v2 (search) |

## Architecture

```
  UPLOAD                                             ASK
  ──────                                             ───
  client                                             client
    │ POST /upload  (x-api-key)                        │ POST /chat  (x-api-key)
    ▼                                                  ▼
  API Gateway ──► upload Lambda                      API Gateway (throttled 5 req/s)
    │  returns presigned URL                           │
    ▼                                                  ▼
  client PUTs PDF ──► S3  docs/*.pdf                 chat Lambda
                       │ ObjectCreated                 │ 1 embed question ─────────► Titan v2
                       ▼ (prefix docs/, suffix .pdf)   │ 2 search index (in memory) ◄─ S3 index/
                     indexer Lambda                    │ 3 load last 10 messages ◄──► DynamoDB
                       │ PyMuPDF: PDF → text           │ 4 build prompt + excerpts
                       │ 300-word chunks, 50 overlap   │ 5 ask Claude ──────────────► Bedrock
                       │ Titan v2: chunk → 1024 floats │ 6 save the turn ───────────► DynamoDB
                       ▼                               ▼
                     S3  index/faiss.index          answer + sources
                         index/metadata.json

  Both Lambdas share one layer (faiss-cpu, PyMuPDF, numpy).
  Everything is defined in CDK (infra/). CloudWatch watches it (alarms, dashboard, Logs Insights).
```

## Phases

| # | Page | Est. | Actual | Status |
| --- | --- | --- | --- | --- |
| 0 | [Background: what, why, decisions](00-background.md) | 15 min read | : | ✅ |
| 1 | [Foundation: tools, Claude access, clean slate](01-foundation.md) | 45 min | ⏳ | ⬜ |
| 2 | [Storage and RAG: bucket, role, layer, indexer](02-storage-and-rag.md) | 90 min | ⏳ | ⬜ |
| 3 | [API layer: DynamoDB, chat Lambda, API Gateway](03-api-layer.md) | 75 min | ⏳ | ⬜ |
| 4 | [Infrastructure as code with CDK](04-iac-with-cdk.md) | 90 min | ⏳ | ⬜ |
| 5 | [Monitoring: logs, alarms, dashboard](05-monitoring.md) | 45 min | ⏳ | ⬜ |
| 6 | [Auth and polish: API key, presigned uploads](06-auth-and-polish.md) | 60 min | ⏳ | ⬜ |

## Results at a glance

TODO(result): one screenshot of the dashboard with traffic on it (save as `assets/dashboard.png`, redacted).

TODO(result): the headline numbers from the final run: chat latency p50/p95, tokens per question, cold-start time, total Bedrock cost for the sitting.

TODO(result): the output of `scripts/60-e2e-test.sh` ending in "all checks passed" ([results/60-e2e-test.txt](results/60-e2e-test.txt)).

## Quick start

```bash
cd projects/smartdocs-ai
cp config.env.example config.env     # set AWS_REGION; everything else is derived
uv sync                              # Python environment (dev + infra groups)
uv run pytest                        # 49 tests, no AWS needed
```

Then follow the phases in order. Run any script you want documented through the capture tool:

```bash
tools/capture.sh smartdocs-ai 10-bedrock-access bash scripts/10-check-bedrock.sh
```

## Repo map

| Path | What is in it |
| --- | --- |
| `src/indexer`, `src/chat`, `src/upload` | The three Lambda functions |
| `scripts/` | Numbered CLI scripts: `1x` foundation, `2x` storage, `3x` API, `4x` CDK, `5x` monitoring, `6x` e2e, `9x` teardown |
| `infra/` | The CDK app (`smartdocs_stack.py`) and its tests |
| `tests/` | 40 unit tests with in-memory fakes for S3, Bedrock and DynamoDB |
| `pyproject.toml`, `uv.lock` | Dependencies, managed with uv (groups: `dev`, `infra`, `layer`) |
| `results/`, `assets/` | Captured outputs and screenshots that the phase pages link to |

Conventions used across projects: [docs/README.md](../../docs/README.md)
