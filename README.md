# VRGDG SeedVR2 TensorRT Studio

A local video restoration and upscale studio for SeedVR2 with TensorRT acceleration for faster VAE processing, a custom JavaScript interface, and FastAPI backend.

## Features

- Original, Restored, Compare, and synchronized Side by side viewing modes.
- One shared play button, timeline scrubbing, frame stepping, fullscreen, zoom, pan, and wipe comparison.
- Preview renders and full-video renders with elapsed time and ETA.
- Output presets for original-size enhancement, 1K/1080p, 2K/1440p, and 4K/2160p.
- Preserve the original aspect ratio or center-crop to 16:9.
- Resumable long-video rendering with automatic frame-aware chunk sizing, manual 30-second to 30-minute choices, retry from the last completed chunk, failure reasons, and saved logs.
- Post-only reprocessing for sharpening, film grain, TensorRT seam smoothing, and optional skin finishing.
- TensorRT decoding uses Optimized Fast automatically and falls back to the internal Stable decoder from saved latents if needed, without rerunning AI restoration.
- Saved settings, previous-output loading, and an Open project folder action.

## Install and start

This package targets Windows with an NVIDIA RTX GPU. Allow at least 35 GB of free disk space for dependencies, model weights, temporary ONNX exports, and locally built TensorRT engines.

1. Double-click **Install SeedVR Studio.bat** once after downloading or cloning the repository.
2. Leave it open while it installs Python/FFmpeg if needed, creates the private environment, installs CUDA PyTorch, SeedVR2, SageAttention 2, and TensorRT RTX, downloads the default model and VAE, and builds engines for your GPU.
3. Double-click **Launch SeedVR Studio Pro.bat**.

The Pro launcher also detects an incomplete installation and opens the installer automatically. Downloads and TensorRT preparation are resumable. Detailed instructions and troubleshooting are in the [installation guide](docs/INSTALLATION.md).

Model weights are stored locally in `models\` and are not committed to GitHub. Outputs, virtual environments, TensorRT engines/caches, and optional runtime files are also kept local.

## Render engines

- **SeedVR2 + TensorRT** — the recommended fast path. It runs SeedVR2 restoration while using TensorRT to accelerate VAE decoding. Fixed TensorRT engines currently support temporal batch sizes **5** and **21**.
- **SeedVR2 (Legacy)** — the standard PyTorch SeedVR2 path. It supports more temporal batch sizes, but it can be substantially slower, especially for long videos.

The batch-size dropdown automatically shows only values supported by the selected engine.

## Workflow

1. Start the Studio and drop an original video into the Media panel.
2. Choose the render engine, output preset, crop policy, model, batch size, and settings.
3. Render a short preview and inspect it in the viewer.
4. Adjust settings as needed, then render the full video.
5. Use **Reprocess post only** to change post-processing without rerunning the AI restoration.

Each job is stored in its own directory under `outputs\`, including output media and logs.

## Settings notes

- Temporal batches follow SeedVR2's `4n+1` rule. Larger batches can improve consistency but use more VRAM.
- Color correction is part of the main SeedVR2 render. `none` leaves colors unchanged; `lab` is the general-purpose matching mode.
- SageAttention 2 is installed and preferred by default. Missing accelerated attention backends fall through to another available option and finally SDPA. See the [SageAttention guide](docs/SAGEATTENTION.md) for verification and repair steps.
- Leave VAE tiling off unless VRAM is insufficient; it saves memory but reduces speed.
- TensorRT uses **Optimized Fast** automatically; every job records the requested and actual decoder in its manifests and log.
- Skin finishing is a non-generative post effect that enhances existing skin pixels; it cannot recreate missing facial identity detail.

## Project layout

- `web/` — JavaScript Studio interface.
- `api_server.py` — FastAPI service.
- `seedvr_studio/` — rendering and legacy Gradio integration.
- `tools/` — TensorRT, assembly, post-processing, and diagnostics.
- `tensorrt_backend/` — optional native TensorRT sources.
- `scripts/` — one-click setup, launcher, model download, verification, and engine preparation scripts.
- `vendor/seedvr2/` — the compatible Apache-2.0 SeedVR2 integration required by the Studio.

## License

The Studio source is released under the MIT License. SeedVR2 and runtime components retain their upstream licenses; see [third-party notices](THIRD_PARTY_NOTICES.md).
