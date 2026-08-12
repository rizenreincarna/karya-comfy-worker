#!/bin/bash
# Entrypoint wrapper: populate the network volume on first boot, then run the
# original worker start script (starts ComfyUI + the RunPod handler).
set -e

VOLUME=/runpod-volume

if [ -d "$VOLUME" ]; then
  if [ ! -f "$VOLUME/models/diffusion_models/MiniMax_H3_Ref2VA_pruned_int8_convrot.safetensors" ] \
     || [ ! -f "$VOLUME/models/checkpoints/flux1-dev-fp8.safetensors" ] \
     || [ ! -f "$VOLUME/models/text_encoders/qwen3vl_32b_minimax_h3_int4_convrot.safetensors" ] \
     || [ ! -f "$VOLUME/models/diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors" ] \
     || [ ! -f "$VOLUME/models/text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors" ] \
     || [ ! -f "$VOLUME/models/model_patches/ltx-2.5-duration-head-bf16.safetensors" ] \
     || [ ! -f "$VOLUME/models/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors" ]; then
    echo "entrypoint: syncing models to $VOLUME (H3/FLUX/LTX)"
    mkdir -p "$VOLUME/models/diffusion_models" "$VOLUME/models/text_encoders" \
             "$VOLUME/models/vae" "$VOLUME/models/checkpoints" "$VOLUME/models/model_patches" \
             "$VOLUME/models/latent_upscale_models"
    VOLUME="$VOLUME" python /model-sync.py
  else
    echo "entrypoint: models already on volume"
  fi
else
  echo "entrypoint: WARNING - no network volume mounted at $VOLUME"
fi

exec /start.sh
