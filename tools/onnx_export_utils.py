"""Portable, observable ONNX export helpers for TensorRT engine preparation."""

from __future__ import annotations

import time
from contextlib import nullcontext
from pathlib import Path

import torch


def _math_attention_context():
    try:
        from torch.nn.attention import SDPBackend, sdpa_kernel
        return sdpa_kernel(SDPBackend.MATH)
    except (ImportError, AttributeError):
        return nullcontext()


def _portable_export(module: torch.nn.Module, args: tuple[torch.Tensor, ...], output: Path, *, legacy: bool) -> None:
    is_encoder = args[0].ndim == 5 and args[0].shape[1] == 3
    with torch.inference_mode(), torch.backends.cudnn.flags(enabled=False), _math_attention_context():
        torch.onnx.export(
            module,
            args,
            str(output),
            input_names=["video"] if is_encoder else ["latent"],
            output_names=["latent_raw"] if is_encoder else ["sample"],
            opset_version=20,
            dynamo=not legacy,
            optimize=False,
            do_constant_folding=False,
        )


def export_portable_onnx(
    module: torch.nn.Module,
    args: tuple[torch.Tensor, ...],
    output: Path,
    *,
    legacy: bool,
) -> None:
    """Export on CUDA with portable operators, falling back to CPU only on OOM."""
    print(f"Exporting ONNX (legacy tracer, portable convs) -> {output}", flush=True)
    started = time.perf_counter()
    try:
        _portable_export(module, args, output, legacy=legacy)
    except RuntimeError as exc:
        if "out of memory" not in str(exc).lower():
            raise
        print("CUDA ONNX export ran out of memory; falling back to CPU export. This may take a while.", flush=True)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        _portable_export(module.cpu(), tuple(value.cpu() for value in args), output, legacy=legacy)
    print(f"ONNX export finished in {time.perf_counter() - started:.1f}s", flush=True)
