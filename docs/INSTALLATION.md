# Installation guide

## Supported setup

The packaged installer currently targets:

- Windows 11
- An NVIDIA RTX GPU with a current driver
- At least 35 GB of free disk space for the environment, models, temporary ONNX files, and TensorRT engines
- An internet connection for the first installation

TensorRT RTX engines are built for the GPU in the computer running the installer. Do not copy RTX plan files between different GPU models or TensorRT versions.

## One-click installation

1. Download or clone the repository.
2. Double-click **Install SeedVR Studio.bat**.
3. Leave the installer window open. It installs or checks Python 3.12, FFmpeg, CUDA PyTorch, the included compatible SeedVR2 integration, SageAttention 2, Triton for Windows, TensorRT RTX, ONNX tools, the default model and VAE, and four TensorRT engines.
4. When it reports success, double-click **Launch SeedVR Studio Pro.bat**.

The Pro launcher also detects an incomplete setup and starts the installer. Setup is resumable: completed model downloads and valid engines are skipped.

## Optional installer switches

Run these from PowerShell only if needed:

~~~powershell
.\scripts\install.ps1 -Repair
.\scripts\install.ps1 -SkipTensorRT
.\scripts\install.ps1 -SkipModels
~~~

**SkipTensorRT** leaves only SeedVR2 Legacy usable. **SkipModels** delays model downloads until a model is first used. A complete normal installation uses neither switch.

## Why engines are built locally

TensorRT plan files are tied to the GPU architecture and runtime version. The repository includes the exporter and builder, not another computer's plans. The installer creates:

- vae_encoder_5f_tile512.rtxplan
- vae_encoder_21f_tile512.rtxplan
- vae_decoder_tile_512_5f.rtxplan
- vae_decoder_tile_256_21f.rtxplan

If setup stops during this stage, run it again. Existing valid plans are retained.

## Logs and troubleshooting

The installer log is saved to **outputs\install.log**. Render logs are saved inside project directories under **outputs**.

Common failures:

- **No NVIDIA driver detected:** install or update the NVIDIA driver, restart Windows, and rerun setup.
- **Not enough disk space:** clear space and rerun. Partial model downloads resume.
- **Launch reports that the app window did not open:** the server often did start. Older launchers required an Edge window handle that Windows 11 does not always expose, then shut the server down. Use **Launch SeedVR Studio Pro.bat** (not the installer). If the UI still vanishes, open http://127.0.0.1:7870/ and check **outputs\js_server_error.log**.
- **TensorRT build failure:** close GPU-heavy programs, confirm the NVIDIA driver is current, then rerun.
- **SageAttention verification failure:** follow the [SageAttention guide](SAGEATTENTION.md).
- **FFmpeg still missing after winget:** restart Windows so the system PATH refreshes, then rerun.

The installer does not require a separate full CUDA Toolkit. The Python CUDA and TensorRT packages provide the runtime used by the Studio.


### If TensorRT export appears hung

The first TensorRT profile performs a fixed-shape ONNX export and can take several minutes. The installer prints an export start message and elapsed time; leave the window open while it runs. Engine preparation is resumable, so completed `.rtxplan` files are skipped on the next run.

If you need to finish setup without TensorRT, run:

```powershell
.\scripts\install.ps1 -SkipTensorRT
```

This leaves SeedVR2 Legacy available. Run the installer again later to build missing GPU-specific engines.
