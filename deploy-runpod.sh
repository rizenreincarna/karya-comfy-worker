#!/bin/bash
# Deploy the Karya ComfyUI worker to RunPod serverless (4090, 100GB volume).
# Usage: RUNPOD_API_KEY=... HF_TOKEN=... bash deploy-runpod.sh <ghcr-token>
set -euo pipefail

GH_TOKEN="${1:-${GHCR_TOKEN:?usage: deploy-runpod.sh <ghcr-token>}}"
export RUNPOD_API_KEY="${RUNPOD_API_KEY:?set RUNPOD_API_KEY}"
HF_TOKEN="${HF_TOKEN:-}"

echo "==> pushing image to GHCR"
echo "$GH_TOKEN" | docker login ghcr.io -u rizenreincarna --password-stdin >/dev/null
docker tag karya-comfy:latest ghcr.io/rizenreincarna/karya-comfy:latest
docker push ghcr.io/rizenreincarna/karya-comfy:latest | tail -1

echo "==> making package public"
gh api -X PUT /user/packages/container/karya-comfy/visibility \
  -f visibility=public >/dev/null && echo "package public"

echo "==> creating template"
TEMPLATE_ID=$(/tmp/runpodctl template create \
  --name karya-comfy \
  --image ghcr.io/rizenreincarna/karya-comfy:latest \
  --container-disk-size 20 \
  --is-serverless true \
  2>&1 | python3 -c "import json,sys; print(json.load(sys.stdin)['template']['id'])")
echo "template: $TEMPLATE_ID"

echo "==> creating endpoint"
ENV_ARGS=()
if [ -n "$HF_TOKEN" ]; then ENV_ARGS+=(--env "HF_TOKEN=$HF_TOKEN"); fi
/tmp/runpodctl serverless create \
  --template-id "$TEMPLATE_ID" \
  --name karya-comfy \
  --gpu-id "NVIDIA GeForce RTX 4090" \
  --network-volume-id whilusgtvp \
  --workers-min 0 \
  --workers-max 1 \
  --idle-timeout 60 \
  --execution-timeout 1500 \
  "${ENV_ARGS[@]}" \
  2>&1 | head -20
