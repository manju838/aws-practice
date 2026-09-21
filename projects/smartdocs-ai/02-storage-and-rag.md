# Phase 2: Storage and RAG

| | |
| --- | --- |
| **Time budget** | 90 min |
| **Actual time** | ⏳ |
| **Cost** | about $0 (a few cents of Titan embeddings) |
| **Status** | ⬜ Not started |

## Why this phase exists

A language model knows nothing about your PDF. RAG bridges that in two stages: **index** the document once,
then **retrieve** the relevant passages at question time and hand them to the model. This phase builds the indexing
stage and the retrieval helper. Nothing here calls Claude yet.

```
PDF in S3 docs/ ──► indexer Lambda ──► chunks ──► Titan embeddings ──► FAISS index in S3 index/
```

Key ideas:

* **Chunking.** Models and embeddings work on limited text, and a whole book embeds into mush. We split into 300-word chunks with a
  50-word overlap so a sentence at a boundary is never cut off from its context.
* **Embedding.** Titan turns each chunk into 1024 numbers. Text with similar meaning lands close together in that space.
* **FAISS.** A library that finds the nearest vectors quickly. We store unit-length vectors so the inner product equals cosine similarity.
* **Two folders in one bucket.** `docs/` receives uploads and triggers indexing; `index/` receives the output. The trigger is filtered to
  `docs/*.pdf`, because a trigger on `index/` would fire on the indexer's own output forever and run up a bill.

## Steps

### 1. The bucket

```bash
tools/capture.sh smartdocs-ai 20-bucket bash scripts/20-create-bucket.sh
```

Private (all public access blocked), versioned, tagged. The name is `smartdocs-<account id>` because bucket names are global.

### 2. The Lambda execution role

```bash
tools/capture.sh smartdocs-ai 21-role bash scripts/21-create-iam-role.sh
```

A Lambda never holds credentials; it **assumes a role** and AWS hands it temporary ones. The role gets the standard logging policy
plus one inline policy with four statements: read and write objects in this bucket, list this bucket, three DynamoDB actions on this
table, and `bedrock:InvokeModel`. Compare with the first attempt, which used `AmazonS3FullAccess`, `AmazonBedrockFullAccess` and
`AmazonDynamoDBFullAccess`. `s3:ListBucket` matters more than it looks: without it, a missing object returns 403 instead of 404.

### 3. The layer

```bash
tools/capture.sh smartdocs-ai 22-layer bash scripts/22-build-layer.sh
```

FAISS, PyMuPDF and numpy contain compiled code, and Lambda runs Linux. Wheels built on your laptop would crash there.
`uv pip install --python-platform x86_64-manylinux_2_28` downloads the Linux builds directly, so no Docker is needed.
The script slims the result (about 170 MB unzipped against a hard 250 MB limit), zips it (about 60 MB, over the 50 MB direct-upload limit),
stages it in S3 and publishes a **layer version**. Layers are immutable and versioned; functions keep the version they were deployed with
until you update them.

### 4. Read the indexer

`src/indexer/lambda_function.py` is short. Read it once now. In order: decode the S3 key, download the PDF, extract text with PyMuPDF,
chunk, embed each chunk, remove any earlier chunks from the same file, add the new vectors, and save. Metadata is written before the index so a
reader that sees the new index always finds its metadata.

### 5. Deploy it

```bash
tools/capture.sh smartdocs-ai 23-deploy-indexer bash scripts/23-deploy-indexer.sh
```

1024 MB of memory, 300 s timeout, the layer attached, and the bucket name passed as an environment variable.

### 6. Wire S3 to it

```bash
tools/capture.sh smartdocs-ai 24-trigger bash scripts/24-attach-s3-trigger.sh
```

S3 and Lambda do not know each other. Two things connect them: a **permission** letting S3 invoke this function (scoped to this bucket and
this account), and a **notification rule** saying when: `ObjectCreated`, prefix `docs/`, suffix `.pdf`.

### 7. Try it for real

```bash
tools/capture.sh smartdocs-ai 25-pipeline bash scripts/25-test-pipeline.sh
```

With no argument it generates a two-page manual for a fictional kettle and uploads it. Every fact in it is invented (the temperature, the warranty
length, the founding city), so if the assistant answers correctly in Phase 3 it can only have come from retrieval. You can also pass your own PDF.

## Verify

* The script prints indexer log lines ending in "Index saved".
* `aws s3 ls s3://<bucket>/index/` shows `faiss.index` and `metadata.json`.
* Run the script a second time: "total_vectors" stays the same. Re-uploading replaces instead of duplicating.
* Local tests pass: `uv run pytest tests/test_indexer_and_retriever.py`.

## Results

TODO(result): the indexer log lines (pages, chars, chunks, vectors) from [results/25-pipeline.txt](results/25-pipeline.txt).

TODO(result): size of `faiss.index` and `metadata.json`, and what one chunk looks like in the metadata.

TODO(result): time from upload to "Index saved", and the embedding cost.

TODO(result): screenshot of the Lambda console showing the layer attached (`assets/indexer-layer.png`, redacted).

## Gotchas and lessons

* TODO(result): first cold-start duration for the indexer.
* The layer zip exceeds 50 MB, so it must be uploaded through S3. Direct upload fails.
* New IAM roles take several seconds to become usable. The deploy helper retries instead of failing.
* A PDF made of scanned images has no text layer. The indexer logs "No text found" and indexes nothing.
