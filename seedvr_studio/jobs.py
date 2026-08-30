from __future__ import annotations

import time
import uuid
from html import escape
from pathlib import Path
from typing import Iterator
from urllib.parse import quote

import gradio as gr

from .backend import RenderSettings, render
from .media import MediaError, make_clip, probe
from .paths import OUTPUTS, ensure_workspace


def _inspection_player_html(before: Path, after: Path, fps: float) -> str:
    def src(path: Path) -> str:
        # Gradio 6 serves user-provided files from the gradio_api namespace.
        # The legacy /file= URL leaves custom HTML videos at 00:00/00:00.
        return "/gradio_api/file=" + quote(str(path), safe="")

    before_src = escape(src(before), quote=True)
    after_src = escape(src(after), quote=True)
    return f'''<div class="seedvr-inspector mode-compare" data-fps="{max(float(fps), 1.0):.6f}" tabindex="0">
      <div class="seedvr-inspector-toolbar">
        <button class="seedvr-fullscreen" title="Fullscreen">⛶ <span>Fullscreen</span></button>
        <div class="seedvr-mode-group" role="group" aria-label="Viewer mode">
          <button data-mode="original" title="Original only">Original</button>
          <button data-mode="restored" title="Restored only">Restored</button>
          <button data-mode="compare" class="active" title="Before/after wipe comparison">◐ Compare</button>
          <button data-mode="side" title="Synchronized side by side">▥ Side by side</button>
        </div>
        <button class="seedvr-zoom-reset" title="Reset zoom">100%</button>
      </div>
      <div class="seedvr-inspector-stage">
        <div class="seedvr-inspector-media">
          <div class="seedvr-pane seedvr-before-pane"><video class="seedvr-before" src="{before_src}" preload="metadata" playsinline></video><span class="seedvr-pane-label">Original</span></div>
          <div class="seedvr-pane seedvr-after-pane"><video class="seedvr-after" src="{after_src}" preload="metadata" playsinline muted></video><span class="seedvr-pane-label">Restored</span></div>
          <div class="seedvr-wipe-divider"><span>↔</span></div>
        </div>
        <div class="seedvr-zoom-help">Mouse wheel to zoom · drag to pan · double-click to reset</div>
      </div>
      <div class="seedvr-scrubber-row"><input class="seedvr-time" aria-label="Video position" type="range" min="0" max="0" step="0.001" value="0"><span class="seedvr-clock">00:00.000 / 00:00.000</span></div>
      <div class="seedvr-transport">
        <label>Frame <input class="seedvr-frame-number" type="number" min="0" value="0"> <span class="seedvr-frame-total">/ 0</span></label>
        <div class="seedvr-transport-buttons"><button class="seedvr-prev-frame" title="Previous frame">|◀</button><button class="seedvr-play" title="Play or pause">▶</button><button class="seedvr-next-frame" title="Next frame">▶|</button></div>
        <label class="seedvr-wipe-control">Wipe <input class="seedvr-wipe-range" type="range" min="0" max="100" value="50"><span>50%</span></label>
      </div>
      <div class="seedvr-inspector-downloads"><a href="{before_src}" download>Download original</a><a href="{after_src}" download>Download restored</a></div>
    </div>'''


def empty_inspection_player_html() -> str:
    """Keep the inspection workspace visible before the first render."""
    return '''<div class="seedvr-inspector seedvr-inspector-empty mode-compare">
      <div class="seedvr-inspector-toolbar">
        <button disabled title="Fullscreen">⛶ <span>Fullscreen</span></button>
        <div class="seedvr-mode-group" role="group" aria-label="Viewer mode">
          <button disabled>Original</button><button disabled>Restored</button>
          <button disabled class="active">◐ Compare</button><button disabled>▥ Side by side</button>
        </div>
        <button disabled class="seedvr-zoom-reset">100%</button>
      </div>
      <div class="seedvr-inspector-stage"><div class="seedvr-empty-message"><strong>No preview loaded</strong><span>Render a preview or full video to inspect it here.</span></div></div>
      <div class="seedvr-scrubber-row"><input disabled class="seedvr-time" type="range" min="0" max="0" value="0"><span class="seedvr-clock">00:00.000 / 00:00.000</span></div>
      <div class="seedvr-transport"><label>Frame <input disabled class="seedvr-frame-number" type="number" value="0"><span>/ 0</span></label><div class="seedvr-transport-buttons"><button disabled>|◀</button><button disabled>▶</button><button disabled>▶|</button></div><label class="seedvr-wipe-control">Wipe <input disabled class="seedvr-wipe-range" type="range" value="50"><span>50%</span></label></div>
    </div>'''


def describe_video(video_path: str | None):
    if not video_path:
        return "Drop a video to begin.", 0, 0
    try:
        info = probe(video_path)
        message = f"**{info.width}×{info.height}** · {info.fps:.3f} fps · {info.duration:.1f} sec · approximately {info.frames:,} frames"
        preview_max = max(0.0, info.duration - 1.0)
        return message, preview_max, min(3.0, preview_max)
    except Exception as exc:
        return f"Could not inspect video: `{exc}`", 0, 0


