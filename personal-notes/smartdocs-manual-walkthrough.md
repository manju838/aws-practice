<!-- markdownlint-disable-file -->
# SmartDocs AI by hand: terminal and console walkthrough

The repo around this project is organised so the build can be repeated: numbered scripts, a shared `tools/` library, a config file, captured results, a Jekyll site. That hides what actually happens. This page strips all of it away. It is the same project built the crude way: a few commands in a terminal, and every AWS service clicked together in the console. Each step says what you do, why, and which file in the repo it connects to.

The phase pages (`01-foundation.md` to `06-auth-and-polish.md`) are the polished record. This page is the by-hand path through the same system.

**Assumptions**

* Terminal commands are for **Git Bash** on Windows, run from `projects/smartdocs-ai/`. PowerShell will not run them as written.
* In the console, sign in as your IAM admin user (never root) and set the region selector (top right) to **Asia Pacific (Hyderabad) ap-south-2**. Almost everything in the console is regional. If something you created seems to have vanished, check the region first. IAM is the exception.

## The system you are building

```
 PDF ──► S3 docs/ ──(ObjectCreated)──► indexer Lambda ──► S3 index/ (faiss.index + metadata.json)
                                           uses: layer (faiss, PyMuPDF, numpy) + Titan embeddings (Bedrock)

 question ──► API Gateway ──► chat Lambda ──► 1 embed question (Titan)
                                          ├─► 2 search the index (downloaded from S3, cached in memory)
                                          ├─► 3 DynamoDB: last 10 messages in, new turn out
                                          └─► 4 Claude on Bedrock (Converse API) ──► answer

 Both Lambdas run as one IAM role. CloudWatch collects their logs.
```

## Repo scaffolding you can ignore

None of this is AWS. It exists to keep the project tidy and repeatable. Here is what each piece did for you and what replaces it by hand.

| Repo thing | What it did for you | By hand |
| --- | --- | --- |
| `config.env.example`, copied to `config.env` | A local, git-ignored file holding region, resource names and model IDs, so names are never typed twice and never pushed to GitHub | Type the names into the console, and `export` a few variables once (Step 2) |
| `tools/lib/common.sh` (`load_project_config`) | Loads `config.env`, asks AWS for your account ID, `cd`s into the project, creates `build/` | `aws sts get-caller-identity` and `mkdir build` |
| `tools/lib/lambda.sh` (`deploy_lambda`) | Zip a folder, create the Lambda or update it, wait for updates, retry while a new IAM role propagates | Zip the folder, upload it in the Lambda console |
| `tools/capture.sh` | Runs a command and saves a redacted copy of the output to `results/` for the website | Nothing, skip it |
| `results/`, `assets/`, `docs/`, `_config.yml`, `_layouts/`, `_includes/`, `index.md`, `Gemfile` | The GitHub Pages site and its documentation | Nothing, no AWS involved |
| `scripts/NN-*.sh` | One script per job, written as CLI calls | Each one is a step below, done in the console |
| `build/` | Scratch folder for zips and generated JSON (git-ignored) | You create it (Step 2) |
| `pyproject.toml`, `uv.lock` | Python dependency list. uv builds the environment and the Lambda layer from it | Steps 3 and 7 |
| `tests/` | Unit tests using fake S3, Bedrock and DynamoDB, so they need no AWS | Step 3 |
| `src/` | The three Lambda functions. This is the actual product | Steps 8, 12 and 20 |
| `infra/` | The same system written as CDK code | Part 6 |

## Overview

| Part | Steps | Layers you touch | Repo code |
| --- | --- | --- | --- |
| 1. Foundation | 1 to 4 | CLI credentials, Python env, Bedrock access | `scripts/10-check-bedrock.sh` |
| 2. Index a PDF | 5 to 10 | S3, IAM, Lambda layer, Lambda, event triggers | `src/indexer/`, `scripts/20` to `25` |
| 3. Ask questions | 11 to 14 | DynamoDB, Lambda, API Gateway, Bedrock Converse | `src/chat/`, `scripts/30` to `33` |
| 4. Observe | 15 to 17 | CloudWatch Logs, Logs Insights, SNS, alarms, dashboard | `scripts/50`, `51` |
| 5. Secure | 18 to 21 | Secrets Manager, presigned URLs, throttling | `src/upload/`, `src/*/auth.py`, `scripts/60` |
| 6. Same thing as code | 22 to 26 | CloudFormation via CDK | `infra/`, `scripts/40` |

---

# Part 1: Foundation

## Step 1. Install the tools (terminal)

```bash
aws --version        # needs v2
uv --version         # Python environment manager
node --version
npm install -g aws-cdk && cdk --version      # only needed for Part 6
```

Why uv: it installs Python, creates the environment from `pyproject.toml`, and later downloads Linux builds of the Lambda libraries without Docker.

## Step 2. Point the terminal at your account (terminal)

One-time credentials setup if you have not done it (see the AWS General Notes page for what a profile is):

```bash
aws configure --profile personal       # region ap-south-2, output json
```

Then, in **every new terminal**:

```bash
cd projects/smartdocs-ai
export AWS_PROFILE=personal
export AWS_REGION=ap-south-2
export AWS_DEFAULT_REGION=ap-south-2
export MSYS_NO_PATHCONV=1      # Git Bash only: stops it rewriting /aws/lambda/... into a Windows path
export ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
export BUCKET=smartdocs-$ACCOUNT_ID
mkdir -p build                 # scratch folder for zips and JSON, git-ignored

# Git Bash has no `zip` command, so let Python zip a folder's CONTENTS (what Lambda wants)
zipdir() { uv run python -c "import shutil,sys; shutil.make_archive(sys.argv[2][:-4], 'zip', sys.argv[1])" "$1" "$2"; }

aws sts get-caller-identity    # should show your IAM user, not root
```

