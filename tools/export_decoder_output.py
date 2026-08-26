"""Export the final decoder normalization/activation/RGB projection stage."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import torch
from einops import rearrange

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "seedvr2"))
from src.core.generation_utils import prepare_runner, setup_generation_context  # noqa: E402
from src.core.model_loader import materialize_model  # noqa: E402
from src.models.video_vae_v3.modules.causal_inflation_lib import causal_norm_wrapper  # noqa: E402
from src.models.video_vae_v3.modules.types import MemoryState  # noqa: E402
from src.utils.debug import Debug  # noqa: E402
from src.utils.model_registry import DEFAULT_DIT, DEFAULT_VAE  # noqa: E402


class OutputStage(torch.nn.Module):
    def __init__(self, decoder: torch.nn.Module) -> None:
        super().__init__()
        self.norm = decoder.conv_norm_out
        self.act = decoder.conv_act
        self.conv = decoder.conv_out

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = causal_norm_wrapper(self.norm, x)
        x = self.act(x)
        return self.conv(x, memory_state=MemoryState.DISABLED)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tile-size", type=int, default=128)
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
    stage = OutputStage(vae.decoder).eval()
    source = torch.randn((1, 128, 9, args.tile_size, args.tile_size), device=device, dtype=torch.float16)
    with torch.inference_mode():
        reference = stage(source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        torch.onnx.export(stage.cpu(), (source.cpu(),), str(args.output),
                          input_names=["hidden"], output_names=["sample"],
                          opset_version=20, dynamo=True, optimize=False)
    print(f"Input: {tuple(source.shape)}")
    print(f"Output: {tuple(reference.shape)}")
    print(f"Exported: {args.output}")


if __name__ == "__main__":
    main()
