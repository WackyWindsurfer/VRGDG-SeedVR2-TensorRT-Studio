"""Export one fixed-shape SeedVR2 decoder up-block for TensorRT profiling."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "seedvr2"))
from src.core.generation_utils import prepare_runner, setup_generation_context  # noqa: E402
from src.core.model_loader import materialize_model  # noqa: E402
from src.models.video_vae_v3.modules.types import MemoryState  # noqa: E402
from src.utils.debug import Debug  # noqa: E402
from src.utils.model_registry import DEFAULT_DIT, DEFAULT_VAE  # noqa: E402


class BlockWrapper(torch.nn.Module):
    def __init__(self, block: torch.nn.Module) -> None:
        super().__init__()
        self.block = block

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return self.block(x, memory_state=MemoryState.DISABLED)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--block", type=int, choices=[0, 1, 2, 3], required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tile-height", type=int, default=64)
    parser.add_argument("--tile-width", type=int, default=64)
    args = parser.parse_args()
    device = torch.device("cuda")
    debug = Debug(enabled=False)
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
    vae = runner.vae.eval()
    if hasattr(vae, "disable_slicing"):
        vae.disable_slicing()
    if hasattr(vae, "set_memory_limit"):
        vae.set_memory_limit(None, None)
    decoder = vae.decoder.eval()
    captured: list[torch.Tensor] = []
    hook = decoder.up_blocks[args.block].register_forward_pre_hook(
        lambda _module, inputs: captured.append(inputs[0].detach())
    )
    latent = torch.randn((1, 16, 3, 90, 160), device=device, dtype=torch.float16)
    with torch.inference_mode():
        decoder(latent, memory_state=MemoryState.DISABLED)
    hook.remove()
    source = captured[0][:, :, :, :args.tile_height, :args.tile_width].contiguous()
    block = BlockWrapper(decoder.up_blocks[args.block]).eval()
    with torch.inference_mode():
        reference = block(source)
        block_cpu = BlockWrapper(decoder.up_blocks[args.block].cpu()).eval()
        source_cpu = source.cpu()
        args.output.parent.mkdir(parents=True, exist_ok=True)
        torch.onnx.export(
            block_cpu, (source_cpu,), str(args.output), input_names=["hidden"],
            output_names=["output"], opset_version=20, dynamo=True, optimize=False,
        )
    print(f"Block: up_blocks.{args.block}")
    print(f"Input: {tuple(source.shape)}")
    print(f"Output: {tuple(reference.shape)}")
    print(f"Exported: {args.output}")


if __name__ == "__main__":
    main()