These variables disappear when the terminal closes. That is the entire job `config.env` and `load_project_config` did for every script.

Repo: [config.env.example](../projects/smartdocs-ai/config.env.example) lists the names and model IDs used everywhere below.

## Step 3. Python environment and tests (terminal)

```bash
uv sync               # creates .venv: boto3, faiss, PyMuPDF, pytest, CDK libraries
uv run pytest         # all green, no AWS credentials needed
```

The tests call the Lambda code with fake S3, Bedrock and DynamoDB objects, so chunking, FAISS search, prompt building and the handlers are checked before anything is deployed. Nothing is created in AWS.

Repo: [tests/](../projects/smartdocs-ai/tests/), fakes in [tests/fakes.py](../projects/smartdocs-ai/tests/fakes.py).

## Step 4. Check which Bedrock models you can call (terminal)

Bedrock hosts the models. Two are used: Claude to write answers, Titan to turn text into vectors. Before building anything, prove your account can call both. Do this with your **admin** credentials: the first call to a third-party model is what creates its AWS Marketplace subscription, and the Lambda role deliberately has no Marketplace permissions, so the Lambda could never do it.

```bash
# 1. Which Claude models are visible in this region?
aws bedrock list-inference-profiles \
  --query "inferenceProfileSummaries[?contains(inferenceProfileId,'anthropic')].inferenceProfileId" --output table

# 2. Can you actually call the one we want? (the Converse API is what the chat Lambda uses)
aws bedrock-runtime converse \
  --model-id global.anthropic.claude-haiku-4-5-20251001-v1:0 \
  --messages '[{"role":"user","content":[{"text":"Reply with the single word: ready"}]}]' \
  --inference-config '{"maxTokens":20}' \
  --query 'output.message.content[?text].text | [0]' --output text

# 3. The embedding model: expect 1024 numbers back
aws bedrock-runtime invoke-model --model-id amazon.titan-embed-text-v2:0 \
  --body '{"inputText":"hello world"}' --cli-binary-format raw-in-base64-out build/embed-response.json
uv run python -c "import json; print(len(json.load(open('build/embed-response.json'))['embedding']))"
```

Expected: the list contains the Haiku profile, call 2 prints `ready`, call 3 prints `1024`.

* The model ID starts with `global.` because it is an **inference profile**: Bedrock routes the request to whichever region has capacity. That ID becomes `CHAT_MODEL_ID` in Step 12. Any ID from the list works if your account can call it.
* Console alternative: Amazon Bedrock, Playgrounds, Chat, pick the model, say hi.
* If you get `INVALID_PAYMENT_INSTRUMENT`, see the payment notes in [Phase 1](../projects/smartdocs-ai/01-foundation.md) step 5. A failed Marketplace subscription stays stuck until it is fixed on the billing side.
* If the JSON quoting misbehaves in your shell, put the JSON in a file and pass `file://build/x.json`, which is what the repo script does.

Repo: [scripts/10-check-bedrock.sh](../projects/smartdocs-ai/scripts/10-check-bedrock.sh) does exactly this, but loops over every model in `CANDIDATE_MODELS`.

---

# Part 2: Index a PDF

Goal: drop a PDF into S3 and have a Lambda turn it into a searchable index, with no server running.

## Step 5. Create the S3 bucket (console)

S3, Create bucket:

* Bucket name: `smartdocs-<your 12-digit account ID>` (bucket names are global, the account ID makes it unique)
* Region: ap-south-2
* Block all public access: leave **on**
* Bucket versioning: **Enable**
* Tags: `project` = `smartdocs`
* Create bucket

No folders are needed. S3 only has keys, so `docs/` and `index/` exist as soon as an object with that prefix does. The indexer reads PDFs from `docs/` and writes `index/faiss.index` and `index/metadata.json`.

Versioning is why deleting this bucket later requires emptying every version first.

Repo: [scripts/20-create-bucket.sh](../projects/smartdocs-ai/scripts/20-create-bucket.sh). The key names are `INDEX_KEY` and `META_KEY` in [src/indexer/lambda_function.py](../projects/smartdocs-ai/src/indexer/lambda_function.py).

## Step 6. Create the Lambda execution role (console)

A Lambda never holds credentials. It **assumes a role** and AWS hands it temporary ones. The role decides what the function may touch.

IAM, Roles, Create role:

