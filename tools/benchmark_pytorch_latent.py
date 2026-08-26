"""Benchmark the original GPU VAE decoder on a captured latent."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "vendor" / "seedvr2"))
from src.core.generation_utils import prepare_runner, setup_generation_context  # noqa: E402
from src.core.model_loader import materialize_model  # noqa: E402
from src.models.video_vae_v3.modules.types import MemoryState  # noqa: E402
from src.utils.debug import Debug  # noqa: E402
from src.utils.model_registry import DEFAULT_DIT, DEFAULT_VAE  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("latent", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = torch.load(args.latent, map_location="cpu", weights_only=False)
    latent = payload["latent"].to(device="cuda", dtype=torch.float16).contiguous()
    debug = Debug(enabled=False)
    device = torch.device("cuda")
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
    decoder = vae.decoder.eval()
    with torch.inference_mode():
        decoder(latent, memory_state=MemoryState.DISABLED)
        torch.cuda.synchronize()
        start = time.perf_counter()
        output = decoder(latent, memory_state=MemoryState.DISABLED)
        torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
    print(f"Latent: {tuple(latent.shape)}")
    print(f"Output: {tuple(output.shape)}")
    print(f"PyTorch GPU decode: {elapsed * 1000:.2f} ms")
    print(f"Output range: {output.min().item():.6f} .. {output.max().item():.6f}")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        torch.save(output.cpu(), args.output)
        print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
