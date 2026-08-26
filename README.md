# SeedVR Studio

A local, Topaz-style workspace for the Apache-licensed SeedVR2 restoration models. It provides:

- Video import and metadata inspection.
- Quick 5- or 9-frame samples and configurable timed preview renders.
- Original/restored comparison slider.
- Synchronized side-by-side preview players.
- Full video renders and downloadable output.
- SeedVR2 3B/7B, FP16/FP8 model selection.
- A fast non-AI demo backend for testing the interface.

This project does not use or extract Topaz model files.

## Start the app

```powershell
cd A:\seedvr2
.\scripts\run.ps1
```

The browser opens at `http://127.0.0.1:7860`.

### New JavaScript viewer (parallel preview)

The new reference-style inspection UI runs alongside Gradio and does not replace the existing renderer yet:

```powershell
& ".\Launch SeedVR Studio JS.bat"
```

For the normal one-click experience, double-click [Launch SeedVR Studio Pro.bat](<A:/seedvr2/Launch SeedVR Studio Pro.bat>). It starts the JS API in the background, waits for a healthy server, and opens the viewer automatically. If it is already running, it simply opens the existing session.

It opens at `http://127.0.0.1:7870` and provides the custom video viewer, local media loading, workspace output discovery, engine/model settings, preview/full render jobs, progress polling, cancellation, compare/side-by-side modes, frame stepping, fullscreen, zoom, and pan. The Gradio launcher remains available as a fallback during this migration.

The RTX 5090 CUDA runtime and recommended **3B FP16** model are already installed. The downloaded model files are stored in `models\SEEDVR2`.

## Preview workflow

1. Import a video.
2. Select a start time and either a quick 5/9-frame sample or a timed preview length.
3. Click **Render preview**.
4. Inspect the comparison slider and side-by-side players.
5. Adjust model/settings and repeat.
6. Click **Render full video** when satisfied.

Outputs are retained in the `outputs` directory, separated by render job.

## RTX 5090 starting settings

- Model: **3B FP16**
- Attention: **SDPA**
- Batch size: **21** initially; try 33 or 45 for longer shots
- Block swapping: **0**
- VAE tiling: **off**
- Color correction: **LAB**

Increase the temporal batch toward the shot length for better consistency and throughput. Enable VAE tiling only after an out-of-memory error. Optional SageAttention 3 or compiled kernels can be explored later for additional speed.

## Reinstall or repair

```powershell
.\scripts\setup_app.ps1
.\scripts\setup_seedvr2.ps1
```

The setup uses the Windows certificate store inside the project environment because this machine's default Python CA bundle cannot validate several package hosts.

## Notes

- Batch sizes must follow `4n+1`: 1, 5, 9, 13, 17, 21, and so on.
- Short preview clips provide less temporal context than a full render.
- The first run is slower because model files are validated and loaded.
- `sageattn_3` requires its optional Blackwell-specific package; `sdpa` is the safe installed default.
