# Root-level handler re-export for RunPod's static repo scan.
# The actual handler logic is in src/handler.py; the Dockerfile copies that file
# to /handler.py in the image. This shim exists so RunPod's pre-deploy check
# (which scans the repo root for runpod.serverless.start()) finds the handler.

from src.handler import handler  # noqa: F401

import runpod

if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
