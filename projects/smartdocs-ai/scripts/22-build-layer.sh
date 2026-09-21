#!/usr/bin/env bash
# Phase 2: build the Lambda layer (faiss-cpu + PyMuPDF + numpy) and publish it.
#
# No Docker needed: uv downloads the *Linux* wheels directly (--python-platform), so it works
# the same from Windows, macOS or Linux. Dependencies come from the `layer` group in pyproject.toml.
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config
need uv

OUT=layer/build
step "Installing Linux (x86_64, Python 3.12) wheels with uv"
rm -rf layer && mkdir -p "$OUT/python"
uv pip install --group layer --target "$OUT/python" \
  --python-platform x86_64-manylinux_2_28 --python-version 3.12 --only-binary :all: --no-cache

step "Slimming (Lambda allows 250 MB unzipped, function code included)"
find "$OUT/python" -name "__pycache__" -type d -prune -exec rm -rf {} +
find "$OUT/python" -path "*/tests" -type d -prune -exec rm -rf {} +
find "$OUT/python" -name "*.pyi" -delete
rm -rf "$OUT/python/bin"
size_mb="$(du -sm "$OUT/python" | cut -f1)"
log "unzipped size: ${size_mb} MB"
[ "$size_mb" -lt 240 ] || die "layer is ${size_mb} MB unzipped; the limit is 250 MB"

step "Zipping and uploading (over the 50 MB direct-upload limit, so it goes via S3)"
make_zip "$OUT" build/faiss-layer.zip
aws s3 cp build/faiss-layer.zip "s3://$BUCKET/layers/faiss-layer.zip"

step "Publishing layer version"
arn="$(aws lambda publish-layer-version --layer-name "$LAYER_NAME" \
  --description "faiss-cpu + PyMuPDF + numpy for $PROJECT" \
  --content "S3Bucket=$BUCKET,S3Key=layers/faiss-layer.zip" \
  --compatible-runtimes python3.12 --compatible-architectures x86_64 \
  --query LayerVersionArn --output text)"
ok "$arn"