1. Trusted entity type: **AWS service**, use case **Lambda**, Next. This writes the trust policy that lets `lambda.amazonaws.com` assume the role.
2. Add permission: `AWSLambdaBasicExecutionRole` (lets the function write logs to CloudWatch). Next.
3. Role name: `smartdocs-lambda-role`. Create role.
4. Open the role, Permissions tab, Add permissions, **Create inline policy**, JSON tab. Paste this, replacing `<BUCKET>` and `<ACCOUNT_ID>`, name it `smartdocs-least-privilege`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Sid": "ReadWriteOurBucket", "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::<BUCKET>/*" },
    { "Sid": "ListOurBucket", "Effect": "Allow",
      "Action": "s3:ListBucket",
      "Resource": "arn:aws:s3:::<BUCKET>" },
    { "Sid": "ConversationHistory", "Effect": "Allow",
      "Action": ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query"],
      "Resource": "arn:aws:dynamodb:ap-south-2:<ACCOUNT_ID>:table/smartdocs-conversations" },
    { "Sid": "InvokeModels", "Effect": "Allow",
      "Action": ["bedrock:InvokeModel"],
      "Resource": ["arn:aws:bedrock:*::foundation-model/*",
                   "arn:aws:bedrock:*:<ACCOUNT_ID>:inference-profile/*"] }
  ]
}
```

What each statement is for:

| Statement | Used by | Why |
| --- | --- | --- |
| `s3:GetObject`, `s3:PutObject` on `<BUCKET>/*` | Indexer reads PDFs and writes the index. Chat reads the index | The files |
| `s3:ListBucket` on the bucket itself | Chat, before an index exists | Without it a missing object returns 403 instead of 404, and the code only handles 404 |
| Three DynamoDB actions on one table | Chat | History in, new turn out. The table does not have to exist yet |
| `bedrock:InvokeModel` | Both | Covers Titan embeddings and, through inference profiles, Claude. The Converse API is authorised by this same action |

There is no `*FullAccess` policy anywhere. The table name here must match Step 11.

Repo: [scripts/21-create-iam-role.sh](../projects/smartdocs-ai/scripts/21-create-iam-role.sh).

## Step 7. Build and publish the layer (terminal, then console)

FAISS, PyMuPDF and numpy contain compiled code, and Lambda runs Linux. Libraries built on your Windows laptop would crash there, and together they are too big to zip into the function. A **layer** is a separate zip of libraries that Lambda mounts at `/opt/python` for any function that attaches it. It is versioned and immutable.

Terminal, build the Linux packages and zip them:

```bash
rm -rf layer && mkdir -p layer/build/python
uv pip install --group layer --target layer/build/python \
  --python-platform x86_64-manylinux_2_28 --python-version 3.12 --only-binary :all: --no-cache

# slim it down: Lambda allows 250 MB unzipped, function code included
find layer/build/python -name "__pycache__" -type d -prune -exec rm -rf {} +
find layer/build/python -path "*/tests" -type d -prune -exec rm -rf {} +
find layer/build/python -name "*.pyi" -delete
rm -rf layer/build/python/bin
du -sm layer/build/python           # must stay well under 250

zipdir layer/build build/faiss-layer.zip      # about 60 MB, over the 50 MB browser upload limit
aws s3 cp build/faiss-layer.zip s3://$BUCKET/layers/faiss-layer.zip
```

* `--python-platform x86_64-manylinux_2_28` makes uv download the Linux wheels directly. That is why no Docker is needed.
* The zip must have a top-level `python/` folder, which is how Lambda knows where the libraries are. `zipdir layer/build` gives you that.
* Over 50 MB means the console cannot take it as a direct upload, so it goes through S3.

Console, Lambda, Layers, Create layer:

* Name: `smartdocs-faiss`
* Upload a file from Amazon S3: paste the **Object URL** of `layers/faiss-layer.zip` (S3 console, click the object, copy Object URL)
* Compatible architectures: x86_64. Compatible runtimes: Python 3.12
* Create

Check: Lambda, Layers shows `smartdocs-faiss` version 1.

Repo: [scripts/22-build-layer.sh](../projects/smartdocs-ai/scripts/22-build-layer.sh). The package list is the `layer` group in [pyproject.toml](../projects/smartdocs-ai/pyproject.toml). `boto3` is not in it because Lambda provides boto3.

## Step 8. Create the indexer Lambda (terminal, then console)

Read [src/indexer/lambda_function.py](../projects/smartdocs-ai/src/indexer/lambda_function.py) first. It is short. In order: decode the S3 key, download the PDF, extract text with PyMuPDF, split into chunks (`chunker.py`), embed each chunk with Titan, remove any earlier chunks from the same file (`indexing.py`), add the new vectors, save metadata then index.

Why chunks: a model and an embedding work on limited text, and a whole book embeds into mush. The code uses 300-word chunks with a 50-word overlap so a sentence at a boundary is never cut away from its context.

Terminal, zip the code (the three files must sit at the zip root):

```bash
find src -name "__pycache__" -type d -prune -exec rm -rf {} +      # tests leave these behind
zipdir src/indexer build/smartdocs-indexer.zip
```

Console, Lambda, Create function, Author from scratch:

* Function name: `smartdocs-indexer`
* Runtime: Python 3.12. Architecture: x86_64
* Change default execution role, Use an existing role: `smartdocs-lambda-role`
* Create function

Then on the function page:

1. **Code** tab, Upload from, .zip file, pick `build/smartdocs-indexer.zip`.
2. Code tab, Runtime settings, Edit: handler `lambda_function.lambda_handler` (file name, dot, function name).
3. Scroll to **Layers**, Add a layer, Custom layers, `smartdocs-faiss`, version 1, Add.
4. **Configuration**, General configuration, Edit: Memory **1024 MB**, Timeout **5 min 0 sec**. PDF parsing plus one Titan call per chunk is slow and memory hungry.
5. Configuration, Environment variables, Edit:

| Key | Value |
| --- | --- |
| `DOCS_BUCKET` | your bucket name |
| `EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` |

`DOCS_BUCKET` is read with `os.environ["DOCS_BUCKET"]` at import time, so a missing value fails the function before it starts. That is how config reaches Lambda code: through environment variables.

Repo: [scripts/23-deploy-indexer.sh](../projects/smartdocs-ai/scripts/23-deploy-indexer.sh), with the create-or-update logic in `tools/lib/lambda.sh`.

## Step 9. Connect S3 to the indexer (console)

S3 and Lambda do not know each other. Two things must exist: a **permission** letting S3 invoke the function, and a **notification rule** saying when.

Lambda, `smartdocs-indexer`, Add trigger:

* Source: **S3**
* Bucket: your bucket
* Event types: **All object create events**
* Prefix: `docs/`
* Suffix: `.pdf`
* Tick the recursive invocation acknowledgement, then Add

The console just created both halves. See them:

* Lambda, Configuration, Permissions, Resource-based policy statements: an entry for `s3.amazonaws.com`, scoped to your bucket.
* S3, your bucket, Properties, Event notifications: the rule with the prefix and suffix.

Why the prefix matters: the indexer writes its output into the same bucket under `index/`. A trigger on the whole bucket would fire on its own output forever and run up a bill. `docs/` plus `.pdf` means only uploaded PDFs trigger indexing. The handler also skips any key not starting with `docs/` as a second guard.

Repo: [scripts/24-attach-s3-trigger.sh](../projects/smartdocs-ai/scripts/24-attach-s3-trigger.sh) does the two halves as two CLI calls (`aws lambda add-permission` and `aws s3api put-bucket-notification-configuration`).

## Step 10. Upload a PDF and watch it get indexed (terminal)

The sample is a two-page manual for a **fictional** kettle. Every fact is invented (87.5 degrees, 26 month warranty, founded in Lisbon), so a correct answer in Part 3 can only come from retrieval, never from Claude's memory.

```bash
uv run python tests/make_sample_pdf.py build/nimbus-kettle-manual.pdf
aws s3 cp build/nimbus-kettle-manual.pdf s3://$BUCKET/docs/nimbus-kettle-manual.pdf

