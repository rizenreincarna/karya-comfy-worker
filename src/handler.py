"""RunPod serverless handler for Karya generation.

Receives a job: { workflow: <ComfyUI API-format workflow JSON>, output_key: "images|videos" }
Runs it through the local ComfyUI (already started by the worker), polls /history,
returns the generated asset(s) as base64 or URL.

Designed to be a drop-in for the tailnet ComfyUI client (lib/generate/local.ts):
same workflow format, same output semantics.
"""

import base64
import json
import os
import subprocess
import time
import urllib.request
import urllib.error

import runpod

COMFYUI_URL = os.environ.get("COMFYUI_URL", "http://127.0.0.1:8188")
POLL_SECONDS = 3
MAX_POLLS = 600  # 30 min cap for slow H3


def submit_prompt(workflow: dict) -> str:
    req = urllib.request.Request(
        f"{COMFYUI_URL}/prompt",
        data=json.dumps({"prompt": workflow}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        # surface ComfyUI's validation detail (model not found, bad input, etc.)
        body = e.read().decode("utf-8", "replace")[:2000]
        raise RuntimeError(f"ComfyUI /prompt {e.code}: {body}") from e
    pid = data.get("prompt_id")
    if not pid:
        raise RuntimeError(f"ComfyUI submit failed: {data}")
    return pid


def wait_for_output(prompt_id: str, output_key: str) -> dict:
    """Poll history until the job completes; return the first output file."""
    for _ in range(MAX_POLLS):
        time.sleep(POLL_SECONDS)
        try:
            with urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}", timeout=15) as resp:
                history = json.loads(resp.read())
        except Exception:
            continue
        entry = history.get(prompt_id)
        if not entry:
            continue
        status = (entry.get("status") or {}).get("status_str")
        if status == "error":
            raise RuntimeError(f"ComfyUI execution error: {entry.get('status')}")
        if not (entry.get("status") or {}).get("completed"):
            continue
        for node in (entry.get("outputs") or {}).values():
            files = node.get(output_key) or node.get("images") or node.get("videos")
            if files:
                f = files[0]
                return {
                    "filename": f["filename"],
                    "subfolder": f.get("subfolder", ""),
                    "type": f.get("type", "output"),
                }
    raise TimeoutError("ComfyUI generation timed out")


def fetch_output(file_info: dict) -> str:
    """Download the output file and return it as a base64 data URI."""
    from urllib.parse import quote

    url = (
        f"{COMFYUI_URL}/view?filename={quote(file_info['filename'])}"
        f"&subfolder={quote(file_info['subfolder'])}&type={file_info['type']}"
    )
    with urllib.request.urlopen(url, timeout=120) as resp:
        data = resp.read()
    mime = resp.headers.get("Content-Type", "application/octet-stream")
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def handler(job):
    """RunPod job entrypoint."""
    job_input = job.get("input", {})
    workflow = job_input.get("workflow")
    if not workflow:
        return {"error": "missing workflow in input"}

    try:
        # Inline reference image (base64) -> ComfyUI input dir
        ref = job_input.get("ref_image") or {}
        if ref.get("data") and ref.get("filename"):
            import re

            # strip any data: prefix
            data = ref["data"]
            if "," in data and data.startswith("data:"):
                data = data.split(",", 1)[1]
            # The worker's ComfyUI input dir is at /comfyui/input (base image layout)
            safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", ref["filename"])
            dest = os.path.join("/comfyui/input", safe_name)
            with open(dest, "wb") as fh:
                fh.write(base64.b64decode(data))
            # point LoadImage at the written file
            for node in workflow.values():
                if node.get("class_type") == "LoadImage":
                    node["inputs"]["image"] = safe_name

        prompt_id = submit_prompt(workflow)
        file_info = wait_for_output(prompt_id, job_input.get("output_key", "images"))
        result = fetch_output(file_info)
        return {"data_uri": result, "filename": file_info["filename"]}
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


if __name__ == "__main__":
    runpod.serverless.start({"handler": handler})
