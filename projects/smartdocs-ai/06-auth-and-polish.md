# Phase 6: Auth and polish

| | |
| --- | --- |
| **Time budget** | 60 min |
| **Actual time** | ⏳ |
| **Cost** | about $0.40 a month for the secret, prorated |
| **Status** | ⬜ Not started |

## Why this phase exists

Until now anyone with the URL could spend your Bedrock budget. This phase closes that, and replaces "upload with the AWS CLI" with the
pattern real products use: the client gets a short-lived link and uploads straight to S3.

## Steps

### 1. API key in Secrets Manager

The stack generates a random 40-character key, stores it in Secrets Manager and gives the Lambdas only its ARN. They fetch it once per container
and compare in constant time (`hmac.compare_digest`). HTTP APIs have no built-in API keys (that is a REST API feature), so the check lives in the function.
The key is never in an environment variable, in the repository or in this site.

### 2. Presigned uploads

`POST /upload` with `{"filename": "x.pdf"}` returns a URL valid for 5 minutes. The client `PUT`s the file straight to S3, so it never passes through
Lambda or API Gateway (which limit payload sizes). The URL can only write under `docs/`, the file name is sanitized (no paths, no odd characters, always `.pdf`),
and the upload triggers the indexer exactly as before.

### 3. Deploy

```bash
tools/capture.sh smartdocs-ai 60-cdk-deploy bash scripts/40-cdk.sh deploy 6
```

### 4. The whole product, secured, end to end

```bash
tools/capture.sh smartdocs-ai 60-e2e-test bash scripts/60-e2e-test.sh
```

It checks that a request without a key gets **401**, asks for an upload URL, uploads the sample PDF directly to S3, waits for the index, and then runs the
same four question checks as before through the secured API.

### 5. Feel the throttle

```bash
# after loading the key: KEY=$(aws secretsmanager get-secret-value --secret-id <ApiKeySecretArn> --query SecretString --output text)
for i in $(seq 1 40); do curl -s -o /dev/null -w '%{http_code} ' -X POST "<ChatUrl>" \
  -H "x-api-key: $KEY" -H 'Content-Type: application/json' -d '{"question":"hi"}' & done; wait
```

Expect a mix of `200` and `429`: the stage allows 5 requests per second with a burst of 10.

### 6. Finish the documentation

```bash
tools/doc-todos.sh          # lists every TODO(result) still left in the docs
```

Fill each one from `results/`, redact any screenshots, then set the status columns in [the overview](README.md), and set `status: done` in `_data/projects.yml`.

## Verify

* Without `x-api-key`: 401. With a wrong key: 401. With the right key: 200.
* The e2e script ends with "all checks passed".
* The throttle test shows `429` responses.
* `tools/doc-todos.sh` reports no placeholders.

## Results

TODO(result): the e2e output ([results/60-e2e-test.txt](results/60-e2e-test.txt)).

TODO(result): the status codes from the throttle test.

TODO(result): final numbers for the overview: latency p50 and p95, tokens per question, total Bedrock spend for the sitting (Cost Explorer, filter by tag `project`).

## Wrap-up: clean up and next steps

```bash
bash scripts/40-cdk.sh destroy      # stop all costs; the code and docs stay
```

Production upgrades this project points at:

* **Cognito** with JWT authorizers in place of one shared key, for real users and per-user limits.
* **A queue in front of the indexer** (or reserved concurrency of 1) to remove the concurrent-upload race.
* **An approximate or managed vector index** once documents pass roughly 10,000 chunks.
* **OCR** (Textract) for scanned PDFs.
* **Restrict CORS** to the frontend origin, and add a WAF if the API ever goes public for real.
* **Prompt caching** for the system prompt, and **streaming** responses for a faster-feeling chat.

## Gotchas and lessons

* TODO(result): anything that surprised you in the secured flow.
* Secrets Manager charges by the month; if you leave the stack up, the secret keeps costing about $0.40. `destroy` removes it.
