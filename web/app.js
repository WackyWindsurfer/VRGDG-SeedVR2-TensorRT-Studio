const $ = (selector) => document.querySelector(selector);
const before = $('#before');
const after = $('#after');
const inspector = $('#inspector');
const stage = $('#stage');
const afterPane = document.querySelector('.after-pane');
const divider = $('#divider');
let fps = 30;
let syncFrame = 0;
let zoom = 1, panX = 0, panY = 0, originX = 50, originY = 50, drag = '', dragX = 0, dragY = 0, baseX = 0, baseY = 0;
let currentOutputPath = '', currentOutputReprocessable = false;
const SETTINGS_STORAGE_KEY = 'seedvr-studio-render-settings-v2';
const LEGACY_SETTINGS_STORAGE_KEY = 'seedvr-studio-render-settings-v1';
const SAVED_SETTING_IDS = [
  'backend', 'preset', 'output-preset', 'crop-policy', 'chunked-render', 'chunk-seconds',
  'model', 'batch-size', 'seed', 'color', 'attention', 'blocks', 'vae-tiling',
  'sharpen', 'sharpen-strength', 'microtexture', 'microtexture-strength',
  'skin-finishing', 'skin-evenness', 'skin-smoothing', 'skin-redness', 'skin-shine', 'blemish-mode', 'preserve-marks',
  'grain', 'grain-intensity', 'grain-saturation', 'seam-enabled',
  'preview-start', 'preview-seconds'
];
const loadSavedSettings = () => {
  try {
    const current = JSON.parse(localStorage.getItem(SETTINGS_STORAGE_KEY) || 'null');
    if (current?.values) return current;
    const legacy = JSON.parse(localStorage.getItem(LEGACY_SETTINGS_STORAGE_KEY) || 'null');
    if (!legacy?.values) return null;
    // The first settings implementation could capture Chromium's restored SDPA
    // value before our intended default was applied. Migrate everything else,
    // but repair attention once; future explicit saves remain authoritative.
    legacy.values.attention = 'sageattn_2';
    legacy.version = 2;
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(legacy));
    return legacy;
  } catch (_) { return null; }
};
const refreshSettingsUi = () => {
  $('#chunk-length-wrap').hidden = !$('#chunked-render').checked;
  $('#seam-warning').hidden = $('#seam-enabled').checked;
  $('#blocks-value').textContent = $('#blocks').value;
  const skinOff = !$('#skin-finishing').checked;
  $('#skin-options').classList.toggle('inactive', skinOff);
  $('#skin-options').querySelectorAll('input,select').forEach((control) => { control.disabled = skinOff; });
  ['sharpen-strength', 'microtexture-strength', 'skin-evenness', 'skin-smoothing', 'skin-redness', 'skin-shine', 'grain-intensity', 'grain-saturation'].forEach((id) => document.getElementById(id)?.dispatchEvent(new Event('input')));
};
const restoreSettings = () => {
  const saved = loadSavedSettings();
  const values = {attention:'sageattn_2', color:'none', ...(saved?.values || {})};
  Object.entries(values).forEach(([id, value]) => {
    const element = document.getElementById(id);
    if (!element) return;
    if (element.type === 'checkbox') { element.checked = Boolean(value); return; }
    if (element.tagName === 'SELECT' && !Array.from(element.options).some((option) => option.value === String(value))) return;
    element.value = String(value);
  });
  // Browser form restoration must never silently replace the unsaved default.
  if (!saved) { $('#attention').value = 'sageattn_2'; $('#color').value = 'none'; }
  refreshSettingsUi();
  $('#settings-save-status').textContent = saved ? 'Saved settings loaded' : 'Using app defaults';
};
const saveCurrentSettings = () => {
  const values = {};
  SAVED_SETTING_IDS.forEach((id) => { const element = document.getElementById(id); if (element) values[id] = element.type === 'checkbox' ? element.checked : element.value; });
  try {
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify({version:1, savedAt:new Date().toISOString(), values}));
    $('#settings-save-status').textContent = 'Saved — these settings will load next time';
  } catch (_) { $('#settings-save-status').textContent = 'Could not save settings in this browser'; }
};
// Establish the real defaults immediately, before Chromium restores old form state.
$('#attention').value = 'sageattn_2';
$('#color').value = 'none';

