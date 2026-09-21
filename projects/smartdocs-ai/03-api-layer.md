# Phase 3: API layer

| | |
| --- | --- |
| **Time budget** | 75 min |
| **Actual time** | ⏳ |
| **Cost** | Claude tokens only |
| **Status** | ⬜ Not started |

## Why this phase exists

Now the documents get a voice. The chat Lambda runs the whole RAG loop, DynamoDB gives the stateless function a memory,
and API Gateway puts a public HTTPS address in front of it.

```
client ─ POST /chat ─► API Gateway ─► chat Lambda ─┬─► Titan  (embed the question)
                                                   ├─► S3     (the index, cached in memory)
                                                   ├─► DynamoDB (history in, new turn out)
                                                   └─► Claude on Bedrock (Converse API)
```

## Steps

### 1. Conversation memory

```bash
tools/capture.sh smartdocs-ai 30-table bash scripts/30-create-table.sh
```

Lambda forgets everything between calls, so the last 10 messages are read from DynamoDB at the start of a request and the new pair is written at the end.
Partition key `session_id` (which conversation) plus sort key `timestamp` (order) gives you one conversation in chronological order with a single query.
Pay-per-request billing means no minimum cost, and a `ttl` attribute lets DynamoDB delete week-old conversations for free.

### 2. Read the chat Lambda

`src/chat/lambda_function.py` in six moves: retrieve, load history, build the prompt, ask Claude, save the turn, return. Notes on the choices:

* **The retrieval query includes the previous question.** "What problem does it solve?" means nothing to a vector search on its own.
* **The prompt says the excerpts are untrusted data.** A PDF could contain "ignore your instructions"; the model is told to treat excerpts as text, not commands.
* **If nothing relevant is found, the model is still called**, told there are no excerpts, and instructed to say so. It can still use the conversation history.
* **A model failure returns 502 and saves nothing**, so a failed turn does not poison the history.
* **Logs are one JSON object per line** with duration, chunk count, top score and token counts, ready for Phase 5.

### 3. Deploy it

```bash
tools/capture.sh smartdocs-ai 31-deploy-chat bash scripts/31-deploy-chat.sh
```

512 MB, 30 s timeout, same layer, and the model ID passed as an environment variable.

### 4. Put an API in front

```bash
tools/capture.sh smartdocs-ai 32-api bash scripts/32-create-api.sh
```

An HTTP API with a Lambda proxy integration, one route (`POST /chat`), a `prod` stage, and a permission for API Gateway to invoke the function.
The stage is **throttled to 5 requests per second (burst 10) from the start**: this endpoint is public and every request costs money.
The URL is written to `build/`, which is git-ignored. Do not paste it into the docs.

### 5. Ask questions and check the answers

```bash
tools/capture.sh smartdocs-ai 33-chat bash scripts/33-test-chat.sh
```

The script asks four questions and checks the answers automatically:

1. The kettle's temperature and heating time (must contain `87.5`).
2. "How long is its warranty?" (a follow-up with no subject; must contain `26`, which only works if history is loaded).
3. Where the company was founded (must contain `Lisbon`).
4. The capital of Australia (not in the document; it should decline).

## Verify

* All checks print a tick and the script ends "all checks passed".
* Look at question 4: a grounded assistant says it cannot find that in the documents.
* In DynamoDB, one session has alternating `user` and `assistant` items with a `ttl` value.
* `aws logs tail /aws/lambda/smartdocs-chat --since 10m` shows "Request complete" lines with token counts.

## Results

TODO(result): the four question and answer pairs from [results/33-chat.txt](results/33-chat.txt), and whether question 4 declined.

TODO(result): cold versus warm latency for the first and second request (from the log `duration_ms`).

TODO(result): tokens per question, input and output.

TODO(result): try a different `CHAT_MODEL_ID` (for example Sonnet) on the same questions and note any difference in answer quality or latency.

## Gotchas and lessons

* If the chat returns 502 with `AccessDeniedException`, the model is not callable by the role. Re-run [Phase 1](01-foundation.md) step 5 as admin.
* If the answer says it cannot find the information but the PDF clearly has it, check `top_score` in the logs. Retrieval below `MIN_SCORE` (0.3) is dropped.
* HTTP API lowercases header names, which matters for `x-api-key` in Phase 6.
* TODO(result): anything that broke and how it was fixed.
