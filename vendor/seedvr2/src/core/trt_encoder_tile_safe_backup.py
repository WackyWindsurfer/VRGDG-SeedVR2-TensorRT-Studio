# Modified by VRGDG SeedVR2 TensorRT Studio: adds TensorRT latent capture/encoder handoff integration.
"""Optional fixed-profile TensorRT VAE encoder used by SeedVR Studio."""

from __future__ import annotations

import gc
from pathlib import Path
from threading import Lock

import torch
import tensorrt_rtx as trt


ROOT = Path(__file__).resolve().parents[4]
ARTIFACTS = ROOT / "tensorrt_backend" / "artifacts"
_ENCODE_LOCK = Lock()


def _engine(frames: int):
    if frames == 5:
        path = ARTIFACTS / "vae_encoder_5f_tile512.rtxplan"
    elif frames == 21:
        path = ARTIFACTS / "vae_encoder_21f_tile512.rtxplan"
    else:
        raise ValueError("TensorRT VAE encoder supports temporal batches 5 and 21")
    if not path.exists():
        raise FileNotFoundError(f"Missing TensorRT VAE encoder engine: {path}")
    runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
    engine = runtime.deserialize_cuda_engine(path.read_bytes())
    if engine is None:
        raise RuntimeError(f"Could not deserialize TensorRT encoder: {path}")
    names = [engine.get_tensor_name(i) for i in range(engine.num_io_tensors)]
    input_name = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT)
    output_name = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.OUTPUT)
    stream = torch.cuda.Stream()
    return runtime, engine, input_name, output_name, stream


def _positions(length: int, tile: int, overlap: int) -> list[int]:
    if length <= tile:
        return [0]
    stride = tile - overlap
    values = list(range(0, length - tile + 1, stride))
    if values[-1] != length - tile:
        values.append(length - tile)
    return values


def _feather(length: int, overlap: int, left: bool, right: bool, device: torch.device) -> torch.Tensor:
    """Cross-fade overlapping latent tiles instead of introducing hard averaging edges."""
    weight = torch.ones(length, device=device, dtype=torch.float32)
    if left and overlap:
        weight[:overlap] = torch.linspace(0.0, 1.0, overlap + 1, device=device)[1:]
    if right and overlap:
        weight[-overlap:] = torch.minimum(
            weight[-overlap:], torch.linspace(1.0, 0.0, overlap + 1, device=device)[1:]
        )
    return weight


@torch.inference_mode()
def encode(sample: torch.Tensor) -> torch.Tensor:
    """Encode [B,3,T,H,W] to raw posterior mean [B,16,T/4,H/8,W/8]."""
    if sample.ndim != 5 or sample.shape[0] != 1 or sample.shape[1] != 3:
        raise ValueError(f"TensorRT encoder expects [1,3,T,H,W], got {tuple(sample.shape)}")
    _, _, frames, height, width = sample.shape
    if height % 8 or width % 8:
        raise ValueError("TensorRT encoder input dimensions must be divisible by 8")
    runtime, engine, input_name, output_name, stream = _engine(int(frames))

    source = sample.to(device="cuda", dtype=torch.float16).contiguous()
    tile, overlap = 512, 96
    ys, xs = _positions(height, tile, overlap), _positions(width, tile, overlap)
    padded_h, padded_w = max(height, ys[-1] + tile), max(width, xs[-1] + tile)
    source = torch.nn.functional.pad(source, (0, padded_w - width, 0, padded_h - height))
    latent_frames = frames // 4 + 1
    latent_h, latent_w = height // 8, width // 8
    raw_h, raw_w = padded_h // 8, padded_w // 8
    result = torch.zeros((1, 32, latent_frames, raw_h, raw_w), device="cuda", dtype=torch.float32)
    weights = torch.zeros_like(result)
    overlap_latent = overlap // 8
    with _ENCODE_LOCK, torch.cuda.stream(stream):
        for y in ys:
            for x in xs:
                # TensorRT-RTX can retain mutable state between spatial tiles.
                # Isolate encoder tiles so a later temporal batch cannot inherit
                # a corrupted tile state, without changing tile geometry or
                # decoder performance.
                context = engine.create_execution_context()
                if context is None:
                    raise RuntimeError(f"TensorRT could not create encoder context for tile y={y}, x={x}")
                tile_input = source[:, :, :, y:y + tile, x:x + tile].contiguous()
                # TensorRT-RTX can leave portions of an output allocation
                # unwritten. Zero initialization prevents recycled CUDA memory
                # from a prior tile/batch appearing as finite grid corruption.
                tile_output = torch.zeros((1, 32, latent_frames, 64, 64), device="cuda", dtype=torch.float16)
                context.set_tensor_address(input_name, tile_input.data_ptr())
                context.set_tensor_address(output_name, tile_output.data_ptr())
                if not context.execute_async_v3(stream.cuda_stream):
                    raise RuntimeError(f"TensorRT VAE encoder failed at tile y={y}, x={x}")
                stream.synchronize()
                finite = torch.isfinite(tile_output).all().item()
                peak = float(tile_output.float().abs().amax().item()) if finite else float("inf")
                if not finite or peak > 128.0:
                    # Retry the affected tile once with a brand-new context.
                    # This keeps the engine cached while preventing corrupt
                    # TensorRT state from poisoning an entire temporal batch.
                    context = engine.create_execution_context()
                    if context is None:
                        raise RuntimeError("TensorRT could not recreate the VAE encoder context")
                    tile_output = torch.zeros((1, 32, latent_frames, 64, 64), device="cuda", dtype=torch.float16)
                    context.set_tensor_address(input_name, tile_input.data_ptr())
                    context.set_tensor_address(output_name, tile_output.data_ptr())
                    if not context.execute_async_v3(stream.cuda_stream):
                        raise RuntimeError(f"TensorRT VAE encoder retry failed at tile y={y}, x={x}")
                    stream.synchronize()
                    finite = torch.isfinite(tile_output).all().item()
                    peak = float(tile_output.float().abs().amax().item()) if finite else float("inf")
                    if not finite or peak > 128.0:
                        raise RuntimeError(
                            f"TensorRT VAE encoder produced invalid values at tile y={y}, x={x} "
                            f"after retry (peak={peak:g})"
                        )
                ly, lx = y // 8, x // 8
                wy = _feather(64, overlap_latent, y != ys[0], y != ys[-1], tile_output.device)
                wx = _feather(64, overlap_latent, x != xs[0], x != xs[-1], tile_output.device)
                window = (wy[:, None] * wx[None, :]).view(1, 1, 1, 64, 64)
                result[:, :, :, ly:ly + 64, lx:lx + 64] += tile_output.float() * window
                weights[:, :, :, ly:ly + 64, lx:lx + 64] += window
    encoded = (result / weights.clamp_min(1e-6))[:, :16, :, :latent_h, :latent_w]
    if not torch.isfinite(encoded).all().item():
        raise RuntimeError("TensorRT VAE encoder produced non-finite assembled latents")
    # Full-resolution testing proved that reusing this TensorRT-RTX engine
    # changes one spatial tile in later temporal batches even with fresh
    # contexts and zeroed outputs. The engine must die with its batch.
    del context, engine, runtime, stream
    gc.collect()
    return encoded.to(sample.dtype)

def release() -> None:
    """Release residual encoder allocations before the DiT phase is loaded."""
    with _ENCODE_LOCK:
        if torch.cuda.is_available():
            torch.cuda.synchronize()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