const format = (value) => { const v = Math.max(0, Number(value) || 0); const m = Math.floor(v / 60); const s = Math.floor(v % 60); const ms = Math.floor((v % 1) * 1000); return `${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}.${String(ms).padStart(3,'0')}`; };
const duration = () => Math.min(Number.isFinite(before.duration) ? before.duration : 0, Number.isFinite(after.duration) ? after.duration : 0);
const update = () => { const d = duration(); $('#seek').max = d; $('#seek').value = before.currentTime || 0; $('#clock').textContent = `${format(before.currentTime)} / ${format(d)}`; const total = Math.max(0, Math.round(d * fps) - 1); $('#frame').max = total; $('#frame').value = Math.min(total, Math.round((before.currentTime || 0) * fps)); $('#frame-total').textContent = `/ ${total}`; };
const seek = (value) => { const t = Math.max(0, Math.min(duration(), Number(value) || 0)); before.currentTime = t; after.currentTime = t; update(); };
const stopPlaybackSync = () => { if (syncFrame) cancelAnimationFrame(syncFrame); syncFrame = 0; after.playbackRate = 1; };
const keepPlaybackSynced = () => { if (before.paused) { stopPlaybackSync(); return; } const drift = after.currentTime - before.currentTime; const tolerance = Math.max(0.006, 0.35 / Math.max(fps, 1)); if (Math.abs(drift) > tolerance) after.currentTime = before.currentTime; update(); syncFrame = requestAnimationFrame(keepPlaybackSynced); };
const pause = () => { before.pause(); after.pause(); stopPlaybackSync(); $('#play').textContent = '▶'; };
const play = async () => { if (!before.src || !after.src) return; if (before.paused) { try { after.currentTime = before.currentTime; await Promise.all([before.play(), after.play()]); stopPlaybackSync(); syncFrame = requestAnimationFrame(keepPlaybackSynced); $('#play').textContent = 'Ⅱ'; } catch (_) { pause(); } } else pause(); };
const setWipe = (value) => { const p = Math.max(0, Math.min(100, Number(value) || 50)); $('#wipe').value = p; afterPane.style.setProperty('clip-path', `inset(0 0 0 ${p}%)`, inspector.classList.contains('mode-compare') ? 'important' : ''); divider.style.left = `${p}%`; $('#wipe-value').textContent = `${Math.round(p)}%`; };
const applyTransform = () => { [before, after].forEach((video) => { video.style.transformOrigin = `${originX}% ${originY}%`; video.style.transform = `translate(${panX}px, ${panY}px) scale(${zoom})`; }); $('#zoom-reset').textContent = `${Math.round(zoom * 100)}%`; };
const resetZoom = () => { zoom = 1; panX = panY = 0; originX = originY = 50; applyTransform(); };
const setMode = (mode) => { ['original','restored','compare','side'].forEach((name) => inspector.classList.toggle(`mode-${name}`, name === mode)); document.querySelectorAll('[data-mode]').forEach((button) => button.classList.toggle('active', button.dataset.mode === mode)); afterPane.style.setProperty('clip-path', mode === 'compare' ? `inset(0 0 0 ${$('#wipe').value}%)` : 'none', 'important'); resetZoom(); updateEmptyState(); };
const updateEmptyState = () => { const hasBefore = Boolean(before.currentSrc || before.src); const hasAfter = Boolean(after.currentSrc || after.src); const mode = ['original','restored','compare','side'].find((name) => inspector.classList.contains(`mode-${name}`)) || 'compare'; const ready = mode === 'original' ? hasBefore : mode === 'restored' ? hasAfter : hasBefore && hasAfter; $('#empty-state').hidden = ready; if (ready) return; if (mode === 'restored' && !hasAfter) { $('#empty-title').textContent = 'Waiting for restored video'; $('#empty-subtitle').textContent = 'Render a preview or full video and it will appear here automatically.'; } else if (!hasBefore) { $('#empty-title').textContent = 'Waiting for original video'; $('#empty-subtitle').textContent = 'Upload an original video to begin.'; } else { $('#empty-title').textContent = 'Waiting for restored video'; $('#empty-subtitle').textContent = 'Render a preview or full video and it will appear here automatically.'; } };
const loadVideo = (video, url) => { if (url) video.src = url; else video.removeAttribute('src'); video.load(); updateEmptyState(); update(); };
const setFile = (video, file, nameTarget) => { if (!file) return; if (video === before) beginNewProject(file); loadVideo(video, URL.createObjectURL(file)); $(nameTarget).textContent = file.name; $('#media-info').textContent = `${file.name} · local file`; };

