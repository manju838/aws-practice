#!/usr/bin/env bash
# Phase 2: one private, versioned bucket with two zones: docs/ (uploads) and index/ (FAISS index).
T="$(dirname "${BASH_SOURCE[0]}")/../../../tools/lib"; source "$T/common.sh"
load_project_config

if aws s3api head-bucket --bucket "$BUCKET" 2>/dev/null; then
  ok "bucket $BUCKET already exists"
else
  step "Creating bucket $BUCKET in $AWS_REGION"
  aws s3 mb "s3://$BUCKET" --region "$AWS_REGION"
fi

step "Locking it down"
aws s3api put-public-access-block --bucket "$BUCKET" --public-access-block-configuration \
  BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-versioning --bucket "$BUCKET" --versioning-configuration Status=Enabled
aws s3api put-bucket-tagging --bucket "$BUCKET" --tagging "TagSet=[{Key=project,Value=$PROJECT}]"
ok "private, versioned, tagged"
aws s3 ls | grep "$BUCKET" || true