aws logs tail /aws/lambda/smartdocs-indexer --since 10m --format short --follow     # Ctrl+C when done
aws s3 ls s3://$BUCKET/index/
```

Expected log lines, in order: `Starting indexing`, `Text extracted` (pages 2), `Chunked` (num_chunks 2), `Created new index`, `Index saved` (total_vectors 2). Then `faiss.index` and `metadata.json` are in `index/`.

Run the upload a second time. The log now says `Loaded existing index` and ends with `total_vectors` still 2: re-uploading replaces, it does not duplicate (`remove_source` in `indexing.py`).

* Console alternative for the logs: Lambda, `smartdocs-indexer`, Monitor, View CloudWatch logs. For the upload: S3, `docs/`, Upload.
* No log group at all means the Lambda never ran: re-check the trigger prefix and suffix, and that the file really is under `docs/` and ends in `.pdf`.
* Optional shortcut that skips S3 events: in the Lambda Test tab, run this event (the PDF must already be in `docs/`). It shows how little of the S3 event the handler actually reads.

```json
{ "Records": [ { "s3": { "object": { "key": "docs/nimbus-kettle-manual.pdf" } } } ] }
```

Repo: [scripts/25-test-pipeline.sh](../projects/smartdocs-ai/scripts/25-test-pipeline.sh), sample generator [tests/make_sample_pdf.py](../projects/smartdocs-ai/tests/make_sample_pdf.py).

---

# Part 3: Ask questions

Goal: put a public HTTPS address in front of a Lambda that retrieves passages, remembers the conversation, and asks Claude.

## Step 11. Create the DynamoDB table (console)

Lambda forgets everything between calls, so conversation memory has to live somewhere.

DynamoDB, Create table:

* Table name: `smartdocs-conversations`
* Partition key: `session_id` (String)
* Sort key: `timestamp` (Number)
* Table settings: Customize settings, Capacity mode **On-demand** (no minimum cost)
* Tags: `project` = `smartdocs`
* Create table

Then turn on TTL: open the table, Settings (Additional settings) tab, Time to Live (TTL), Turn on, attribute name `ttl`.

* `session_id` says which conversation. `timestamp` (milliseconds) orders it. One query for a `session_id` returns the whole conversation in order.
* `ttl` is an epoch-seconds value the code writes on each item (7 days ahead). DynamoDB deletes expired items for free.

Repo: [scripts/30-create-table.sh](../projects/smartdocs-ai/scripts/30-create-table.sh). The reads and writes are `load_history` and `save_turn` in [src/chat/lambda_function.py](../projects/smartdocs-ai/src/chat/lambda_function.py).

## Step 12. Create the chat Lambda (terminal, then console)

Read [src/chat/lambda_function.py](../projects/smartdocs-ai/src/chat/lambda_function.py). It does six things: retrieve (`retriever.py`), load history, build the prompt (`prompting.py`), call Claude with `converse`, save the turn, return. Choices worth noticing:

* The retrieval query includes the previous user question, because "What problem does it solve?" means nothing to a vector search on its own.
* The system prompt tells Claude the excerpts are untrusted text, not instructions.
* If nothing relevant is found, Claude is still called and told there are no excerpts, so it can say so.
* A failed model call returns 502 and saves nothing, so a failed turn does not poison the history.
* Every request logs one JSON line with duration, chunks, top score and token counts. Step 15 uses it.

Terminal:

```bash
find src -name "__pycache__" -type d -prune -exec rm -rf {} +
zipdir src/chat build/smartdocs-chat.zip
```

Console, Lambda, Create function, same as Step 8 but:

* Function name: `smartdocs-chat`, existing role `smartdocs-lambda-role`
* Upload `build/smartdocs-chat.zip`, handler `lambda_function.lambda_handler`
* Add the same layer `smartdocs-faiss`
* Memory **512 MB**, timeout **30 sec**
* Environment variables:

| Key | Value |
| --- | --- |
| `DOCS_BUCKET` | your bucket name |
| `CONVERSATIONS_TABLE` | `smartdocs-conversations` |
| `CHAT_MODEL_ID` | `global.anthropic.claude-haiku-4-5-20251001-v1:0` (or any ID that worked in Step 4) |
| `EMBED_MODEL_ID` | `amazon.titan-embed-text-v2:0` |
| `TEMPERATURE` | `0.2` (leave this key out if a newer model rejects the parameter) |

Test it **before** any API exists. A Lambda only ever sees an event JSON, and API Gateway just builds that JSON for it. In the Test tab, create an event:

```json
{ "body": "{\"question\": \"How hot does the NK-4471 kettle get, and how fast?\", \"session_id\": \"console-test\"}" }
```

Expected: `statusCode` 200 and an answer containing `87.5`. The body is a string inside the JSON because that is how API Gateway delivers it.

Check: DynamoDB, the table, Explore table items. Two items for `console-test`, one `user` and one `assistant`, each with a `ttl`.

Repo: [scripts/31-deploy-chat.sh](../projects/smartdocs-ai/scripts/31-deploy-chat.sh).

## Step 13. Create the HTTP API (console)

API Gateway, Create API, **HTTP API**, Build. (HTTP API is cheaper and faster than REST API for Lambda backends. REST wins only for request transformation or usage plans.)

1. Integrations: Add integration, Lambda, region ap-south-2, function `smartdocs-chat`. API name: `smartdocs-api`. Next.
2. Routes: method `POST`, resource path `/chat`, integration target `smartdocs-chat`. Next.
3. Stages: stage name `prod` (not `$default`, the URL then contains `/prod`), auto-deploy on. Next, then Create.
4. **CORS** (left menu), Configure: allow origins `*`, allow methods `POST` and `OPTIONS`, allow headers `content-type` and `x-api-key`, Save. Fine while there is no frontend.
5. **Throttling**: Stages, `prod`, Default route throttling, Edit: rate **5**, burst **10**. This endpoint is public and every request costs money, so cap it from the start.

Copy the **Invoke URL** from the stage page. Your chat URL is that plus `/chat`: `https://<api-id>.execute-api.ap-south-2.amazonaws.com/prod/chat`. Do not paste it into anything committed to git.

