"""Compare PyTorch and TensorRT fixed-profile VAE encoder outputs."""

from __future__ import annotations

import sys
from pathlib import Path

import torch
import tensorrt_rtx as trt

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / "vendor" / "seedvr2"
sys.path.insert(0, str(VENDOR))
from src.core.generation_utils import prepare_runner, setup_generation_context  # noqa: E402
from src.core.model_loader import materialize_model  # noqa: E402
from src.models.video_vae_v3.modules.types import MemoryState  # noqa: E402
from src.models.video_vae_v3.modules.causal_inflation_lib import InflatedCausalConv3d  # noqa: E402
from src.utils.debug import Debug  # noqa: E402
from src.utils.model_registry import DEFAULT_DIT, DEFAULT_VAE  # noqa: E402


def configure(vae):
    vae.disable_slicing()
    vae.set_memory_limit(None, None)
    for module in vae.modules():
        if isinstance(module, InflatedCausalConv3d):
            module.set_memory_limit(float("inf")); module.set_memory_device(None)
        if hasattr(module, "slicing"):
            module.slicing = False


def main():
    device = torch.device("cuda")
    debug = Debug(enabled=True)
    ctx = setup_generation_context(dit_device=device, vae_device=device,
                                   tensor_offload_device=None, debug=debug)
    ctx["compute_dtype"] = torch.float16
    runner, _ = prepare_runner(
        dit_model=DEFAULT_DIT, vae_model=DEFAULT_VAE,
        model_dir=str(ROOT / "models" / "SEEDVR2"), debug=debug, ctx=ctx,
        block_swap_config={"blocks_to_swap": 0, "swap_io_components": False, "offload_device": None},
        attention_mode="sdpa",
    )
    materialize_model(runner, "vae", device, runner.config, debug)
    vae = runner.vae.eval(); configure(vae)
    video = torch.randn(1, 3, 5, 64, 64, device=device, dtype=torch.float16)
    with torch.inference_mode():
        pt = vae.encoder(video, memory_state=MemoryState.DISABLED)
        if vae.quant_conv is not None:
            pt = vae.quant_conv(pt, memory_state=MemoryState.DISABLED)

    runtime = trt.Runtime(trt.Logger(trt.Logger.WARNING))
    engine = runtime.deserialize_cuda_engine((ROOT / "tensorrt_backend/artifacts/vae_encoder_5f_64.rtxplan").read_bytes())
    names = [engine.get_tensor_name(i) for i in range(engine.num_io_tensors)]
    inp = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.INPUT)
    out = next(n for n in names if engine.get_tensor_mode(n) == trt.TensorIOMode.OUTPUT)
    trt_out = torch.empty_like(pt)
    context = engine.create_execution_context()
    context.set_tensor_address(inp, video.data_ptr()); context.set_tensor_address(out, trt_out.data_ptr())
    stream = torch.cuda.current_stream()
    if not context.execute_async_v3(stream.cuda_stream):
        raise RuntimeError("TensorRT encoder execution failed")
    stream.synchronize()
    diff = (pt.float() - trt_out.float()).abs()
    print(f"PyTorch shape: {tuple(pt.shape)}")
    print(f"TensorRT shape: {tuple(trt_out.shape)}")
    print(f"max_abs={diff.max().item():.6f} mean_abs={diff.mean().item():.6f} rmse={diff.square().mean().sqrt().item():.6f}")
    print(f"pt_range={pt.min().item():.6f}..{pt.max().item():.6f} trt_range={trt_out.min().item():.6f}..{trt_out.max().item():.6f}")


if __name__ == "__main__":
    main()
