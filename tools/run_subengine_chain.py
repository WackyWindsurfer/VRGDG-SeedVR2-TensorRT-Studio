"""Run the fixed SeedVR2 decoder sub-engines as a GPU-only chain."""

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
    w = torch.ones(length, device=device, dtype=torch.float32)
    if left:
        w[:overlap] = torch.linspace(0, 1, overlap + 1, device=device)[1:]
    if right:
        w[-overlap:] = torch.minimum(w[-overlap:], torch.linspace(1, 0, overlap + 1, device=device)[1:])
    return w


def run(engine: trt.ICudaEngine, source: torch.Tensor, stream: torch.cuda.Stream) -> torch.Tensor:
    context = engine.create_execution_context()
    names = [engine.get_tensor_name(i) for i in range(engine.num_io_tensors)]
    input_name = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT)
    output_name = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.OUTPUT)
    expected = tuple(engine.get_tensor_shape(input_name))
    if tuple(source.shape) != expected:
        raise ValueError(f"Expected {expected}, received {tuple(source.shape)}")
    output = torch.empty(tuple(engine.get_tensor_shape(output_name)), device="cuda", dtype=torch.float16)
    context.set_tensor_address(input_name, source.data_ptr())
    context.set_tensor_address(output_name, output.data_ptr())
    if not context.execute_async_v3(stream.cuda_stream):
        raise RuntimeError("TensorRT sub-engine execution failed")
    stream.synchronize()
    return output


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("latent", type=Path)
    parser.add_argument("--engine-dir", type=Path, default=Path("tensorrt_backend/artifacts"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--overlap-latent", type=int, default=16)
    args = parser.parse_args()
    payload = torch.load(args.latent, map_location="cpu", weights_only=False)
    latent = payload["latent"].to(device="cuda", dtype=torch.float16).contiguous()
    _, _, frames, height, width = latent.shape
    tile = 64
    overlap = args.overlap_latent
    ys, xs = positions(height, tile, overlap), positions(width, tile, overlap)
    out_h, out_w, out_tile = height * 8, width * 8, tile * 8
    result = torch.zeros((1, 3, frames * 4 - 3, out_h, out_w), device="cuda", dtype=torch.float32)
    weights = torch.zeros_like(result)
    logger = trt.Logger(trt.Logger.WARNING)
    runtime = trt.Runtime(logger)
    names = [
        "decoder_front_tile64.rtxplan",
        "decoder_block0_tile64.rtxplan",
        "decoder_block1_tile128.rtxplan",
        "decoder_block2_tile256.rtxplan",
        "decoder_block3_tile512.rtxplan",
        "decoder_output_tile512.rtxplan",
    ]
    engines = [runtime.deserialize_cuda_engine((args.engine_dir / n).read_bytes()) for n in names]
    if any(e is None for e in engines):
        raise RuntimeError("Could not load one or more sub-engines")
    stream = torch.cuda.Stream()
    for y in ys:
        for x0 in xs:
            tile_input = latent[:, :, :, y:y + tile, x0:x0 + tile]
            if tile_input.shape[-2:] != (tile, tile):
                tile_input = torch.nn.functional.pad(tile_input, (0, tile - tile_input.shape[-1], 0, tile - tile_input.shape[-2]))
            with torch.cuda.stream(stream):
                decoded = run(engines[0], tile_input.contiguous(), stream)
                decoded = run(engines[1], decoded, stream)
                decoded = run(engines[2], decoded, stream)
                decoded = run(engines[3], decoded, stream)
                decoded = run(engines[4], decoded, stream)
                decoded = run(engines[5], decoded, stream)
            wy = feather(out_tile, overlap * 8, y != ys[0], y != ys[-1], decoded.device)
            wx = feather(out_tile, overlap * 8, x0 != xs[0], x0 != xs[-1], decoded.device)
            window = (wy[:, None] * wx[None, :]).view(1, 1, 1, out_tile, out_tile)
            oy, ox = y * 8, x0 * 8
            result[:, :, :, oy:oy + out_tile, ox:ox + out_tile] += decoded.float() * window
            weights[:, :, :, oy:oy + out_tile, ox:ox + out_tile] += window
    result = result / weights.clamp_min(1e-6)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    torch.save(result.cpu(), args.output)
    print(f"Latent: {tuple(latent.shape)}")
    print(f"Tiles: {len(ys) * len(xs)} ({ys} × {xs})")
    print(f"RGB output: {tuple(result.shape)}")
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
