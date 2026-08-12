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

# Skip files already on the volume so re-syncs only fetch what's missing
# (idempotent). snapshot_download would otherwise re-download everything.
# The transformer is checked at its destination (diffusion_models/ after the
# first-boot move); the download pattern targets the repo-root path.
MISSING = []
for pat in PATTERNS:
    if pat.startswith("MiniMax_H3_Ref2VA"):
        check = VOLUME / "models" / "diffusion_models" / pat
    else:
        check = VOLUME / "models" / pat
    if not check.exists():
        MISSING.append(pat)

if MISSING:
    print(f"model-sync: pulling H3 stack ({len(MISSING)} file(s) missing: {MISSING})")
    out = snapshot_download(
        repo_id=REPO,
        allow_patterns=MISSING,
        local_dir=str(VOLUME / "models"),
        local_dir_use_symlinks=False,
    )
    print(f"model-sync: snapshot at {out}")
else:
    print("model-sync: H3 stack already complete on volume")

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

# ---------------------------------------------------------------------------
# LTX-2.5 (multi-shot audio-video) — GATED repo, needs HF_TOKEN with gated
# access. Files land in their own dirs so H3/FLUX are untouched.
# ComfyUI v0.32.0 required (duration_head nodes). The gemma4_e2b prompt
# enhancer is a separate UNGATED repo (Comfy-Org/gemma-4).
# ---------------------------------------------------------------------------
LTX_REPO = "Lightricks/LTX-2.5"
LTX_PATTERNS = [
    "diffusion_models/ltx-2.5-22b-distilled-transformer-comfy-int8-convrot.safetensors",
    "text_encoders/gemma4-12b-with-proj-ltx-2.5-comfy-int8-convrot.safetensors",
    "vae/ltx-2.5-video-vae-bf16.safetensors",
    "vae/ltx-2.5-audio-vae-bf16.safetensors",
    "model_patches/ltx-2.5-duration-head-bf16.safetensors",
]
ltx_missing = [p for p in LTX_PATTERNS if not (VOLUME / "models" / p).exists()]
if ltx_missing:
    if not os.environ.get("HF_TOKEN"):
        print("model-sync: WARNING — LTX-2.5 files missing but HF_TOKEN not set; skipping LTX sync")
    else:
        print(f"model-sync: pulling LTX-2.5 stack ({len(ltx_missing)} missing: {ltx_missing})")
        snapshot_download(
            repo_id=LTX_REPO,
            allow_patterns=ltx_missing,
            local_dir=str(VOLUME / "models"),
            local_dir_use_symlinks=False,
            token=os.environ.get("HF_TOKEN"),
        )
        print("model-sync: LTX-2.5 stack done")
else:
    print("model-sync: LTX-2.5 stack already complete on volume")

# gemma4_e2b prompt enhancer (ungated, separate repo)
gemma_e2b = VOLUME / "models" / "text_encoders" / "gemma4_e2b_it_bf16.safetensors"
if not gemma_e2b.exists():
    print("model-sync: pulling gemma4_e2b prompt enhancer")
    snapshot_download(
        repo_id="Comfy-Org/gemma-4",
        allow_patterns=["text_encoders/gemma4_e2b_it_bf16.safetensors"],
        local_dir=str(VOLUME / "models"),
        local_dir_use_symlinks=False,
    )

print("model-sync: complete")