What the console did for you: it created the Lambda **proxy integration** (payload format 2.0, which is what lowercases header names) and added a resource policy letting `apigateway.amazonaws.com` invoke the function. Check Lambda, `smartdocs-chat`, Configuration, Permissions.

Repo: [scripts/32-create-api.sh](../projects/smartdocs-ai/scripts/32-create-api.sh) does this in five CLI calls: create-api, create-integration, create-route, create-stage, add-permission.

## Step 14. Ask questions (terminal)

```bash
URL="https://<api-id>.execute-api.ap-south-2.amazonaws.com/prod/chat"
SESSION=demo-$(date +%s)
ask() { curl -s -X POST "$URL" -H 'Content-Type: application/json' -d "{\"question\": \"$1\", \"session_id\": \"$SESSION\"}"; echo; }

ask "How hot does the NK-4471 kettle get, and how fast?"
ask "How long is its warranty?"
ask "In which city was the company founded?"
ask "What is the capital of Australia?"
```

What each answer proves:

| Question | Expect | Proves |
| --- | --- | --- |
| Temperature and time | `87.5` | Retrieval works. Claude cannot know a fictional kettle |
| "How long is its warranty?" | `26` months | History works. "its" is meaningless without the previous turn |
| Where was the company founded | `Lisbon` | A different passage is retrieved |
| Capital of Australia | Declines | The prompt forces answers from the excerpts only |

If a correct answer says "I could not find that", look at `top_score` in the logs (Step 15). Retrieval below `MIN_SCORE` (0.3) is dropped.

Repo: [scripts/33-test-chat.sh](../projects/smartdocs-ai/scripts/33-test-chat.sh) is this plus automatic checks.

---

# Part 4: Observe

Goal: answer three questions in production. Is it broken, is it slow, and what did one request do?

## Step 15. Read the logs and run Logs Insights (console)

Nothing in the code changes for this. The chat Lambda already prints one JSON line per request.

CloudWatch, Log groups, `/aws/lambda/smartdocs-chat`, latest log stream. Find a line containing `Request complete` with `duration_ms`, `chunks`, `top_score`, `input_tokens`, `output_tokens`.

Then CloudWatch, Logs Insights, select that log group, time range 1 hour. Lambda puts its own prefix in front of each line, so the queries use `parse` to pull fields out of the JSON.

```
filter @message like /Request complete/
| parse @message /"duration_ms": (?<duration_ms>[0-9]+)/
| parse @message /"session_id": "(?<session>[^"]*)"/
| parse @message /"chunks": (?<chunks>[0-9]+)/
| sort duration_ms desc | limit 5 | fields @timestamp, session, duration_ms, chunks
```

```
filter @message like /Request complete/
| parse @message /"duration_ms": (?<d>[0-9]+)/
| parse @message /"input_tokens": (?<tin>[0-9]+)/
| parse @message /"output_tokens": (?<tout>[0-9]+)/
| stats count() as requests, avg(d) as avg_ms, pct(d, 95) as p95_ms, sum(tin) as input_tokens, sum(tout) as output_tokens
```

Make some traffic first by running the `ask` function from Step 14 a dozen times. The first request after idle is slower than the rest: that is a **cold start**.