$('#source-file').addEventListener('change', (event) => setFile(before, event.target.files[0], '#source-name'));
document.querySelectorAll('[data-mode]').forEach((button) => button.addEventListener('click', () => setMode(button.dataset.mode)));
$('#seek').addEventListener('input', (event) => seek(event.target.value));
$('#frame').addEventListener('change', (event) => seek((Number(event.target.value) || 0) / fps));
$('#prev').addEventListener('click', () => { pause(); seek(before.currentTime - 1 / fps); });
$('#next').addEventListener('click', () => { pause(); seek(before.currentTime + 1 / fps); });
$('#play').addEventListener('click', play);
$('#wipe').addEventListener('input', (event) => setWipe(event.target.value));
$('#zoom-reset').addEventListener('click', resetZoom);
$('#fullscreen').addEventListener('click', () => (inspector.requestFullscreen || inspector.webkitRequestFullscreen)?.call(inspector));
$('#exit-studio').addEventListener('click', async () => { if (!window.confirm('Exit SeedVR Studio? Any active render will stop and GPU/RAM will be released.')) return; $('#render-status').textContent = 'Shutting down…'; try { await fetch('/api/shutdown', {method:'POST', keepalive:true}); } catch (_) {} window.close(); });
before.addEventListener('timeupdate', update);
before.addEventListener('ended', pause); before.addEventListener('loadedmetadata', update); after.addEventListener('loadedmetadata', update);
stage.addEventListener('wheel', (event) => { event.preventDefault(); const rect = stage.getBoundingClientRect(); originX = Math.max(0, Math.min(100, ((event.clientX - rect.left) / rect.width) * 100)); originY = Math.max(0, Math.min(100, ((event.clientY - rect.top) / rect.height) * 100)); zoom = Math.max(1, Math.min(8, zoom * (event.deltaY < 0 ? 1.2 : 1 / 1.2))); if (zoom === 1) panX = panY = 0; applyTransform(); }, { passive:false });
stage.addEventListener('dblclick', resetZoom);
stage.addEventListener('pointerdown', (event) => { drag = event.target.closest('#divider') ? 'wipe' : (zoom > 1 ? 'pan' : ''); if (!drag) return; stage.setPointerCapture?.(event.pointerId); dragX = event.clientX; dragY = event.clientY; baseX = panX; baseY = panY; });
stage.addEventListener('pointermove', (event) => { if (drag === 'wipe') setWipe(((event.clientX - stage.getBoundingClientRect().left) / stage.getBoundingClientRect().width) * 100); if (drag === 'pan') { panX = baseX + event.clientX - dragX; panY = baseY + event.clientY - dragY; applyTransform(); } });
stage.addEventListener('pointerup', () => { drag = ''; });
inspector.addEventListener('keydown', (event) => { if (event.target.matches('input')) return; if (event.code === 'Space') { event.preventDefault(); play(); } if (event.key === 'ArrowLeft') $('#prev').click(); if (event.key === 'ArrowRight') $('#next').click(); });

