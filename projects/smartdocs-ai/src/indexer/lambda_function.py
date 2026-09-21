"""Indexer Lambda: runs when a PDF lands in s3://<bucket>/docs/.

PDF -> text (PyMuPDF) -> overlapping chunks -> Titan embeddings -> FAISS index,
saved back to s3://<bucket>/index/ where the chat Lambda finds it.
"""
import json
import logging
import os
from urllib.parse import unquote_plus

import boto3
import faiss
import pymupdf  # PyMuPDF (the old name "fitz" is deprecated)
import numpy as np
from botocore.config import Config

from chunker import chunk_text
from indexing import new_index, normalize, remove_source

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def log(msg, **fields):
    """One JSON object per line: CloudWatch Logs Insights can query the fields."""
    logger.info(json.dumps({"msg": msg, **fields}))


REGION = os.environ.get("AWS_REGION", "ap-south-2")
BUCKET = os.environ["DOCS_BUCKET"]
EMBED_MODEL = os.environ.get("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
EMBED_DIM = 1024
INDEX_KEY = "index/faiss.index"
META_KEY = "index/metadata.json"

# Clients live at module level so warm invocations reuse them.
s3 = boto3.client("s3", region_name=REGION)
bedrock = boto3.client(
    "bedrock-runtime", region_name=REGION,
    config=Config(retries={"max_attempts": 8, "mode": "adaptive"}),   # ride out throttling
)


def embed(text):
    resp = bedrock.invoke_model(modelId=EMBED_MODEL, body=json.dumps({"inputText": text[:8000]}))
    return json.loads(resp["body"].read())["embedding"]


def load_index():
    """Existing index from S3, or a fresh empty one on the very first upload."""
    try:
        raw = s3.get_object(Bucket=BUCKET, Key=INDEX_KEY)["Body"].read()
        index = faiss.deserialize_index(np.frombuffer(raw, dtype=np.uint8))
        meta = json.loads(s3.get_object(Bucket=BUCKET, Key=META_KEY)["Body"].read())
        log("Loaded existing index", vectors=index.ntotal)
    except s3.exceptions.NoSuchKey:
        index, meta = new_index(EMBED_DIM), {"chunks": [], "sources": []}
        log("Created new index")
    return index, meta


def save_index(index, meta):
    # Order matters: metadata first, index last. A chat request that sees the new
    # index is then guaranteed to find the matching metadata already in place.
    s3.put_object(Bucket=BUCKET, Key=META_KEY, Body=json.dumps(meta))
    s3.put_object(Bucket=BUCKET, Key=INDEX_KEY, Body=faiss.serialize_index(index).tobytes())
    log("Index saved", total_vectors=index.ntotal)


def index_document(key):
    pdf = s3.get_object(Bucket=BUCKET, Key=key)["Body"].read()
    doc = pymupdf.open(stream=pdf, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    log("Text extracted", key=key, pages=len(doc), chars=len(text))

    chunks = chunk_text(text)
    if not chunks:
        # Typical for scanned PDFs (images with no text layer). OCR would be the fix.
        log("No text found, nothing indexed", key=key)
        return 0
    log("Chunked", key=key, num_chunks=len(chunks))

    vectors = np.vstack([normalize(embed(c)) for c in chunks])

    index, meta = load_index()
    index, meta = remove_source(index, meta, key)      # idempotent re-uploads
    index.add(vectors)
    meta["chunks"].extend(chunks)
    meta["sources"].extend([key] * len(chunks))
    save_index(index, meta)
    return len(chunks)


def lambda_handler(event, context):
    results = []
    for record in event["Records"]:
        key = unquote_plus(record["s3"]["object"]["key"])   # S3 events URL-encode keys ("my file.pdf" -> "my+file.pdf")
        # Safety guard: the index is written under index/, so never react to it.
        # (The S3 trigger is filtered to docs/ too. Belt and braces against a loop.)
        if not key.startswith("docs/"):
            log("Skipping non-docs key", key=key)
            continue
        log("Starting indexing", key=key)
        results.append({"source": key, "indexed_chunks": index_document(key)})
    return {"statusCode": 200, "body": json.dumps(results)}
