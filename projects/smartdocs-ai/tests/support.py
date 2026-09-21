"""Shared test setup: env vars the Lambda modules read at import time, import paths, and
load_handler(). Imported by conftest.py (so it runs first) and by the test files.
Nothing here talks to AWS, so the tests run without credentials."""
import importlib.util
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

os.environ.update({
    "AWS_DEFAULT_REGION": "ap-south-2", "AWS_REGION": "ap-south-2",
    "AWS_ACCESS_KEY_ID": "test", "AWS_SECRET_ACCESS_KEY": "test",   # dummy: clients are never called for real
    "DOCS_BUCKET": "test-bucket", "CONVERSATIONS_TABLE": "test-table",
    "CHAT_MODEL_ID": "test-model",
})
os.environ.pop("API_KEY_SECRET_ARN", None)

# Each Lambda dir is a flat namespace (chunker, retriever, auth, ...). Put them all on the path.
for sub in ("indexer", "chat", "upload"):
    sys.path.insert(0, str(ROOT / "src" / sub))


def load_handler(alias, sub):
    """Import src/<sub>/lambda_function.py under a unique name (all three are called lambda_function)."""
    spec = importlib.util.spec_from_file_location(alias, ROOT / "src" / sub / "lambda_function.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[alias] = module
    spec.loader.exec_module(module)
    return module