def _settings(resolution, max_resolution, batch_size, seed, model_label, color_correction, attention_mode, blocks_to_swap, vae_tiling, stop_before_vae, sharpen_enabled, sharpen_strength, grain_enabled, grain_intensity, grain_saturation, microtexture_enabled=False, microtexture_strength=0.60, skin_finishing_enabled=False, skin_evenness=0.25, skin_smoothing=0.20, skin_redness=0.15, skin_shine=0.15, blemish_mode="off", preserve_marks=True, seam_mode="match", seam_frames=2, decoder_mode="stable", source_fps=0.0) -> RenderSettings:
    batch = int(batch_size)
    if batch < 1 or (batch - 1) % 4:
        raise MediaError("Batch size must follow 4n+1: 1, 5, 9, 13, 17, 21…")
    return RenderSettings(int(resolution), int(max_resolution), batch, int(seed), model_label, color_correction, attention_mode, int(blocks_to_swap), bool(vae_tiling), bool(stop_before_vae), bool(sharpen_enabled), float(sharpen_strength), bool(grain_enabled), float(grain_intensity), float(grain_saturation), bool(microtexture_enabled) and bool(skin_finishing_enabled), float(microtexture_strength), bool(skin_finishing_enabled), float(skin_evenness), float(skin_smoothing), float(skin_redness), float(skin_shine), str(blemish_mode), bool(preserve_marks), str(seam_mode), max(1, min(12, int(seam_frames))), str(decoder_mode), float(source_fps))


def render_preview(video_path, backend_name, preview_start, preview_seconds, resolution, max_resolution, batch_size, seed, model_label, color_correction, attention_mode, blocks_to_swap, vae_tiling, stop_before_vae, sharpen_enabled, sharpen_strength, grain_enabled, grain_intensity, grain_saturation, microtexture_enabled, microtexture_strength, skin_finishing_enabled, skin_evenness, skin_smoothing, skin_redness, skin_shine, blemish_mode, preserve_marks, progress: gr.Progress = gr.Progress(track_tqdm=True)) -> Iterator[tuple]:
    if not video_path:
        raise MediaError("Import a video first")
    progress(0.0, desc="Preparing preview")
    ensure_workspace()
    source = Path(video_path)
    info = probe(source)
    job = OUTPUTS / f"preview-{uuid.uuid4().hex[:10]}"
    job.mkdir(parents=True)
    start = min(max(float(preview_start), 0.0), max(info.duration - 0.1, 0.0))
    length = min(float(preview_seconds), max(info.duration - start, 0.1))
    source_clip = make_clip(source, job / "source.mp4", start, length)
    output_clip = job / "restored.mp4"
    settings = _settings(resolution, max_resolution, batch_size, seed, model_label, color_correction, attention_mode, blocks_to_swap, vae_tiling, stop_before_vae, sharpen_enabled, sharpen_strength, grain_enabled, grain_intensity, grain_saturation, microtexture_enabled, microtexture_strength, skin_finishing_enabled, skin_evenness, skin_smoothing, skin_redness, skin_shine, blemish_mode, preserve_marks)
    yield "### Rendering preview…\nProgress is shown above while SeedVR2 works.", empty_inspection_player_html()
    started = time.perf_counter()

    def report(value: float, description: str) -> None:
        progress(0.04 + value * 0.90, desc=description)

    render(backend_name, source_clip, output_clip, settings, report)
    if stop_before_vae:
        latent_dir = job / "vae_latents"
        yield f"### Stopped before VAE\nLatents captured in `{latent_dir}`. No restored video was generated.", empty_inspection_player_html()
        return
    progress(0.95, desc="Building comparison preview")
    elapsed = time.perf_counter() - started
    progress(1.0, desc="Preview complete")
    yield (f"### Preview ready\nRendered {length:.1f} seconds in {elapsed:.1f} seconds.",
           _inspection_player_html(source_clip, output_clip, info.fps))


def render_full(video_path, backend_name, resolution, max_resolution, batch_size, seed, model_label, color_correction, attention_mode, blocks_to_swap, vae_tiling, stop_before_vae, sharpen_enabled, sharpen_strength, grain_enabled, grain_intensity, grain_saturation, microtexture_enabled, microtexture_strength, skin_finishing_enabled, skin_evenness, skin_smoothing, skin_redness, skin_shine, blemish_mode, preserve_marks, progress: gr.Progress = gr.Progress(track_tqdm=True)) -> Iterator[tuple]:
    if not video_path:
        raise MediaError("Import a video first")
    progress(0.0, desc="Preparing full render")
    ensure_workspace()
    source = Path(video_path)
    info = probe(source)
    job = OUTPUTS / f"render-{uuid.uuid4().hex[:10]}"
    job.mkdir(parents=True)
    output = job / f"{source.stem}-restored.mp4"
    settings = _settings(resolution, max_resolution, batch_size, seed, model_label, color_correction, attention_mode, blocks_to_swap, vae_tiling, stop_before_vae, sharpen_enabled, sharpen_strength, grain_enabled, grain_intensity, grain_saturation, microtexture_enabled, microtexture_strength, skin_finishing_enabled, skin_evenness, skin_smoothing, skin_redness, skin_shine, blemish_mode, preserve_marks)
    yield "### Full render running…\nProgress is shown above while SeedVR2 works.", empty_inspection_player_html()
    started = time.perf_counter()
    render(backend_name, source, output, settings, progress)
    if stop_before_vae:
        yield f"### Stopped before VAE\nLatents captured in `{job / 'vae_latents'}`. No restored video was generated.", empty_inspection_player_html()
        return
    elapsed = time.perf_counter() - started
    progress(1.0, desc="Full render complete")
    yield (f"### Render complete\nFinished in {elapsed / 60:.1f} minutes.",
           _inspection_player_html(source, output, info.fps))
