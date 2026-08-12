#!/usr/bin/env python3
"""Download Karya's generation models into the network volume (ComfyUI layout).

Only downloads the specific files we need (allow_patterns), avoiding the huge
source repos. Repo layout (text_encoders/, vae/) matches ComfyUI's model dirs;
the transformer lands at repo root and is moved to diffusion_models/.
"""
import os
import shutil
from pathlib import Path

from huggingface_hub import snapshot_download

VOLUME = Path(os.environ.get("VOLUME", "/runpod-volume"))
REPO = "Abiray/Minimax-h3-nvfp4-INT4-INT8-Convrot"

# NOTE: the repo only ships int4_convrot / nvfp4_awq encoders. The int8_convrot
# encoder is documented in the README but NOT present in the file listing, so
# snapshot_download would silently skip it (text_encoders/ ends up empty).
# int4_convrot is the same Qwen3-VL-32B encoder, 4-bit convrot — safe with the
# int8 transformer (embeddings are dequantized at the interface).
PATTERNS = [
    "MiniMax_H3_Ref2VA_pruned_int8_convrot.safetensors",
    "text_encoders/qwen3vl_32b_minimax_h3_int4_convrot.safetensors",
    "vae/minimax_h3_video_vae_fp16.safetensors",
    "vae/minimax_h3_audio_vae_fp32.safetensors",
]

print("model-sync: pulling H3 stack (int8 convrot + encoder + VAEs)")
out = snapshot_download(
    repo_id=REPO,
    allow_patterns=PATTERNS,
    local_dir=str(VOLUME / "models"),
    local_dir_use_symlinks=False,
)
print(f"model-sync: snapshot at {out}")

# Move the transformer (repo root) into diffusion_models/
src = VOLUME / "models" / "MiniMax_H3_Ref2VA_pruned_int8_convrot.safetensors"
dst = VOLUME / "models" / "diffusion_models" / "MiniMax_H3_Ref2VA_pruned_int8_convrot.safetensors"
if src.exists() and not dst.exists():
    shutil.move(str(src), str(dst))
    print(f"model-sync: moved transformer -> {dst}")

# FLUX.1-dev fp8 for images
flux = VOLUME / "models" / "checkpoints" / "flux1-dev-fp8.safetensors"
if not flux.exists():
    print("model-sync: pulling FLUX.1-dev-fp8")
    snapshot_download(
        repo_id="Kijai/flux-fp8",
        allow_patterns=["flux1-dev-fp8.safetensors"],
        local_dir=str(VOLUME / "models" / "checkpoints"),
        local_dir_use_symlinks=False,
    )

print("model-sync: complete")
