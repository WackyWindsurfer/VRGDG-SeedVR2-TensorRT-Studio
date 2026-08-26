"""Export the fixed-shape VAE decoder front (latent conditioning + mid block)."""

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


class Front(torch.nn.Module):
    def __init__(self, vae: torch.nn.Module) -> None:
        super().__init__()
        self.post = vae.post_quant_conv
        self.conv_in = vae.decoder.conv_in
        self.mid = vae.decoder.mid_block

    def forward(self, latent: torch.Tensor) -> torch.Tensor:
        x = self.post(latent, memory_state=MemoryState.DISABLED) if self.post is not None else latent
        x = self.conv_in(x, memory_state=MemoryState.DISABLED)
        return self.mid(x, memory_state=MemoryState.DISABLED)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tile-latent", type=int, default=64)
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
    front = Front(vae).eval()
    source = torch.randn((1, 16, 3, args.tile_latent, args.tile_latent), device=device, dtype=torch.float16)
    with torch.inference_mode():
        reference = front(source)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        torch.onnx.export(front.cpu(), (source.cpu(),), str(args.output),
                          input_names=["latent"], output_names=["hidden"],
                          opset_version=20, dynamo=True, optimize=False)
    print(f"Input: {tuple(source.shape)}")
    print(f"Output: {tuple(reference.shape)}")
    print(f"Exported: {args.output}")


if __name__ == "__main__":
    main()
