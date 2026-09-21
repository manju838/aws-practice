# Phase 5: Monitoring

| | |
| --- | --- |
| **Time budget** | 45 min |
| **Actual time** | ⏳ |
| **Cost** | about $0 (within the free tier for alarms and one dashboard) |
| **Status** | ⬜ Not started |

## Why this phase exists

A system you cannot see into is a system you cannot fix. This phase answers three questions that matter in production:
is it broken, is it slow, and what did a particular request do.

## Steps

### 1. What the logs already contain

The chat Lambda writes one JSON object per line per request: request id, session, duration, chunks retrieved, top similarity score, model, input and output tokens. The indexer logs each stage (pages, characters, chunks, vectors saved).
That was planned in Phase 3, which is why this phase needs no code changes to the functions.

### 2. Add monitoring to the stack

Set `ALERT_EMAIL` in `config.env`, then:

```bash
bash scripts/40-cdk.sh diff 5         # only the new monitoring resources appear
tools/capture.sh smartdocs-ai 50-cdk-deploy bash scripts/40-cdk.sh deploy 5
```

Confirm the SNS subscription email, or no alarm will ever reach you.

The stack adds four alarms and a dashboard:

| Alarm | Fires when | Why |
| --- | --- | --- |
| Chat errors | 1 or more Lambda errors in 5 minutes | Unhandled exceptions |
| Chat slow p95 | p95 latency at or above 15 s for two periods | The timeout is 30 s; alert well before it |
| Indexer errors | 1 or more errors in 5 minutes | Bad PDFs or Bedrock trouble |
| API 5xx | 1 or more 5xx responses | Includes handled failures such as a model call returning 502 |

Alert on **p95, not the average.** An average hides the slow tail that one request in twenty experiences.

### 3. Make some traffic

```bash
tools/capture.sh smartdocs-ai 50-traffic bash scripts/50-generate-traffic.sh
```

Twelve good questions across three sessions, one bad request, one with a wrong key.

### 4. Look at it

Open CloudWatch, Dashboards, `smartdocs-overview`. Then query the logs from the terminal:

```bash
tools/capture.sh smartdocs-ai 51-insights bash scripts/51-logs-insights.sh
```

It runs three Logs Insights queries: slowest requests, latency and token totals, and errors. Lambda wraps each log line in its own prefix, so the
queries use `parse` to pull fields out of the JSON. (Lambda's JSON log format is a possible upgrade.)

### 5. Make an alarm fire

Handled errors do not count as Lambda errors, so the way to trigger an alarm is a 5xx from API Gateway:

1. Lambda console, the chat function, Configuration, Environment variables: change `CHAT_MODEL_ID` to `nonsense`.
2. Send two chat requests. They return 502 because the model call fails and is handled.
3. Within about five minutes the **API 5xx** alarm goes red and an email arrives.
4. Restore the value (or run `cdk deploy` again, which resets it).

This is also a good moment to notice why the API 5xx alarm exists: the Lambda itself never "failed".

## Verify

* Dashboard graphs show the traffic you generated.
* Insights output shows plausible latency and token counts.
* An alert email arrived after step 5.

## Results

TODO(result): dashboard screenshot with traffic (`assets/dashboard.png`, redacted).

TODO(result): Logs Insights output ([results/51-insights.txt](results/51-insights.txt)): p50 and p95 latency, tokens per request, cold-start outliers.

TODO(result): the alert email and how long after the fault it arrived.

## Gotchas and lessons

* HTTP API metrics are published with the `ApiId` and `Stage` dimensions. If the API graphs are empty while traffic is flowing, check the dimensions in the console first. This was written from the documentation and not yet confirmed against a live account.
* Dashboards and alarms take a minute or two to show data. Metrics for a five-minute period appear at the end of the period.
* TODO(result): anything surprising about cold starts in the latency distribution.
