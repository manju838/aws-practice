"""Retriever: question -> the most relevant document chunks.

The FAISS index lives in S3. It is downloaded once per warm Lambda container and
kept in memory; a cheap HEAD request on each call notices when the indexer has
written a newer version and reloads it.
"""
import json
import logging
import os

import boto3
import faiss
import numpy as np
from botocore.config import Config
from botocore.exceptions import ClientError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

REGION = os.environ.get("AWS_REGION", "ap-south-2")
BUCKET = os.environ["DOCS_BUCKET"]
EMBED_MODEL = os.environ.get("EMBED_MODEL_ID", "amazon.titan-embed-text-v2:0")
MIN_SCORE = float(os.environ.get("MIN_SCORE", "0.3"))   # cosine similarity floor
INDEX_KEY = "index/faiss.index"
META_KEY = "index/metadata.json"

s3 = boto3.client("s3", region_name=REGION)
bedrock = boto3.client(
    "bedrock-runtime", region_name=REGION,
    config=Config(retries={"max_attempts": 6, "mode": "adaptive"}),
)

# Module-level cache survives between invocations of the same warm container.
_cache = {"index": None, "meta": None, "etag": None}


def _refresh_cache():
    """Make sure the cache holds the current index. Returns False if no index exists yet."""
    try:
        etag = s3.head_object(Bucket=BUCKET, Key=INDEX_KEY)["ETag"]
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchKey", "NotFound"):
            _cache.update(index=None, meta=None, etag=None)
            return False
        raise
    if _cache["etag"] == etag and _cache["index"] is not None:
        return True                                          # warm hit: nothing to download

    # Load the index first, then the metadata. The indexer writes them in the
    # opposite order, so a new index always has its metadata already in place.
    obj = s3.get_object(Bucket=BUCKET, Key=INDEX_KEY)
    index = faiss.deserialize_index(np.frombuffer(obj["Body"].read(), dtype=np.uint8))
    meta = json.loads(s3.get_object(Bucket=BUCKET, Key=META_KEY)["Body"].read())
    _cache.update(index=index, meta=meta, etag=obj["ETag"])
    logger.info(json.dumps({"msg": "Index loaded", "vectors": index.ntotal}))
    return True


def _embed_query(text):
    resp = bedrock.invoke_model(modelId=EMBED_MODEL, body=json.dumps({"inputText": text[:8000]}))
    vec = np.array(json.loads(resp["body"].read())["embedding"], dtype=np.float32)
    vec /= np.linalg.norm(vec) + 1e-9        # same normalisation as at index time
    return vec.reshape(1, -1)                # FAISS wants shape (1, dim)


def retrieve(question, top_k=3):
    """Return up to top_k chunks as [{"text", "source", "score"}], best first.
    Returns [] if nothing has been indexed yet or nothing is similar enough."""
    if not _refresh_cache():
        logger.warning(json.dumps({"msg": "No index found yet"}))
        return []

    scores, ids = _cache["index"].search(_embed_query(question), top_k)
    meta = _cache["meta"]
    results = []
    for i, score in zip(ids[0], scores[0]):
        # i == -1 means "fewer than top_k vectors exist"; the bounds check guards
        # the brief window where metadata is older than the index.
        if 0 <= i < len(meta["chunks"]) and score >= MIN_SCORE:
            results.append({"text": meta["chunks"][i], "source": meta["sources"][i], "score": round(float(score), 4)})

    logger.info(json.dumps({
        "msg": "Retrieved chunks", "returned": len(results),
        "top_score": round(float(scores[0][0]), 4) if len(scores[0]) else None,
    }))
    return results
