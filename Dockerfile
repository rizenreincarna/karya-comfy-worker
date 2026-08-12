# Karya serverless worker — ComfyUI (v0.31.1, native MiniMax-H3) + FLUX.1-dev.
FROM runpod/worker-comfyui:5.8.6-base

# --- Upgrade ComfyUI to v0.31.1 (native MiniMax H3 nodes) ---
# Full clone for reliability on the builder (shallow --depth fetches miss tags).
RUN cd /comfyui \
  && git fetch --tags origin \
  && git checkout -q v0.31.1 \
  && pip install --no-cache-dir -r requirements.txt \
  && python -c "import pathlib; hits=[p for p in pathlib.Path('/comfyui').rglob('*.py') if 'MiniMaxH3' in p.read_text(errors='ignore')]; assert hits, 'H3 nodes missing'; print('H3 files:', hits)"

# --- Let ComfyUI find diffusion_models on the network volume ---
RUN sed -i 's|  unet: models/unet/|  unet: models/unet/\n  diffusion_models: models/diffusion_models/\n  text_encoders: models/text_encoders/|' /comfyui/extra_model_paths.yaml \
  && grep -c "text_encoders" /comfyui/extra_model_paths.yaml

# --- First-boot model sync + custom handler ---
COPY scripts/model-sync.py /model-sync.py
COPY src/handler.py /handler.py
COPY scripts/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