Repo: [scripts/51-logs-insights.sh](../projects/smartdocs-ai/scripts/51-logs-insights.sh), traffic generator [scripts/50-generate-traffic.sh](../projects/smartdocs-ai/scripts/50-generate-traffic.sh).

## Step 16. Alarms (console)

First, somewhere for alerts to go. SNS, Topics, Create topic, Standard, name `smartdocs-alerts`. Then Create subscription: protocol Email, your address. **Open the email and confirm it**, or no alarm will ever reach you.

Then CloudWatch, Alarms, Create alarm, Select metric. Four alarms:

| Alarm name | Metric | Statistic, period | Condition |
| --- | --- | --- | --- |
| `smartdocs-chat-errors` | Lambda, By Function Name, `smartdocs-chat`, Errors | Sum, 5 min | greater or equal 1, 1 of 1 |
| `smartdocs-chat-slow-p95` | Lambda, `smartdocs-chat`, Duration | **p95**, 5 min | greater or equal 15000, 2 of 2 |
| `smartdocs-indexer-errors` | Lambda, `smartdocs-indexer`, Errors | Sum, 5 min | greater or equal 1, 1 of 1 |
| `smartdocs-api-5xx` | ApiGateway, dimensions `ApiId` and `Stage` (`prod`), `5xx` | Sum, 5 min | greater or equal 1, 1 of 1 |

On every alarm: set "Treat missing data" to **Not breaching** (no traffic is not an outage), and under notification pick `smartdocs-alerts`.

* Alert on p95, not the average. An average hides the slow tail that one request in twenty experiences. The 15 s threshold sits well below the 30 s timeout.
* Handled errors do not count as Lambda errors. A model failure returns 502 from a perfectly healthy function, which is why the API 5xx alarm exists.

Make an alarm fire: on `smartdocs-chat`, Configuration, Environment variables, change `CHAT_MODEL_ID` to `nonsense`. Send two chat requests (each returns 502). Within about five minutes the 5xx alarm goes red and an email arrives. Restore the value afterwards.

## Step 17. Dashboard (console)

CloudWatch, Dashboards, Create dashboard, name `smartdocs-overview`. Add widgets:

* Line: `smartdocs-chat` Invocations and Errors
* Line: `smartdocs-chat` Duration with three series, statistics p50, p95, p99
* Line: ApiGateway `Count`, `4xx`, `5xx` for your API and stage
* Line: `smartdocs-indexer` Invocations and Errors
* Logs table: log group `smartdocs-chat`, the "slowest requests" query from Step 15

Metrics for a five-minute period appear at the end of the period, so a fresh dashboard looks empty for a few minutes.

Repo: all of Steps 16 and 17 exist only as code, in `_observability()` in [infra/smartdocs_stack.py](../projects/smartdocs-ai/infra/smartdocs_stack.py).

---

# Part 5: Secure it

Goal: until now, anyone with the URL can spend your Bedrock budget. Close that, and replace "upload with the AWS CLI" with how real products upload.

## Step 18. Store an API key (terminal, then console)

Generate a random 40 character key:

```bash
uv run python -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(40)))"
```

Secrets Manager, Store a new secret:

* Secret type: **Other type of secret**, then the **Plaintext** tab (not Key/value), paste the key
* Secret name: `smartdocs/api-key`
* Skip rotation. Store

Plaintext matters: the code compares the raw `SecretString` to the request header. Key/value stores it as JSON and every request would get 401.

Copy the secret's ARN. It ends with a random suffix like `-AbCdEf`.

Cost: about $0.40 a month while it exists.

## Step 19. Turn on the key check (console)

Both Lambdas already contain `auth.py`. It checks the `x-api-key` header **only if** the environment variable `API_KEY_SECRET_ARN` exists, which is why Parts 2 and 3 ran open. HTTP APIs have no built-in API keys (that is a REST API feature), so the check lives in the function. It fetches the key once per container and compares in constant time with `hmac.compare_digest`.

1. IAM, `smartdocs-lambda-role`, edit the inline policy `smartdocs-least-privilege`, add a statement:

```json
{ "Sid": "ReadApiKey", "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": "arn:aws:secretsmanager:ap-south-2:<ACCOUNT_ID>:secret:smartdocs/api-key-*" }
```

The trailing `-*` is needed because of the random suffix on the ARN.

2. Lambda, `smartdocs-chat`, Configuration, Environment variables: add `API_KEY_SECRET_ARN` = the secret's full ARN. The key itself is never in an environment variable.

Repo: [src/chat/auth.py](../projects/smartdocs-ai/src/chat/auth.py), identical copy in [src/upload/auth.py](../projects/smartdocs-ai/src/upload/auth.py) (a test enforces that).

## Step 20. Add the upload Lambda and route (terminal, then console)

Pushing a PDF through API Gateway and Lambda hits their payload size limits. Instead the client asks for a **presigned URL**: a short-lived S3 link that allows exactly one upload. The file then goes straight to S3 and triggers the indexer exactly as before.

Read [src/upload/lambda_function.py](../projects/smartdocs-ai/src/upload/lambda_function.py): it checks the key, sanitises the file name (no paths, no odd characters, always `.pdf`), and returns a URL valid for 5 minutes that can only write under `docs/`.

Terminal:

```bash
find src -name "__pycache__" -type d -prune -exec rm -rf {} +
zipdir src/upload build/smartdocs-upload.zip
```

Console, Lambda, Create function: name `smartdocs-upload`, Python 3.12, existing role `smartdocs-lambda-role`, upload the zip, handler `lambda_function.lambda_handler`. **No layer needed**, it only uses boto3. Memory 256 MB, timeout 10 sec. Environment variables:

