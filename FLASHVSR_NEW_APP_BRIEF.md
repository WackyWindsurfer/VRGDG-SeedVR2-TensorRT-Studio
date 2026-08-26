# VRGDG FlashVSR Studio — New Project Brief

## Purpose

Create a new, standalone VRGDG video upscaling application for FlashVSR v1.1.
This should be treated as a separate project from the existing VRGDG SeedVR2
TensorRT Studio. Do not modify the SeedVR2 application or its decoder code
while developing this app.

The goal is a practical Windows desktop/local web app with a workflow similar
to SeedVR2 Studio: choose an input video, configure upscale/restoration
settings, run the model, preserve audio, show progress, and save the result.

## Why a separate app/repository

FlashVSR has a different model architecture, Python/CUDA dependency set, model
weights, resolution rules, and attention backend from SeedVR2. Its sparse
attention build may be GPU-specific. Isolating it prevents experimental
dependencies or model failures from destabilizing the working SeedVR2 Studio.

Suggested repository name:

`VRGDG-FlashVSR-Studio`

Do not copy the SeedVR2 TensorRT decoder implementation as the FlashVSR
inference path. Reuse ideas and, if useful later, small generic media/UI
utilities only after the standalone implementation works.

## Research findings

FlashVSR is a one-step streaming diffusion video super-resolution model. Its
main components are:

- distilled streaming inference;
- locality-constrained sparse attention (LCSA);
- a tiny conditional decoder for fast reconstruction;
- Wan 2.1-based components and FlashVSR-specific weights.

The official project reports approximately 17 FPS for 768×1408 video on one
A100 and up to approximately 12× speedup over prior one-step diffusion VSR
models. These are author-reported reference numbers, not guarantees for the
target workstation.

Official repository:

https://github.com/OpenImagingLab/FlashVSR

The official README recommends FlashVSR primarily for 4× video super-resolution
and recommends v1.1 for improved stability and fidelity. The repository lists
Python 3.11.13, separate model weights, and the Block-Sparse-Attention
dependency.

Important compatibility warning: the official repository confirms the sparse
attention backend on A100/A800 and H200, but says RTX 40/50 compatibility and
performance are unknown. Do not assume the advertised A100 speed applies to a
consumer RTX card. Benchmark the actual GPU.

The official repository also warns that third-party implementations missing
LCSA can have noticeably worse quality and more artifacts at high resolution.
The first implementation or benchmark must identify whether the full LCSA path
is active.

The official FlashVSR repo recommends 4×. NVIDIA's FlashDreams integration
provides 2× sparse presets and a 4× scale option, so the new app should treat
2× and 4× as explicit experimental settings rather than assuming they are
identical paths.

Useful NVIDIA reference implementation:

https://github.com/NVIDIA/flashdreams/blob/main/docs/source/models/flashvsr.rst

## Initial scope

### Required first version

- Windows-oriented local app.
- Input video selection.
- Output directory and output filename.
- FlashVSR v1.1 model selection.
- 2× and 4× scale controls, clearly labeling 4× as the upstream-recommended
  mode and 2× as a separately validated mode.
- Chunk size control, with a safe default such as 8 frames.
- Sparse-ratio choice where supported:
  - 2.0: safer/stability-oriented preset;
  - 1.5: faster experimental preset.
- Progress reporting with phase names and elapsed time.
- Audio preservation/remuxing.
- Cancellation that terminates child inference cleanly.
- Output dimension reporting and validation.
- Log capture for model loading, attention backend, GPU, scale, chunk size,
  output size, and timing.
- Clear error messages for missing weights, missing sparse-attention backend,
  unsupported GPU/runtime, VRAM/OOM, and failed output encoding.

### Defer until the basic app works

- BFVR-STC face restoration.
- SeedVR2 integration.
- TensorRT conversion of FlashVSR.
- Multi-GPU support.
- Automatic face detection or face compositing.
- Cloud/API execution.
- Automatic model downloading without an explicit user action.

## Suggested architecture

Use a separate environment and repository with a small process boundary:

```text
VRGDG-FlashVSR-Studio/
  app.py or server entrypoint
  web/                         UI assets
  flashvsr_backend/            wrapper around official inference code
  tools/
    probe_video.py
    remux_audio.py
    benchmark_flashvsr.py
  models/                      ignored or separately configured
  runs/                        ignored output/log directory
  requirements or environment files
  README.md
  FLASHVSR_SETUP.md
```

Prefer invoking the official or minimally modified FlashVSR inference pipeline
as a child process from the UI/backend. This keeps CUDA/model crashes isolated,
makes cancellation possible, and allows the UI to parse structured progress
events.

