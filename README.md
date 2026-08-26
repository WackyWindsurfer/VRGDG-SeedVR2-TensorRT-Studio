# VRGDG SeedVR2 TensorRT Studio

A local, professional-style video restoration workspace for SeedVR2. The primary interface is a custom JavaScript UI backed by a local FastAPI service, with TensorRT VAE acceleration available for fast previews and full renders.

## What it does

- Import an original video and inspect its metadata.
- Render short previews or the complete restored video.
- View Original, Restored, Compare, and synchronized Side by side modes.
- Use one shared play button, frame stepping, timeline scrubbing, fullscreen, zoom, and pan.
- Compare frames with an adjustable wipe slider.
- Choose output presets: enhancement-only at the original size, 1K/1080p, 2K/1440p, or 4K/2160p.
- Preserve the source aspect ratio or center-crop to 16:9.
- Use resumable long-video rendering. Completed chunks are retained so a failed job can retry from the last unfinished chunk.
- Apply post-processing such as sharpening, film grain, TensorRT batch-seam smoothing, and optional skin finishing.
- Reprocess post effects on an existing render without running SeedVR2 again.
- Save and restore preferred settings between sessions.
- Load previous workspace outputs and open their project folders.

The project does not include or extract Topaz model files.

## Start the Studio

### One-click launcher

Double-click **Launch SeedVR Studio Pro.bat**. It starts the local API, waits for it to become ready, and opens the Studio in your browser at:

`http://127.0.0.1:7870`

The other launchers are available for direct JS or legacy Gradio startup:

- **Launch SeedVR Studio JS.bat** — starts the JavaScript Studio directly.
- **Launch SeedVR Studio.bat** — starts the legacy Gradio interface.

### PowerShell

```powershell
cd A:\seedvr2
.\scripts\run_js.ps1
```

Use `-NoBrowser` when starting the API from an existing browser session.

## First-time setup

```powershell
cd A:\seedvr2
.\scripts\setup_app.ps1
.\scripts\setup_seedvr2.ps1
```

The setup creates `.venv`, installs the Python dependencies, and downloads the SeedVR2 source dependencies. Model weights are kept in `models\` and are downloaded/validated separately; they are not committed to GitHub.

## Typical workflow

1. Start **Launch SeedVR Studio Pro.bat**.
2. Drop an original video into the Media panel.
3. Select the backend, output size, crop policy, model, batch size, and other settings.
4. Render a short preview and inspect it in the viewer.
5. Adjust settings and render another preview until the result is satisfactory.
6. Render the full video.
7. Use **Reprocess post only** when you want to change post-processing without repeating the AI restoration.

The restored output and logs are stored in a separate directory under `outputs\` for each job.

## Main settings

- **Backend:** SeedVR2 + TensorRT is the recommended fast path; SeedVR2 (Legacy) is the standard PyTorch path and can be substantially slower.
- **Output size:** Original enhancement only, 1K/1080p, 2K/1440p, or 4K/2160p.
- **Crop/aspect:** Preserve the original aspect ratio or center-crop to 16:9.
- **Temporal batch:** Values follow SeedVR2's `4n+1` pattern, such as 1, 5, 9, 13, 17, 21, 33, and 45. Larger batches may improve consistency but use more VRAM.
- **Color correction:** `none` leaves colors unchanged. `lab` is the general-purpose matching option; the wavelet modes are useful when preserving local detail or controlling saturation is more important.
- **Attention:** SageAttention 2 is preferred when installed. The backend automatically falls through to another available accelerated option and finally SDPA.
- **VAE tiling:** Leave off unless VRAM is insufficient; it reduces memory use at the cost of speed.
- **Resumable long-video render:** Off by default. When enabled, long videos are processed in chunks and can resume after a failure. The UI reports the failure reason and keeps the backend log for debugging.

## Post-processing

Post-processing runs after restoration and can be repeated without rerunning SeedVR2:

- Extra sharpening, up to strength 10.
- Film grain with adjustable intensity and saturation.
- TensorRT batch-seam smoothing, enabled by default.
- Optional skin finishing for even tone, smoothing, redness/shine reduction, blemish cleanup, mark preservation, and skin-aware microtexture.

Skin finishing is an enhancement of existing pixels; it is not a generative face-restoration model and cannot recreate missing identity detail.

## Project layout

- `web/` — JavaScript Studio interface.
- `api_server.py` — FastAPI service used by the JS UI.
- `seedvr_studio/` — rendering, media, jobs, and legacy Gradio integration.
- `tools/` — TensorRT, assembly, post-processing, and diagnostic utilities.
- `tensorrt_backend/` — optional native TensorRT integration sources.
- `scripts/` — setup and launcher scripts.

Large local assets are intentionally ignored by Git: model weights, outputs, virtual environments, TensorRT engines/caches, and the optional `third_party\` runtime directory.

## Hardware notes

The Studio is designed for local NVIDIA CUDA systems. Start with the 3B FP16 model, temporal batch 21, zero block swapping, and VAE tiling disabled. If a job runs out of VRAM, lower the temporal batch or enable VAE tiling. Longer videos do not inherently require loading the whole video into VRAM, but they take longer and are more likely to benefit from resumable chunking.

## License

The Studio source is released under the MIT License. SeedVR2 and optional runtime components retain their respective upstream licenses.
