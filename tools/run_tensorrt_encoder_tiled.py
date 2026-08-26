"""Run a fixed-profile TensorRT VAE encoder over overlapping spatial tiles."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
import tensorrt_rtx as trt


def positions(length: int, tile: int, overlap: int) -> list[int]:
    if length <= tile:
        return [0]
    stride = tile - overlap
    values = list(range(0, length - tile + 1, stride))
    if values[-1] != length - tile:
        values.append(length - tile)
    return values


def feather(length: int, overlap: int, left: bool, right: bool, device: torch.device) -> torch.Tensor:
    """Build a separable ramp so overlapping encoder tiles cross-fade smoothly."""
    weight = torch.ones(length, device=device, dtype=torch.float32)
    if left and overlap:
        weight[:overlap] = torch.linspace(0.0, 1.0, overlap + 1, device=device)[1:]
    if right and overlap:
        weight[-overlap:] = torch.minimum(
            weight[-overlap:], torch.linspace(1.0, 0.0, overlap + 1, device=device)[1:]
        )
    return weight


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("engine", type=Path)
    parser.add_argument("video", type=Path, help="Torch tensor [1,3,T,H,W] or [T,3,H,W] in [0,1].")
    parser.add_argument("--tile-pixels", type=int, default=512)
    parser.add_argument("--overlap-pixels", type=int, default=96)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scaling-factor", type=float, default=0.9152)
    args = parser.parse_args()
    payload = torch.load(args.video, map_location="cpu", weights_only=False)
    video = payload["video"] if isinstance(payload, dict) and "video" in payload else payload
    if video.ndim == 4:
        video = video.unsqueeze(0)
    if video.ndim != 5 or video.shape[1] != 3:
        raise ValueError(f"Expected [1,3,T,H,W] or [T,3,H,W], got {tuple(video.shape)}")
    video = video.to(device="cuda", dtype=torch.float16).contiguous()
    _, _, frames, height, width = video.shape
    if frames not in (5, 21):
        raise ValueError("Encoder profiles currently support temporal batches 5 and 21")
    tile = args.tile_pixels
    overlap = args.overlap_pixels
    if tile != 512 or overlap <= 0 or overlap >= tile:
        raise ValueError("Current encoder engine requires a 512px tile and positive overlap below 512")

    runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
    engine = runtime.deserialize_cuda_engine(args.engine.read_bytes())
    if engine is None:
        raise RuntimeError("Could not deserialize TensorRT encoder engine")
    names = [engine.get_tensor_name(i) for i in range(engine.num_io_tensors)]
    input_name = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT)
    output_name = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.OUTPUT)
    expected = tuple(engine.get_tensor_shape(input_name))
    if expected != (1, 3, frames, 512, 512):
        raise ValueError(f"Engine input {expected} does not match video temporal size {frames}")

    ys, xs = positions(height, tile, overlap), positions(width, tile, overlap)
    padded_h, padded_w = max(height, ys[-1] + tile), max(width, xs[-1] + tile)
    padded = torch.nn.functional.pad(video, (0, padded_w - width, 0, padded_h - height))
    latent_h, latent_w = height // 8, width // 8
    out_h, out_w = padded_h // 8, padded_w // 8
    latent_frames = frames // 4 + 1
    raw_result = torch.zeros((1, 32, latent_frames, out_h, out_w), device="cuda", dtype=torch.float32)
    weights = torch.zeros_like(raw_result)
    overlap_latent = overlap // 8
    context = engine.create_execution_context()
    stream = torch.cuda.current_stream()
    for y in ys:
        for x in xs:
            tile_input = padded[:, :, :, y:y + tile, x:x + tile].contiguous()
            tile_output = torch.empty((1, 32, latent_frames, tile // 8, tile // 8), device="cuda", dtype=torch.float16)
            context.set_tensor_address(input_name, tile_input.data_ptr())
            context.set_tensor_address(output_name, tile_output.data_ptr())
            if not context.execute_async_v3(stream.cuda_stream):
                raise RuntimeError(f"TensorRT encoder failed at tile y={y}, x={x}")
            stream.synchronize()
            ly, lx = y // 8, x // 8
            wy = feather(tile // 8, overlap_latent, y != ys[0], y != ys[-1], tile_output.device)
            wx = feather(tile // 8, overlap_latent, x != xs[0], x != xs[-1], tile_output.device)
            window = (wy[:, None] * wx[None, :]).view(1, 1, 1, tile // 8, tile // 8)
            raw_result[:, :, :, ly:ly + tile // 8, lx:lx + tile // 8] += tile_output.float() * window
            weights[:, :, :, ly:ly + tile // 8, lx:lx + tile // 8] += window
    raw = (raw_result / weights.clamp_min(1e-6))[:, :, :, :latent_h, :latent_w]
    # The 32 channels are posterior mean/log-variance pairs. SeedVR2's
    # wrapper uses the posterior mode for its latent, so retain the first 16.
    latent = (raw[:, :16] * args.scaling_factor).to(dtype=torch.float16).cpu()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"latent": latent, "raw": raw.cpu(), "original_frames": frames}, args.output)
    print(f"Video: {tuple(video.shape)}")
    print(f"Tiles: {len(ys) * len(xs)}")
    print(f"Raw encoder output: {tuple(raw.shape)}")
    print(f"Latent: {tuple(latent.shape)}")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