The backend should expose a stable internal contract such as:

```text
run(input_path, output_path, scale, chunk_size, sparse_ratio, preset)
```

Do not mix FlashVSR latent tensors with SeedVR2 latent files. They are separate
model pipelines and should have separate cache/output formats.

## Resolution and media rules to validate

The app must probe the input dimensions and calculate the actual output size.
FlashVSR's resolution behavior is not the same as SeedVR2's SideResize and
TensorRT padding rules.

The NVIDIA reference documentation describes output dimensions as being based
on the scaled dimensions rounded/cropped to 128-pixel multiples. The app must
display the actual produced dimensions and must not silently claim an exact
requested size if the model center-crops or pads.

Test at least:

- 16:9 landscape;
- portrait video;
- odd dimensions;
- dimensions not divisible by 128 after scaling;
- short clips shorter than one chunk;
- clips with audio;
- clips with variable frame rate if supported;
- long clips crossing multiple chunks.

## Benchmark plan before UI polish

Use one fixed representative clip and record:

- input dimensions and frame count;
- output dimensions and frame count;
- GPU model and VRAM;
- FlashVSR version and weight variant;
- sparse ratio and chunk size;
- whether LCSA/block-sparse attention is active;
- model load time;
- inference time;
- encode/remux time;
- total wall time;
- peak VRAM;
- visual artifacts, temporal flicker, missing frames, and face changes.

Compare at minimum:

1. FlashVSR v1.1 sparse ratio 2.0;
2. FlashVSR v1.1 sparse ratio 1.5;
3. dense/full-attention path if the hardware can run it;
4. a non-generative 4× SPAN baseline.

Do not use the A100 headline FPS as the app's ETA formula. Derive ETA from
measured progress on the current GPU and settings.

## Quality and safety checks

The app should reject or flag:

- missing output files;
- frame-count changes unless explicitly expected;
- silent audio loss;
- unexpected output dimensions;
- NaN/Inf tensors if accessible at the wrapper boundary;
- obvious first-frame/last-frame discontinuities;
- chunk-boundary flicker;
- model output with severe color shift or hallucinated faces.

Save a run manifest containing settings, model version, backend, input probe
metadata, output metadata, and timing. Keep failed runs and logs easy to find.

## BFVR-STC research note

BFVR-STC should be a separate companion project or later optional sidecar, not
part of the first FlashVSR implementation.

Official repository:

https://github.com/Dixin-Lab/BFVR-STC

It targets blind face video restoration plus brightness and pixel
de-flickering. Its official inference scripts are:

- `scripts/infer_bfvr.py`;
- `scripts/infer_deflicker.py`;
- `scripts/infer_deflickersd.py`.

It uses a separate environment, dlib, FFmpeg, face-oriented processing, and a
CodeFormer-derived codebase. It is not a drop-in full-frame upscaler. A future
BFVR app would need face detection, tracking, crop restoration, temporal
consistency, and compositing back into the source video. Identity drift and
over-restoration must be evaluated carefully.

## Licensing and distribution

Check the licenses of the FlashVSR repository, weights, Block-Sparse-Attention,
any third-party wrapper, and all bundled media utilities before packaging or
redistributing the app.

REAL Video Enhancer is useful as a SPAN/TensorRT comparison reference, but its
repository is AGPL-3.0. Do not embed its code into this new app without making
an explicit licensing decision.

REAL Video Enhancer reference:

https://github.com/TNTwise/REAL-Video-Enhancer

## Rules for the first Codex session

1. Start by creating the new project in a separate folder/repository.
2. Do not edit `A:\seedvr2` or the existing SeedVR2 Studio files.
3. Inspect the target GPU, Python version, CUDA version, and available disk/RAM.
4. Read the official FlashVSR README and inference scripts before designing the
   wrapper.
5. Build a command-line smoke test before building the web UI.
6. Validate one short clip end-to-end before downloading or caching large
   models unnecessarily.
7. Keep model weights and generated videos out of Git.
8. Do not claim real-time or 12× speed until measured on the target hardware.
9. Preserve the original video and audio; write outputs to a new run folder.
10. Keep BFVR-STC out of scope until FlashVSR's general VSR path is stable.

## Current recommendation

Build FlashVSR as a standalone app first. The model is the most credible fast
alternative to evaluate, but the sparse-attention compatibility warning means
the first milestone is a hardware/quality benchmark, not a production UI.
Treat BFVR-STC as a separate face-restoration tool that may later be chained
after FlashVSR or SeedVR2 for face-specific finishing.

