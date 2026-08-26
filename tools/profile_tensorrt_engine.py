"""Collect TensorRT-RTX per-layer timing for a fixed engine."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
import tensorrt_rtx as trt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("engine", type=Path)
    parser.add_argument("--iterations", type=int, default=10)
    args = parser.parse_args()
    logger = trt.Logger(trt.Logger.WARNING)
    runtime = trt.Runtime(logger)
    engine = runtime.deserialize_cuda_engine(args.engine.read_bytes())
    if engine is None:
        raise RuntimeError("Could not deserialize engine")
    names = [engine.get_tensor_name(i) for i in range(engine.num_io_tensors)]
    input_name = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT)
    output_name = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.OUTPUT)
    source = torch.randn(tuple(engine.get_tensor_shape(input_name)), device="cuda", dtype=torch.float16)
    result = torch.empty(tuple(engine.get_tensor_shape(output_name)), device="cuda", dtype=torch.float16)
    context = engine.create_execution_context()
    context.set_tensor_address(input_name, source.data_ptr())
    context.set_tensor_address(output_name, result.data_ptr())
    context.enqueue_emits_profile = True
    context.profiler = trt.Profiler()
    stream = torch.cuda.Stream()
    for _ in range(args.iterations):
        with torch.cuda.stream(stream):
            if not context.execute_async_v3(stream.cuda_stream):
                raise RuntimeError("Execution failed")
        stream.synchronize()
    context.report_to_profiler()
    print(f"Profiled {args.iterations} iterations: {args.engine}")
    print("The TensorRT-RTX profiler reports per-layer timings above when supported by the runtime.")


if __name__ == "__main__":
    main()
