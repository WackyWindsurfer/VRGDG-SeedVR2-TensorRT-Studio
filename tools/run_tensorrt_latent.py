"""Run a captured SeedVR2 VAE latent through a fixed TensorRT-RTX engine."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import torch
import tensorrt_rtx as trt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("engine", type=Path)
    parser.add_argument("latent", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = torch.load(args.latent, map_location="cpu", weights_only=False)
    source = payload["latent"].to(device="cuda", dtype=torch.float16).contiguous()
    logger = trt.Logger(trt.Logger.WARNING)
    runtime = trt.Runtime(logger)
    engine = runtime.deserialize_cuda_engine(args.engine.read_bytes())
    if engine is None:
        raise RuntimeError("Could not deserialize TensorRT-RTX engine")
    input_name = next(engine.get_tensor_name(i) for i in range(engine.num_io_tensors)
                      if engine.get_tensor_mode(engine.get_tensor_name(i)) == trt.TensorIOMode.INPUT)
    output_name = next(engine.get_tensor_name(i) for i in range(engine.num_io_tensors)
                       if engine.get_tensor_mode(engine.get_tensor_name(i)) == trt.TensorIOMode.OUTPUT)
    expected = tuple(engine.get_tensor_shape(input_name))
    if tuple(source.shape) != expected:
        raise ValueError(f"Latent shape {tuple(source.shape)} does not match engine {expected}")
    result = torch.empty(tuple(engine.get_tensor_shape(output_name)), device="cuda", dtype=torch.float16)
    context = engine.create_execution_context()
    context.set_tensor_address(input_name, source.data_ptr())
    context.set_tensor_address(output_name, result.data_ptr())
    stream = torch.cuda.Stream()
    with torch.cuda.stream(stream):
        start = time.perf_counter()
        if not context.execute_async_v3(stream.cuda_stream):
            raise RuntimeError("TensorRT-RTX execution failed")
    stream.synchronize()
    elapsed = time.perf_counter() - start
    print(f"Latent: {args.latent} {tuple(source.shape)}")
    print(f"Output: {tuple(result.shape)}")
    print(f"TensorRT GPU decode: {elapsed * 1000:.2f} ms")
    print(f"Output range: {result.min().item():.6f} .. {result.max().item():.6f}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        torch.save(result.cpu(), args.output)
        print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
