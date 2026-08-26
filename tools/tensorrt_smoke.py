"""Build and execute a tiny TensorRT-RTX engine to validate the toolchain."""

from __future__ import annotations

import numpy as np
import torch
import tensorrt_rtx as trt


def main() -> None:
    logger = trt.Logger(trt.Logger.WARNING)
    builder = trt.Builder(logger)
    # TensorRT-RTX networks use explicit shapes by default; unlike older
    # TensorRT releases there is no EXPLICIT_BATCH flag to pass here.
    network = builder.create_network()
    input_tensor = network.add_input("input", trt.DataType.FLOAT, (1, 4))
    identity = network.add_identity(input_tensor)
    identity.get_output(0).name = "output"
    network.mark_output(identity.get_output(0))

    config = builder.create_builder_config()
    config.set_memory_pool_limit(trt.MemoryPoolType.WORKSPACE, 64 * 1024 * 1024)
    engine_blob = builder.build_serialized_network(network, config)
    if engine_blob is None:
        raise RuntimeError("TensorRT failed to build the smoke-test engine")

    runtime = trt.Runtime(logger)
    engine = runtime.deserialize_cuda_engine(engine_blob)
    if engine is None:
        raise RuntimeError("TensorRT failed to deserialize the smoke-test engine")

    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is unavailable; TensorRT runtime test cannot execute")
    context = engine.create_execution_context()
    source = torch.arange(4, dtype=torch.float32, device="cuda").reshape(1, 4)
    result = torch.empty_like(source)
    context.set_tensor_address("input", int(source.data_ptr()))
    context.set_tensor_address("output", int(result.data_ptr()))
    stream = torch.cuda.Stream()
    with torch.cuda.stream(stream):
        if not context.execute_async_v3(stream.cuda_stream):
            raise RuntimeError("TensorRT execution returned failure")
    stream.synchronize()
    if not torch.equal(source, result):
        raise RuntimeError(f"TensorRT output mismatch: {result.cpu().tolist()}")

    print(f"TensorRT-RTX: {trt.__version__}")
    print(f"Bindings: {engine.num_io_tensors} IO tensor(s)")
    print(f"Input dtype: {engine.get_tensor_dtype('input')}")
    print(f"Output dtype: {engine.get_tensor_dtype('output')}")
    # Keep NumPy imported here as a dependency sanity check for upcoming
    # ONNX/export scripts; execution will use CUDA buffers in the next stage.
    print(f"NumPy: {np.__version__}")
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print("TensorRT engine build/execute: OK")


if __name__ == "__main__":
    main()
