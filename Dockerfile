# Karya serverless worker — ComfyUI (v0.31.1, native MiniMax-H3) + FLUX.1-dev.
# Base: RunPod worker-comfyui (official handler; accepts input.workflow + input.images).
# Customizations: (1) ComfyUI upgraded to v0.31.1 for native MiniMaxH3 nodes,
# (2) first-boot model sync into the attached network volume.

FROM runpod/worker-comfyui:5.8.6-base

# --- Upgrade ComfyUI to v0.31.1 (native MiniMax H3 nodes) ---
RUN cd /comfyui \
  && git fetch --tags --depth 50 origin \
  && git checkout v0.31.1 \
  && pip install --no-cache-dir -r requirements.txt \
  && python -c "import pathlib; hits=[p for p in pathlib.Path('/comfyui').rglob('*.py') if 'MiniMaxH3' in p.read_text(errors='ignore')]; assert hits, 'H3 nodes missing'; print('H3 files:', hits)"

# --- Let ComfyUI find diffusion_models on the network volume ---
RUN sed -i 's|  unet: models/unet/|  unet: models/unet/\n  diffusion_models: models/diffusion_models/|' /comfyui/extra_model_paths.yaml

# --- First-boot model sync ---
COPY scripts/model-sync.py /model-sync.py
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