async function loadOutputs() {
  try {
    const response = await fetch('/api/outputs');
    const outputs = await response.json();
    const select = $('#output-select'); select.innerHTML = '<option value="">Select a workspace output…</option>';
    outputs.forEach((output) => { const option = document.createElement('option'); option.value = output.url; option.textContent = output.name; option.dataset.path = output.path; option.dataset.fps = output.fps || 30; option.dataset.reprocessable = output.reprocessable ? 'true' : 'false'; select.append(option); });
    $('#api-dot').classList.add('ok'); $('#api-status').textContent = `API ready · ${outputs.length} output${outputs.length === 1 ? '' : 's'}`;
  } catch (_) { $('#api-status').textContent = 'API unavailable'; }
}
$('#load-output').addEventListener('click', () => { const select = $('#output-select'); const url = select.value; if (!url) return; const option = select.selectedOptions[0]; currentOutputPath = option.dataset.path || url; currentOutputReprocessable = option.dataset.reprocessable === 'true'; fps = Number(option.dataset.fps) || 30; $('#reprocess-post').hidden = !currentOutputReprocessable; $('#open-output-folder').hidden = false; loadVideo(after, url); $('#media-info').textContent = currentOutputReprocessable ? 'Previous result loaded · post-only reprocess available' : 'Previous workspace result loaded'; });
$('#open-output-folder').addEventListener('click', async () => { if (!currentOutputPath) return; const data = new FormData(); data.append('output_path', currentOutputPath); try { const response = await fetch('/api/open-folder', {method:'POST', body:data}); if (!response.ok) throw new Error(await response.text()); } catch (error) { $('#media-info').textContent = `Could not open folder: ${error.message}`; } });
const chunkToggle = $('#chunked-render');
const chunkLengthWrap = $('#chunk-length-wrap');
chunkToggle.addEventListener('change', () => { chunkLengthWrap.hidden = !chunkToggle.checked; });
$('#chunk-help').addEventListener('click', () => $('#chunk-help-dialog').showModal());
const seamToggle = $('#seam-enabled');
seamToggle.addEventListener('change', () => { $('#seam-warning').hidden = seamToggle.checked; });
$('#skin-finishing').addEventListener('change', refreshSettingsUi);
$('#save-settings').addEventListener('click', saveCurrentSettings);
window.addEventListener('pageshow', () => setTimeout(restoreSettings, 0));
setWipe(50); applyTransform(); updateEmptyState(); update(); loadOutputs();

