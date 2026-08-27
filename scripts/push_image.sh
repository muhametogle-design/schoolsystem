#!/usr/bin/env bash
# Build and push the NE-EMIS image to a registry.
#
# Usage:
#   ./scripts/push_image.sh ghcr.io/<owner>/ne-emis:1.0.0
#   ./scripts/push_image.sh registry.example.com/ne-emis:latest
#
# Requires Docker and authentication to the target registry.
set -euo pipefail
TAG="${1:-ne-emis:latest}"
REGISTRY="${TAG%%/*}"

echo "Building $TAG (layer-cached via requirements.txt)..."
docker build -t "$TAG" .

echo "Pushing $TAG to $REGISTRY..."
docker push "$TAG"

echo
echo "Run it:"
echo "  docker run --rm -p 5000:5000 -e NEEMIS_DEMO_MODE=true $TAG"
echo "  curl http://localhost:5000/health"
echo "  curl http://localhost:5000/students"
