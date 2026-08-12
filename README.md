# RunPod serverless deployment for Karya

High-quality image (FLUX) + audio-video (MiniMax-H3 at 768p/24fps) generation
via RunPod serverless. Replaces the 8GB tailnet GPUs for production quality.

## Prerequisites
- RunPod account with credits + API key (https://www.runpod.io/user/settings)
- HuggingFace token (models are ungated but a token speeds downloads)
- Docker (for building the worker image) or use runpodctl

## Deploy

1. Build and push the worker image:
```bash
docker build -t docker.io/<your-user>/karya-comfy:latest .
docker push docker.io/<your-user>/karya-comfy:latest
```

2. Create the endpoint (24GB GPU recommended for H3 int8):
```bash
export RUNPOD_API_KEY=<your-key>
runpodctl serverless deploy karya-comfy \
  --gpu RTX4090 \
  --max-workers 1 \
  --min-workers 0 \
  --idle-timeout 30 \
  --image docker.io/<your-user>/karya-comfy:latest
```
(GPU options: RTX4090, A5000, L40S. H3 int8_convrot needs 24GB.)

3. Set Karya env on the VPS:
```bash
# /opt/karya/.env
RUNPOD_URL=https://api.runpod.ai/v2/<ENDPOINT_ID>
RUNPOD_API_KEY=<your-key>
```

4. Restart karya-web + karya-worker. providers.ts routes:
   RunPod (best) -> tailnet local (free fallback) -> FAL (last resort).

## Workflows
- Image: FLUX.1 schnell Q4_K_S, 1024x1024, 8 steps, anti-slop negative
- Video: MiniMax-H3 Ref2VA int8_convrot, 1280x720, 24fps, 24 steps, synced audio,
  reference image inline (base64), anti-slop prompt suffix

## Notes
- Serverless scales to zero; billed per GPU-second while warm.
- MiniMax-H3 license restricts US/EU/UK/KR territories (use APAC regions).
- The handler (src/handler.py) writes inline ref images to ComfyUI/input then runs.