let activeJob = null, lastFailedJob = null, elapsedTimer = null, elapsedStarted = 0, projectToken = 0;
const beginNewProject = (file) => { projectToken += 1; const previousJob = activeJob; activeJob = null; lastFailedJob = null; currentOutputPath = ''; currentOutputReprocessable = false; stopElapsed(0); setRenderBusy(false); loadVideo(after, ''); $('#reprocess-post').hidden = true; $('#open-output-folder').hidden = true; $('#output-select').value = ''; $('#media-info').textContent = `${file.name} · new project`; $('#render-status').textContent = previousJob ? 'New project ready · previous render continues in background' : 'Ready'; };
const formatElapsed = (seconds) => { const total = Math.max(0, Math.floor(Number(seconds) || 0)); return `${String(Math.floor(total / 60)).padStart(2,'0')}:${String(total % 60).padStart(2,'0')}`; };
const updateEta = (progress) => { const p = Number(progress) || 0; const elapsed = (performance.now() - elapsedStarted) / 1000; if (p < 0.05 || elapsed < 5) { $('#eta-time').textContent = 'Estimating…'; return; } $('#eta-time').textContent = `~${formatElapsed(elapsed * (1 - Math.min(p, 0.99)) / p)}`; };
const startElapsed = () => { clearInterval(elapsedTimer); elapsedStarted = performance.now(); $('#elapsed-time').textContent = '00:00'; $('#eta-time').textContent = 'Estimating…'; elapsedTimer = setInterval(() => { const elapsed = (performance.now() - elapsedStarted) / 1000; $('#elapsed-time').textContent = formatElapsed(elapsed); updateEta(window.__seedvrProgress || 0); }, 250); };
const stopElapsed = (seconds) => { clearInterval(elapsedTimer); elapsedTimer = null; $('#elapsed-time').textContent = formatElapsed(seconds); $('#eta-time').textContent = '—'; };
const formValue = (id) => document.getElementById(id).value;
const formChecked = (id) => document.getElementById(id).checked ? 'true' : 'false';
const renderForm = (type) => {
  const file = $('#source-file').files[0];
  if (!file) throw new Error('Choose an original video first.');
  const data = new FormData();
  data.append('file', file); data.append('job_type', type); data.append('backend_name', formValue('backend'));
  data.append('preview_start', formValue('preview-start')); data.append('preview_seconds', formValue('preview-seconds')); data.append('output_preset', formValue('output-preset')); data.append('crop_policy', formValue('crop-policy'));
  data.append('chunked_render', type === 'full' && $('#chunked-render').checked ? 'true' : 'false'); data.append('chunk_seconds', formValue('chunk-seconds'));
  data.append('batch_size', formValue('batch-size')); data.append('seed', formValue('seed'));
  data.append('model_label', formValue('model')); data.append('color_correction', formValue('color')); data.append('attention_mode', formValue('attention')); data.append('blocks_to_swap', formValue('blocks'));
  data.append('vae_tiling', formChecked('vae-tiling')); data.append('stop_before_vae', 'false'); data.append('sharpen_enabled', formChecked('sharpen')); data.append('sharpen_strength', formValue('sharpen-strength')); data.append('microtexture_enabled', $('#skin-finishing').checked ? formChecked('microtexture') : 'false'); data.append('microtexture_strength', formValue('microtexture-strength')); data.append('grain_enabled', formChecked('grain')); data.append('grain_intensity', formValue('grain-intensity')); data.append('grain_saturation', formValue('grain-saturation'));
  data.append('skin_finishing_enabled', formChecked('skin-finishing')); data.append('skin_evenness', formValue('skin-evenness')); data.append('skin_smoothing', formValue('skin-smoothing')); data.append('skin_redness', formValue('skin-redness')); data.append('skin_shine', formValue('skin-shine')); data.append('blemish_mode', formValue('blemish-mode')); data.append('preserve_marks', formChecked('preserve-marks'));
  data.append('seam_mode', $('#seam-enabled').checked ? 'match' : 'off'); data.append('seam_frames', '2');
  return data;
};
const setRenderBusy = (busy) => { ['render-preview','render-full','reprocess-post'].forEach((id) => { $( `#${id}` ).disabled = busy; }); $('#stop-render').hidden = !busy; if (busy) { $('#resume-render').hidden = true; lastFailedJob = null; } };
const pollJob = async (id, token = projectToken) => {
  const job = await (await fetch(`/api/jobs/${id}`)).json();
  if (token !== projectToken) return;
  window.__seedvrProgress = Number(job.progress) || 0;
  updateEta(window.__seedvrProgress);
  $('#render-status').textContent = `${job.message || job.status}${job.progress != null ? ` · ${Math.round(job.progress * 100)}%` : ''}`;
  if (job.status === 'complete') { stopElapsed(job.elapsed_seconds); setRenderBusy(false); activeJob = null; if (Number(job.fps) > 0) fps = Number(job.fps); if (job.original_url) loadVideo(before, job.original_url); if (job.restored_url) loadVideo(after, job.restored_url); currentOutputPath = job.output_relative || ''; currentOutputReprocessable = Boolean(job.reprocessable); $('#reprocess-post').hidden = !currentOutputReprocessable; $('#open-output-folder').hidden = !currentOutputPath; $('#media-info').textContent = job.job_type === 'reprocess' ? 'Post-only reprocess complete' : `${job.job_type} complete`; loadOutputs(); return; }
  if (job.status === 'error' || job.status === 'cancelled') { stopElapsed(job.elapsed_seconds); setRenderBusy(false); activeJob = null; lastFailedJob = job.resumable ? job.id : null; $('#resume-render').hidden = !lastFailedJob; $('#render-status').textContent = `${job.failure_reason || job.error || job.message || job.status}${job.log_file ? ' · log saved' : ''}`; return; }
  setTimeout(() => pollJob(id, token).catch((error) => { if (token !== projectToken) return; setRenderBusy(false); $('#render-status').textContent = error.message; }), 800);
};
const startRender = async (type) => { try { setRenderBusy(true); $('#render-status').textContent = `Uploading ${type}…`; const response = await fetch('/api/jobs', { method:'POST', body:renderForm(type) }); if (!response.ok) throw new Error(await response.text()); activeJob = (await response.json()).id; startElapsed(); pollJob(activeJob, projectToken); } catch (error) { stopElapsed(0); setRenderBusy(false); $('#render-status').textContent = error.message; } };
const startReprocess = async () => { try { if (!currentOutputPath || !currentOutputReprocessable) throw new Error('Load a TensorRT result with saved decoded batches first.'); const data = new FormData(); data.append('output_path', currentOutputPath); data.append('seed', formValue('seed')); data.append('sharpen_enabled', formChecked('sharpen')); data.append('sharpen_strength', formValue('sharpen-strength')); data.append('microtexture_enabled', $('#skin-finishing').checked ? formChecked('microtexture') : 'false'); data.append('microtexture_strength', formValue('microtexture-strength')); data.append('skin_finishing_enabled', formChecked('skin-finishing')); data.append('skin_evenness', formValue('skin-evenness')); data.append('skin_smoothing', formValue('skin-smoothing')); data.append('skin_redness', formValue('skin-redness')); data.append('skin_shine', formValue('skin-shine')); data.append('blemish_mode', formValue('blemish-mode')); data.append('preserve_marks', formChecked('preserve-marks')); data.append('grain_enabled', formChecked('grain')); data.append('grain_intensity', formValue('grain-intensity')); data.append('grain_saturation', formValue('grain-saturation')); data.append('seam_mode', $('#seam-enabled').checked ? 'match' : 'off'); data.append('seam_frames', '2'); setRenderBusy(true); $('#render-status').textContent = 'Starting post-only reprocess…'; const response = await fetch('/api/reprocess', {method:'POST', body:data}); if (!response.ok) throw new Error(await response.text()); activeJob = (await response.json()).id; startElapsed(); pollJob(activeJob, projectToken); } catch (error) { stopElapsed(0); setRenderBusy(false); $('#render-status').textContent = error.message; } };
$('#render-preview').addEventListener('click', () => startRender('preview')); $('#render-full').addEventListener('click', () => startRender('full'));
$('#reprocess-post').addEventListener('click', startReprocess);
$('#resume-render').addEventListener('click', async () => { if (!lastFailedJob) return; try { $('#resume-render').hidden = true; setRenderBusy(true); const response = await fetch(`/api/jobs/${lastFailedJob}/resume`, {method:'POST'}); if (!response.ok) throw new Error(await response.text()); activeJob = lastFailedJob; startElapsed(); pollJob(activeJob, projectToken); } catch (error) { setRenderBusy(false); $('#render-status').textContent = error.message; } });
$('#stop-render').addEventListener('click', async () => { if (!activeJob) return; await fetch(`/api/jobs/${activeJob}/cancel`, {method:'POST'}); });
$('#blocks').addEventListener('input', (event) => { $('#blocks-value').textContent = event.target.value; });
const bindSliderValue = (inputId, outputId, digits) => { const input = $(`#${inputId}`); const output = $(`#${outputId}`); const refresh = () => { output.textContent = Number(input.value).toFixed(digits); }; input.addEventListener('input', refresh); refresh(); };
bindSliderValue('sharpen-strength', 'sharpen-strength-value', 2);
bindSliderValue('microtexture-strength', 'microtexture-strength-value', 2);
bindSliderValue('skin-evenness', 'skin-evenness-value', 2);
bindSliderValue('skin-smoothing', 'skin-smoothing-value', 2);
bindSliderValue('skin-redness', 'skin-redness-value', 2);
bindSliderValue('skin-shine', 'skin-shine-value', 2);
bindSliderValue('grain-intensity', 'grain-intensity-value', 3);
bindSliderValue('grain-saturation', 'grain-saturation-value', 2);
const fillSelect = (id, values) => { const select = $(`#${id}`); select.innerHTML = ''; values.forEach((value) => { const option = document.createElement('option'); option.value = value; option.textContent = value; select.append(option); }); };
const setSkinBackendAvailable = (available) => { $('#skin-backend-warning').hidden = available; $('#skin-finishing').disabled = !available; if (!available) $('#skin-finishing').checked = false; refreshSettingsUi(); };
const loadConfig = async () => { try { const config = await (await fetch('/api/config')).json(); fillSelect('model', config.models); fillSelect('preset', Object.keys(config.presets)); fillSelect('output-preset', Object.keys(config.output_presets)); fillSelect('crop-policy', config.crop_policies); $('#output-preset').value = '1K / 1080p'; $('#crop-policy').value = 'Preserve original aspect ratio'; if (config.seam_modes) { $('#seam-enabled').disabled = false; $('#seam-enabled').title = 'Color + noise match over 2 frames'; } else { $('#seam-enabled').title = 'Available after the JS backend is restarted'; } const preset = $('#preset'); preset.addEventListener('change', () => { const value = config.presets[preset.value]; if (!value) return; ['model','batch-size','attention','blocks'].forEach((id) => { const key = {'batch-size':'batch_size','model':'model','attention':'attention','blocks':'blocks'}[id]; if (value[key] != null) $(`#${id}`).value = value[key]; }); $('#vae-tiling').checked = Boolean(value.vae_tiling); $('#blocks-value').textContent = $('#blocks').value; }); restoreSettings(); setSkinBackendAvailable(config.features?.skin_finishing === true); const backend = config.backend; $('#api-status').textContent = backend.seedvr?.message || 'API ready'; } catch (_) { restoreSettings(); setSkinBackendAvailable(false); $('#api-status').textContent = 'API ready · config unavailable'; } };
loadConfig();
