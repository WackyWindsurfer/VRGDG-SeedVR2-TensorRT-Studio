"""Deserialize and execute a fixed-shape TensorRT-RTX engine."""

from __future__ import annotations

import argparse
from pathlib import Path

import torch
import tensorrt_rtx as trt


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("engine", type=Path)
    args = parser.parse_args()
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required")
    logger = trt.Logger(trt.Logger.WARNING)
    runtime = trt.Runtime(logger)
    engine = runtime.deserialize_cuda_engine(args.engine.read_bytes())
    if engine is None:
        raise RuntimeError("Could not deserialize TensorRT-RTX engine")
    names = [engine.get_tensor_name(i) for i in range(engine.num_io_tensors)]
    inputs = [n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT]
    outputs = [n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.OUTPUT]
    if len(inputs) != 1 or len(outputs) != 1:
        raise RuntimeError(f"Expected one input/output, got {inputs}/{outputs}")
    input_name, output_name = inputs[0], outputs[0]
    input_shape = tuple(engine.get_tensor_shape(input_name))
    output_shape = tuple(engine.get_tensor_shape(output_name))
    source = torch.randn(input_shape, device="cuda", dtype=torch.float16)
    result = torch.empty(output_shape, device="cuda", dtype=torch.float16)
    context = engine.create_execution_context()
    context.set_tensor_address(input_name, source.data_ptr())
    context.set_tensor_address(output_name, result.data_ptr())
    stream = torch.cuda.Stream()
    with torch.cuda.stream(stream):
        if not context.execute_async_v3(stream.cuda_stream):
            raise RuntimeError("TensorRT-RTX execution failed")
    stream.synchronize()
    print(f"Input: {input_name} {input_shape} {engine.get_tensor_dtype(input_name)}")
    print(f"Output: {output_name} {output_shape} {engine.get_tensor_dtype(output_name)}")
    print(f"Output range: {result.min().item():.6f} .. {result.max().item():.6f}")
    print("TensorRT-RTX engine execute: OK")


if __name__ == "__main__":
    main()
