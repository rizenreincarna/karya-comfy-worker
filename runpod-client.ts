// RunPod serverless generation backend for Karya.
// Targets the official runpod/worker-comfyui handler contract:
//   INPUT:  { input: { workflow, images?: [{name, image: dataUri}], comfy_org_api_key? } }
//   OUTPUT: { images: [{filename, type: "base64", data: <raw base64>}], errors?: [] }
//           or { error } on failure.
// SaveVideo output arrives under the "images" key (mp4 filename), same as SaveImage.
// Enabled when RUNPOD_URL + RUNPOD_API_KEY are set (providers.ts routes here first).

const POLL_MS = 4000;
const IMAGE_TIMEOUT_MS = 5 * 60 * 1000;
const VIDEO_TIMEOUT_MS = 25 * 60 * 1000;

interface RunpodOutput {
  images?: Array<{ filename: string; type: string; data: string }>;
  errors?: string[];
  error?: string;
}

function sleep(ms: number): Promise<void> {
  const { promise, resolve } = Promise.withResolvers<void>();
  setTimeout(resolve, ms);
  return promise;
}

function contentTypeFor(filename: string): string {
  if (filename.endsWith(".mp4")) return "video/mp4";
  if (filename.endsWith(".webp")) return "image/webp";
  if (filename.endsWith(".jpg") || filename.endsWith(".jpeg")) return "image/jpeg";
  if (filename.endsWith(".png")) return "image/png";
  if (filename.endsWith(".mp3")) return "audio/mpeg";
  return "application/octet-stream";
}

/** Submit a job and poll /status/{id} until COMPLETED; return the first base64 asset. */
async function runpodJob(
  input: Record<string, unknown>,
  timeoutMs: number
): Promise<{ buffer: Buffer; contentType: string }> {
  const base = process.env.RUNPOD_URL;
  const key = process.env.RUNPOD_API_KEY;
  if (!base || !key) throw new Error("RUNPOD_URL/RUNPOD_API_KEY not set");

  const submit = await fetch(`${base}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${key}` },
    body: JSON.stringify({ input }),
  });
  if (!submit.ok) throw new Error(`runpod submit failed: ${submit.status}`);
  const { id } = (await submit.json()) as { id?: string };
  if (!id) throw new Error("runpod: no job id");

  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    await sleep(POLL_MS);
    const res = await fetch(`${base}/status/${id}`, { headers: { Authorization: `Bearer ${key}` } });
    if (!res.ok) continue;
    const data = (await res.json()) as { status?: string; output?: RunpodOutput };
    if (data.status === "FAILED") throw new Error(`runpod job failed: ${data.output?.error ?? JSON.stringify(data.output ?? {}).slice(0, 300)}`);
    if (data.status === "COMPLETED") {
      const asset = data.output?.images?.[0];
      if (!asset?.data) throw new Error(`runpod: completed without image data: ${JSON.stringify(data.output ?? {}).slice(0, 200)}`);
      return { buffer: Buffer.from(asset.data, "base64"), contentType: contentTypeFor(asset.filename) };
    }
  }
  throw new Error("runpod job timed out");
}

/** Anti-slop suffix appended to every image prompt (FLUX dev fp8, cfg=1 → positive-prompt-driven). */
const IMAGE_ANTI_SLOP =
  ". clean minimalist composition, plain uncluttered background, absolutely no text, no letters, no words, no signs, no labels, no watermark, no logos, photorealistic, sharp focus";

/** FLUX.1-dev fp8 image workflow (checkpoint from volume). */
function fluxImageWorkflow(prompt: string): Record<string, unknown> {
  const text = prompt + IMAGE_ANTI_SLOP;
  return {
    "3": { class_type: "KSampler", inputs: { seed: Math.floor(Math.random() * 1e15), steps: 20, cfg: 1.0, sampler_name: "euler", scheduler: "simple", denoise: 1.0, model: ["30", 0], positive: ["35", 0], negative: ["7", 0], latent_image: ["5", 0] } },
    "5": { class_type: "EmptyLatentImage", inputs: { width: 1024, height: 1024, batch_size: 1 } },
    "6": { class_type: "CLIPTextEncode", inputs: { text, clip: ["30", 1] } },
    "7": { class_type: "CLIPTextEncode", inputs: { text: "text, letters, words, watermark, logo, signature, typography, caption, writing, gibberish, brand name, title, label", clip: ["30", 1] } },
    "8": { class_type: "VAEDecode", inputs: { samples: ["3", 0], vae: ["30", 2] } },
    "9": { class_type: "SaveImage", inputs: { filename_prefix: "karya_gen", images: ["8", 0] } },
    "30": { class_type: "CheckpointLoaderSimple", inputs: { ckpt_name: "flux1-dev-fp8.safetensors" } },
    "35": { class_type: "FluxGuidance", inputs: { guidance: 3.5, conditioning: ["6", 0] } },
  };
}

