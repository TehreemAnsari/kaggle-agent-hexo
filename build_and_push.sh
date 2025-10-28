#!/bin/bash
set -e

ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION="us-west-2"
REPO="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/kaggle-runner"

TAG=${1:-latest}

echo "🚀 Building and pushing multi-arch image to $REPO:$TAG"

docker buildx create --use --name multi || true
docker buildx build \
  --platform linux/amd64,linux/arm64 \
  -t "$REPO:$TAG" \
  -f runner/Dockerfile \
  --push .

echo " Image pushed: $REPO:$TAG"