| Key | Value |
| --- | --- |
| `DOCS_BUCKET` | your bucket name |
| `API_KEY_SECRET_ARN` | the secret's ARN |

Then API Gateway, `smartdocs-api`, Routes, Create: `POST /upload`, attach a new Lambda integration for `smartdocs-upload`. Confirm the console added the invoke permission (Lambda, Configuration, Permissions). If the route returns `Internal Server Error` and the Lambda shows no logs, that permission is missing.

The presigned URL is signed with the Lambda role's temporary credentials, so the role must itself have `s3:PutObject`. It already does (Step 6).

## Step 21. Test the secured system (terminal)

```bash
KEY=$(aws secretsmanager get-secret-value --secret-id smartdocs/api-key --query SecretString --output text)
CHAT_URL="https://<api-id>.execute-api.ap-south-2.amazonaws.com/prod/chat"
UPLOAD_URL="https://<api-id>.execute-api.ap-south-2.amazonaws.com/prod/upload"

# 1. no key, wrong key, right key
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$CHAT_URL" -H 'Content-Type: application/json' -d '{"question":"hi"}'
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$CHAT_URL" -H 'x-api-key: nope' -H 'Content-Type: application/json' -d '{"question":"hi"}'
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$CHAT_URL" -H "x-api-key: $KEY" -H 'Content-Type: application/json' -d '{"question":"hi"}'

# 2. ask for an upload URL, then PUT the PDF straight to S3
curl -s -X POST "$UPLOAD_URL" -H "x-api-key: $KEY" -H 'Content-Type: application/json' -d '{"filename":"nimbus-kettle-manual.pdf"}'
# copy the upload_url value from that JSON, then:
curl -s -o /dev/null -w '%{http_code}\n' -X PUT "<upload_url>" -H 'Content-Type: application/pdf' --data-binary @build/nimbus-kettle-manual.pdf

# 3. feel the throttle: expect a mix of 200 and 429 (rate 5/s, burst 10)
for i in $(seq 1 40); do curl -s -o /dev/null -w '%{http_code} ' -X POST "$CHAT_URL" \
  -H "x-api-key: $KEY" -H 'Content-Type: application/json' -d '{"question":"hi"}' & done; wait
```

Expected: `401`, `401`, `200`. Then `200` from S3, followed by the indexer log lines from Step 10. Then a mix of `200` and `429`.

* The upload `PUT` must send `Content-Type: application/pdf`. The URL was signed with that header, and any other value gives `SignatureDoesNotMatch`.
* Re-run the four questions from Step 14, this time adding `-H "x-api-key: $KEY"`.

Repo: [scripts/60-e2e-test.sh](../projects/smartdocs-ai/scripts/60-e2e-test.sh) does this whole sequence.

---

# Part 6: The same thing as code (CDK)

Everything above was dozens of console visits in a specific order. If the account were wiped, rebuilding would mean remembering all of it. **CDK** turns the system into Python in git: `cdk synth` compiles it to a CloudFormation template, `cdk deploy` creates the resources, `cdk destroy` removes them.

What you clicked, and the line of CDK that replaces it ([infra/smartdocs_stack.py](../projects/smartdocs-ai/infra/smartdocs_stack.py)):

| Console | CDK |
| --- | --- |
| S3 bucket (Step 5) | `s3.Bucket(..., versioned=True, enforce_ssl=True, block_public_access=BLOCK_ALL)` |
| IAM role and inline policy (Step 6) | `bucket.grant_read(chat)`, `table.grant_read_write_data(chat)`, `add_to_role_policy(...)`. CDK writes the policy, with one generated role per function |
| Layer (Step 7) | `_lambda.LayerVersion(code=Code.from_asset(layer_dir))` |
| Lambdas (Steps 8, 12, 20) | `_lambda.Function(..., memory_size, timeout, layers, environment)` |
| S3 trigger (Step 9) | `bucket.add_event_notification(..., prefix="docs/", suffix=".pdf")` |
| DynamoDB (Step 11) | `dynamodb.Table(..., time_to_live_attribute="ttl")` |
| HTTP API (Step 13) | `HttpApi`, `HttpStage(throttle=...)`, `add_routes(...)` |
| SNS, alarms, dashboard (Steps 16 and 17) | `_observability()` |
| Secret (Step 18) | `secretsmanager.Secret(generate_secret_string=...)` |

## Step 22. Delete the hand-built version (console and terminal)

Not strictly required, because CDK generates its own resource names, but it proves the stack can rebuild everything alone. Delete in this order:

1. API Gateway: delete `smartdocs-api`.
2. Lambda: delete `smartdocs-indexer`, `smartdocs-chat`, `smartdocs-upload`. Lambda, Layers: delete every version of `smartdocs-faiss`.
3. DynamoDB: delete `smartdocs-conversations`.
4. S3: select your bucket, **Empty** (this removes all versions), then **Delete**.
5. IAM: delete `smartdocs-lambda-role`.
6. CloudWatch, Log groups: delete the three `/aws/lambda/smartdocs-*` groups. Lambda does not delete these itself.
7. Secrets Manager, from the terminal, to remove it immediately rather than after a waiting period:

```bash
aws secretsmanager delete-secret --secret-id smartdocs/api-key --force-delete-without-recovery
```

8. SNS and CloudWatch: delete the topic and the four alarms, and the dashboard.

Check for leftovers:

```bash
aws s3 ls | grep smartdocs
aws lambda list-functions --query "Functions[?starts_with(FunctionName,'smartdocs')].FunctionName"
aws dynamodb list-tables
aws apigatewayv2 get-apis --query "Items[].Name"
```

