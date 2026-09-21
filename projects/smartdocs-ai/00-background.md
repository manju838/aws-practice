# Background

## The goal

Build a document Q&A assistant end to end on AWS, in a way that leaves nothing magic: no managed RAG service,
no framework hiding the retrieval step. When it works you can say exactly what happens between "PDF uploaded"
and "answer returned", and you can rebuild it from scratch with one command.

## Why this project

It exists to practice the AWS skills that come up in AI engineering work, each in a place where it is actually needed:

| Skill | Where it shows up here |
| --- | --- |
| IAM, least privilege, execution roles | The Lambda role has four small statements, no `*FullAccess` |
| Amazon Bedrock | Claude for answers, Titan for embeddings, inference profiles, Marketplace subscriptions |
| Event-driven design | An S3 upload triggers indexing with no server polling |
| Lambda layers and cold starts | FAISS and PyMuPDF are native code, shipped as a layer; the index is cached in memory |
| Vector search and RAG | Chunking, embeddings, cosine similarity, relevance thresholds, prompt construction |
| DynamoDB | Conversation memory for a stateless function; TTL; single-table keys |
| API Gateway (HTTP API) | Routes, CORS, stages, throttling |
| Infrastructure as code | The whole stack in CDK, deployed and destroyed in one command each |
| Observability | Structured logs, Logs Insights, p95 alarms, a dashboard |
| Security basics | API key from Secrets Manager, presigned uploads, no public bucket |

## Key decisions

| Decision | Chosen | Alternative | Why |
| --- | --- | --- | --- |
| Vector store | FAISS index file in S3, loaded in Lambda memory | Bedrock Knowledge Bases with OpenSearch Serverless | The managed path costs roughly $3 a day just to exist and hides the mechanics. The file approach is nearly free and teaches the retrieval step. It stops scaling at around 10k chunks |
| How to call Claude | Bedrock Converse API on `bedrock-runtime`, model ID in config | The newer Messages API on the `bedrock-mantle` endpoint | Converse is one consistent call shape across models, works with the same IAM and boto3 as Titan, and needs no extra SDK in the layer. Switching model is a config change |
| Default chat model | Claude Haiku 4.5 through its `global.` inference profile | Sonnet 5, Opus | Cheapest and fastest of the current models, plenty for grounded Q&A. Change `CHAT_MODEL_ID` to compare |
| Embeddings | Titan Text Embeddings v2, 1024 dimensions | Cohere Embed | Already in Bedrock, no extra subscription |
| API type | HTTP API (API Gateway v2) | REST API (v1) | Cheaper and faster for Lambda proxying. REST only wins when you need request transformation or usage plans |
| Auth | Shared API key in Secrets Manager, checked in the Lambda | Cognito with JWT | Good enough for a personal tool and easy to reason about. HTTP APIs have no native API keys. Cognito is the upgrade for real users |
| Uploads | Presigned S3 URLs | Send the PDF through Lambda | Lambda and API Gateway cap payload sizes; direct-to-S3 is also cheaper |
| Python tooling | uv, with dependency groups | pip and venv | One tool for the environment, the lockfile, running tests and even the cross-platform layer build |
| Layer build | `uv pip install --python-platform x86_64-manylinux_2_28` | Docker with the Lambda base image | Same result, no Docker Desktop, works from Windows unchanged |
| Manual first, then CDK | Phases 2 to 3 with CLI scripts, Phase 4 rebuilds it as code | CDK from the start | Doing it by hand once shows what CDK is generating for you |

## History

| When | What happened |
| --- | --- |
| Earlier | Phases 1 to 3 built by hand with CLI scripts and documented: foundation, storage and RAG, API layer. The Phase 4 (CDK) notes were written but the stack was not finished. Phases 5 and 6 were never started |
| May 2026 | Bedrock calls to Claude Haiku 4.5, Opus 4.5 and Sonnet 4.6 failed with `INVALID_PAYMENT_INSTRUMENT`. Bedrock now creates the AWS Marketplace subscription for a third-party model on first use, that first attempt had failed, and the failed subscription stayed stuck even after the payment method was fixed. Other models kept working. This blocked the end-to-end test, so the project paused |
| Sept 2026 | Claude access restored. Restarted from a clean slate with the goal of finishing all six phases in one sitting, documented as it goes |

### What the rebuild changed, and why

The first attempt worked on the happy path. Reviewing it turned up problems worth fixing before repeating it:

| Problem in the first attempt | Fix |
| --- | --- |
| `s3:ObjectCreated` events URL-encode keys, so `my file.pdf` arrives as `my+file.pdf` and the indexer fails with NoSuchKey | Decode with `unquote_plus`. Covered by a test |
| Uploading the same PDF twice appended duplicate chunks, so retrieval returned one passage three times | The indexer removes a document's old chunks before adding new ones. Covered by a test |
| The chat Lambda cached the index forever, so a warm container never saw newly uploaded documents | A cheap `HEAD` request compares the index ETag on each call and reloads when it changed. Covered by a test |
| Follow-up questions such as "What problem does it solve?" retrieve nothing on their own | The retrieval query includes the previous user question |
| History trimmed to the last 10 items could start with an assistant turn, which the model API rejects | History is repaired to start with a user turn and alternate roles |
| `*FullAccess` managed policies on the Lambda role | One inline policy with only the actions and resources used |
| Hardcoded account ID, API URL and a Windows path in scripts (unsafe on a public site) | Everything comes from `config.env` and a runtime lookup; `tools/capture.sh` redacts outputs |
| Public, unauthenticated endpoint calling a paid model | Throttling from day one, API key in Phase 6, and teardown at the end |
| Deploy scripts updated code then configuration back to back, which can fail while an update is still running; new roles are not usable for several seconds | Wait for the update to finish; retry on "role cannot be assumed" |
| Scanned PDFs (no text layer) crashed the indexer | Detected and logged as "nothing indexed" |
| The old sample test asked questions the model could answer from its own memory | A generated manual full of invented facts, so a correct answer proves retrieval |

## Known limitations

* **Concurrent uploads can overwrite each other.** Two PDFs indexed at the same moment each read the index, add their chunks and write it back; the last write wins. Upload one at a time. Production fixes: a queue that feeds one indexer at a time, or reserved concurrency of 1 on the indexer, or S3 conditional writes.
* **The index is one file loaded fully into memory.** Fine up to about 10,000 chunks. Beyond that, use an approximate index (IVF or HNSW) or a vector database.
* **Scanned PDFs are not supported** (no OCR).
* **Re-uploading reorders chunks** in the metadata file. During the second or two between the metadata write and the index write, a chat request could pair a chunk with a slightly wrong index. The write order and a bounds check make crashes impossible, but it is a real if tiny window.
* **CORS allows any origin.** Restrict it once there is a frontend.
* **One shared API key.** No per-user identity or usage limits beyond the stage throttle.

## Where to read next

Start with [Phase 1](01-foundation.md).