/** MiniMax-H3 Ref2VA workflow at 768p / 24fps with synced audio (int8_convrot, native nodes). */
function h3VideoWorkflow(prompt: string, refImage: string): Record<string, unknown> {
  const p = prompt + ". Photorealistic, sharp focus, perfect anatomy, five fingers, no text, no letters, no words, no captions, no watermark, no logos, no gibberish";
  return {
    "186": { class_type: "UNETLoader", inputs: { unet_name: "MiniMax_H3_Ref2VA_pruned_int8_convrot.safetensors", weight_dtype: "default" } },
    "187": { class_type: "CLIPLoader", inputs: { clip_name: "qwen3vl_32b_minimax_h3_int8_convrot.safetensors", type: "minimax" } },
    "119": { class_type: "VAELoader", inputs: { vae_name: "minimax_h3_video_vae_fp16.safetensors" } },
    "120": { class_type: "VAELoader", inputs: { vae_name: "minimax_h3_audio_vae_fp32.safetensors" } },
    "137": { class_type: "LoadImage", inputs: { image: refImage, upload: "image" } },
    "136": { class_type: "MiniMaxH3ReferenceToVideo", inputs: { clip: ["187", 0], vae: ["119", 0], audio_vae: ["120", 0], ref_images: { ref_image_0: ["137", 0] }, prompt: p, width: 1360, height: 768, length: 124, ref_image_size: "match" } },
    "129": { class_type: "RandomNoise", inputs: { noise_seed: Math.floor(Math.random() * 1e15) } },
    "126": { class_type: "BasicGuider", inputs: { model: ["186", 0], conditioning: ["136", 0] } },
    "123": { class_type: "KSamplerSelect", inputs: { sampler_name: "res_multistep" } },
    "124": { class_type: "BasicScheduler", inputs: { model: ["186", 0], scheduler: "simple", steps: 24, denoise: 1.0 } },
    "125": { class_type: "SamplerCustomAdvanced", inputs: { noise: ["129", 0], guider: ["126", 0], sampler: ["123", 0], sigmas: ["124", 0], latent_image: ["136", 1] } },
    "122": { class_type: "VAEDecode", inputs: { samples: ["125", 0], vae: ["119", 0] } },
    "121": { class_type: "VAEDecodeAudio", inputs: { samples: ["125", 0], vae: ["120", 0] } },
    "175": { class_type: "CreateVideo", inputs: { images: ["122", 0], audio: ["121", 0], fps: 24 } },
    "174": { class_type: "SaveVideo", inputs: { video: ["175", 0], filename_prefix: "karya_h3", format: "mp4", codec: "h264", quality: "auto" } },
  };
}

export async function runpodGenerateImage(prompt: string): Promise<{ buffer: Buffer; contentType: string; model: string }> {
  const { buffer, contentType } = await runpodJob({ workflow: fluxImageWorkflow(prompt) }, IMAGE_TIMEOUT_MS);
  return { buffer, contentType, model: "runpod-flux-dev-fp8" };
}

/** H3 video: reference image travels in the official handler's `images` array (base64 data URI). */
export async function runpodGenerateVideo(
  prompt: string,
  refImageBuffer: Buffer,
  refImageName: string,
  refImageContentType = "image/jpeg"
): Promise<{ buffer: Buffer; contentType: string; model: string }> {
  const dataUri = `data:${refImageContentType};base64,${refImageBuffer.toString("base64")}`;
  const { buffer, contentType } = await runpodJob(
    {
      workflow: h3VideoWorkflow(prompt, refImageName),
      images: [{ name: refImageName, image: dataUri }],
    },
    VIDEO_TIMEOUT_MS
  );
  return { buffer, contentType, model: "runpod-minimax-h3-int8" };
}