Repo: [scripts/90-teardown-manual.sh](../projects/smartdocs-ai/scripts/90-teardown-manual.sh) covers steps 1 to 6 for the resources the repo's own scripts create (API, indexer and chat Lambdas, layer, table, bucket, role), with a confirmation prompt. It knows nothing about the upload Lambda, the secret, or the Part 4 and 5 resources, because those exist in the repo only as CDK code. Delete those by hand as listed.

## Step 23. Bootstrap CDK, once per account and region (terminal)

```bash
cdk bootstrap aws://$ACCOUNT_ID/ap-south-2
```

This creates a `CDKToolkit` stack, a staging bucket and a few roles, which CDK uses to upload the Lambda zips and the layer. Look at it in the CloudFormation console. It lives outside your stack and is only needed once.

## Step 24. Synthesize, diff, deploy (terminal)

CDK packages `layer/build` as the layer, so Step 7 must have been run on this machine.

```bash
cd infra
export CDK_DEFAULT_ACCOUNT=$ACCOUNT_ID CDK_DEFAULT_REGION=ap-south-2
CTX="-c phase=4 -c project=smartdocs -c chat_model=global.anthropic.claude-haiku-4-5-20251001-v1:0 -c embed_model=amazon.titan-embed-text-v2:0"

cdk synth $CTX --quiet       # compile Python to a CloudFormation template, deploys nothing
cdk diff $CTX                # on the first run everything shows as new
cdk deploy $CTX --outputs-file ../build/cdk-outputs.json
```

* `diff` is how you review IAM and resource changes before applying them. Companies run it before every production deploy.
* `deploy` asks you to approve the IAM changes. When it ends, the outputs (`ChatUrl`, `BucketName`, `ChatLogGroup`) are printed and saved to `build/cdk-outputs.json`.
* `-c phase=` selects how much of the stack to build. 4 is storage, Lambdas and API. 5 adds SNS, alarms and the dashboard. 6 adds the API key, the upload Lambda and `/upload`, and includes 5. Add `-c alert_email=you@example.com` for the alarm emails.
* The context values are the same settings that came from `config.env` before. [infra/app.py](../projects/smartdocs-ai/infra/app.py) reads them, and `infra/cdk.json` tells CDK to start the app through uv.

Repo: [scripts/40-cdk.sh](../projects/smartdocs-ai/scripts/40-cdk.sh) is these commands plus a check that the layer exists.

## Step 25. Prove it works (terminal and console)

The new stack has its own auto-named bucket and an empty index. Upload the sample and ask the questions again:

```bash
cd ..
cat build/cdk-outputs.json            # BucketName, ChatUrl, ...
aws s3 cp build/nimbus-kettle-manual.pdf s3://<BucketName>/docs/nimbus-kettle-manual.pdf
# wait for index/faiss.index to appear, then re-run the ask function from Step 14 with the ChatUrl output
```

With `phase=6` the chat endpoint wants the key. Read it from the secret named in the `ApiKeySecretArn` output:

```bash
KEY=$(aws secretsmanager get-secret-value --secret-id <ApiKeySecretArn> --query SecretString --output text)
```

In the console, open CloudFormation, stack `smartdocs-stack`, Resources tab. That list is everything you created by hand, plus the generated roles and log groups. Compare it with what you clicked.

Repo: [scripts/41-upload-sample-cdk.sh](../projects/smartdocs-ai/scripts/41-upload-sample-cdk.sh), and `33-test-chat.sh --cdk`.

## Step 26. Prove it is repeatable, then stop the costs (terminal)

```bash
cd infra
cdk destroy $CTX --force         # deletes everything, including the bucket contents
cdk deploy $CTX --outputs-file ../build/cdk-outputs.json       # and back again
```

When you are done for good, run `destroy` once more. It removes the secret too, which is the only thing with a standing cost. Nothing else here charges while idle. Bedrock tokens are the only real spend.

`removal_policy=DESTROY` and `auto_delete_objects=True` are right for a learning project. Production data uses `RETAIN`.

---

# When something breaks

| Symptom | Likely cause |
| --- | --- |
| `INVALID_PAYMENT_INSTRUMENT` on a Claude call | Failed Marketplace subscription, see Step 4 |
| Chat returns 502 with `AccessDeniedException` | The role lacks `bedrock:InvokeModel`, or the model was never called successfully as admin (Step 4) |
| `No module named 'faiss'` in a Lambda log | The layer is not attached, or was built for the wrong platform (Step 7) |
| `KeyError: 'DOCS_BUCKET'` (or another name) | Missing environment variable on that function |
| Upload works but the indexer never runs | Trigger prefix or suffix is wrong, or the key is not `docs/*.pdf` (Step 9) |
| Answer says "not found" but the PDF has it | Retrieval score below `MIN_SCORE`. Check `top_score` in the logs |
| `{"message":"Not Found"}` from curl | The URL is missing `/prod` or `/chat`, or the route's method is wrong |
| `Internal Server Error` and no Lambda logs | API Gateway has no permission to invoke the function |
| `aws logs tail /aws/lambda/...` returns nonsense | Git Bash path rewriting. `export MSYS_NO_PATHCONV=1` (Step 2) |
| Every request is 401 after Step 19 | The secret was stored as Key/value instead of Plaintext (Step 18) |
| `SignatureDoesNotMatch` on the PDF upload | The `PUT` was not sent with `Content-Type: application/pdf` |
| `429` responses | The throttle doing its job (Step 13) |
