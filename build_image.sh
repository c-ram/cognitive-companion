#!/bin/bash
set -e

IMAGE_NAME="ai-api-gateway:latest"
NAMESPACE="default"

echo "Building image $IMAGE_NAME..."

if command -v nerdctl &> /dev/null; then
    echo "Using nerdctl..."
    nerdctl build -t $IMAGE_NAME --namespace k8s.io .
elif command -v docker &> /dev/null; then
    echo "Using docker..."
    docker build . -t localhost:32000/$IMAGE_NAME # --no-cache
    docker push localhost:32000/$IMAGE_NAME
else
    echo "Error: Neither nerdctl nor docker found."
    exit 1
fi

echo "Build complete."
