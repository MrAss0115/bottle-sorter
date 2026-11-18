import {BIN_META, DISPLAY_STATES, ERROR_LABELS, escapeHtml as esc, finiteNumber, fullLabel, formatDuration, binPresentation} from './view-model.mjs';
import {getLanguage, getLocale, setLanguage, translatePage, translateText} from './i18n.mjs';

const $ = id => document.getElementById(id);
const icon = name => `<svg viewBox="0 0 24 24" aria-hidden="true"><use href="/assets/lucide.svg#icon-${name}"></use></svg>`;
const number = value => new Intl.NumberFormat(getLocale(), {maximumFractionDigits: 1}).format(value);
const date = (value, full = false) => {
  if (!value || Number.isNaN(new Date(value).getTime())) return '—';
  return new Intl.DateTimeFormat(getLocale(), full ? {year: 'numeric', month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false} : {month: 'short', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false}).format(new Date(value));
};
const badge = (text, tone = 'neutral') => `<span class="badge ${tone}">${esc(text)}</span>`;
const state = {status: null, rows: [], visibleRows: [], statusError: false, historyError: false, historyLoaded: false, fetchedAt: 0, polling: true, busy: false, pending: false, timer: null, initial: true};

async function readJSON(path) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);
  try {
    const response = await fetch(path, {cache: 'no-store', signal: controller.signal, headers: {Accept: 'application/json'}});
    if (!response.ok) throw new Error(`Request failed (${response.status})`);
    return await response.json();
  } finally {clearTimeout(timeout);}
}

function currentSnapshot() {
  return !!(state.status && !state.statusError && state.polling && Date.now() - state.fetchedAt < 10000);
}

function renderNotices() {
  const messages = [];
  if (state.status?.configuration?.calibration_mode === 'demo') messages.push('<div class="notice">Demo thresholds are active. Sensor distances can be live; percentages and full-state labels are for bench testing, not measured bin capacity.</div>');
  if (state.statusError) messages.push('<div class="notice error">The monitoring service is unavailable. Retrying automatically; any visible values are from the last successful sync.</div>');
  if (state.historyError) messages.push('<div class="notice error">Measurement history could not be refreshed. Previously loaded records are retained.</div>');
  if (!state.polling) messages.push('<div class="notice">Auto-refresh is paused. You are viewing the last synchronized state. Select Resume live to continue.</div>');
  const html = messages.join('');
  if ($('noticeRegion').innerHTML !== html) $('noticeRegion').innerHTML = html;
}

function renderDevice() {
  const d = state.status?.device;
  const connection = $('connectionBadge');
  connection.className = `connection-badge ${state.statusError ? 'disconnected' : state.status ? 'connected' : ''}`;
  connection.innerHTML = `<i></i>${state.statusError ? 'Service unavailable' : state.status ? 'Service connected' : 'Connecting'}`;
  let label = 'Awaiting sync', tone = 'neutral';
  if (d) {
    [label, tone] = d.connection_state === 'online' ? ['Online', 'good'] : d.connection_state === 'offline' ? ['Offline', 'neutral'] : ['Awaiting device', 'warning'];
    if (!currentSnapshot()) {label = `Last: ${label.toLowerCase()}`; tone = 'neutral';}
  }
  $('deviceState').className = `badge ${tone}`;
  $('deviceState').textContent = label;
  $('deviceId').textContent = d?.device_id || 'sorter_01';
  const tasks = {idle: 'Idle', rotating: 'Positioning bin', settling: 'Waiting to settle', measuring: 'Measuring', error: 'Device error'};
  const task = tasks[d?.scan_state] || 'Awaiting report';
  $('taskState').textContent = d ? `${!d.online || !currentSnapshot() ? 'Last: ' : ''}${task}${d.current_bin_id ? ` · ${BIN_META[d.current_bin_id]?.short || 'Unknown bin'}` : ''}` : '—';
  $('heartbeatTime').textContent = date(d?.last_heartbeat_at);
  $('droppedUploads').textContent = finiteNumber(d?.dropped_uploads) === null ? '—' : number(d.dropped_uploads);
  $('bootId').textContent = d?.boot_id || 'No device heartbeat received';
  const thresholds = state.status?.thresholds;
  $('offlineThreshold').textContent = `${number((thresholds?.device_offline_after_ms ?? 30000) / 1000)} sec`;
  $('staleThreshold').textContent = `${number((thresholds?.measurement_stale_after_ms ?? 120000) / 1000)} sec`;
  $('deviceRule').textContent = `${number((thresholds?.device_offline_after_ms ?? 30000) / 1000)}s without a new heartbeat marks the device offline`;
  renderConfiguration();
  renderClock();
}

function renderConfiguration() {
  const config = state.status?.configuration;
  const descriptions = {
    not_configured: 'Measured calibration values are still needed. Distance readings and history remain available.',
    invalid: 'Configuration checks failed. Capacity estimates are unavailable until the configuration is corrected.',
    ready: 'Calibration parameters passed software checks. Estimates are calculated for each bin independently.',
  };
  const labels = {not_configured: ['Needs calibration', 'warning'], invalid: ['Configuration error', 'danger'], ready: ['Configured', 'good']};
  const [label, tone] = labels[config?.status] || ['Awaiting sync', 'neutral'];
  $('configState').textContent = label;
  $('configState').className = `badge ${tone}`;
  $('configVersion').textContent = config?.config_version || '—';
  $('configDescription').textContent = descriptions[config?.status] || 'Waiting for configuration.';
  $('calibrationNotice').hidden = !config || config.status === 'ready';
  $('calibrationTitle').textContent = config?.status === 'invalid' ? 'Calibration configuration needs attention' : 'Capacity calibration required';
  $('calibrationMessage').textContent = config?.status === 'invalid' ? 'Values are not used until configuration checks pass.' : 'Distance readings are saved. Remaining capacity needs measured calibration values.';
  if (config?.calibration_mode === 'demo') {
    $('configState').textContent = 'Demo thresholds';
    $('configState').className = 'badge warning';
    const demoBins = (state.status?.bins || []).filter(bin => bin.calibration_status === 'ready').map(bin => BIN_META[bin.bin_id]?.name || bin.bin_id);
    $('configDescription').textContent = demoBins.length ? `Demo thresholds configured for: ${demoBins.join(', ')}. Percentages are for bench testing.` : 'Demo mode is active. No bin has complete capacity thresholds.';
    $('calibrationNotice').hidden = false;
    $('calibrationTitle').textContent = 'Bench test: example thresholds';
    $('calibrationMessage').textContent = 'Live sensor readings; test percentages. These values do not certify actual bin capacity.';
  }
}

function renderBins() {
  const current = currentSnapshot();
  $('binGrid').innerHTML = Object.entries(BIN_META).map(([id, meta]) => {
    const bin = state.status?.bins?.find(item => item.bin_id === id);
    const view = binPresentation(bin, {hasSnapshot: !!state.status, current});
    const percentText = view.percent === null ? '—' : `${number(view.percent)}<small>%</small>`;
    const percentLabel = view.percent !== null && !view.fresh ? '<span class="old-label">Last valid</span>' : '';
    const lastDate = view.latest?.received_at;
    const distance = view.distance === null ? '—' : `${number(view.distance)} mm`;
    const oldDistance = view.latest && !view.latest.valid && view.lastValid ? 'Last valid distance' : 'Sensor distance';
    const foot = !current && state.status ? 'Last synchronized state' : view.latest && !view.latest.valid ? (ERROR_LABELS[view.latest.error_code] || 'Measurement failed') : view.latest ? `Reading #${view.latest.measurement_id}` : 'Awaiting a measurement';
    return `<article class="bin-card ${id}" aria-label="${meta.name}"><div class="bin-accent"></div><div class="bin-content"><div class="bin-topline"><span class="bin-number">BIN ${meta.number}</span>${badge(...view.badge)}</div><div class="bin-identity"><div><h3>${meta.name}</h3><div class="bin-subtitle">${meta.subtitle}</div></div><span class="bin-symbol">${icon(meta.icon)}</span></div><div class="capacity-caption">Estimated remaining ${percentLabel}</div><div class="capacity-value ${view.percent === null ? 'unknown' : ''}">${percentText}</div><div class="capacity-track ${view.percent === null ? 'unconfigured' : ''}" aria-hidden="true"><span style="width:${view.percent ?? 0}%"></span></div><div class="capacity-hint">${esc(view.hint)}</div><dl class="bin-details"><div><dt>${oldDistance}</dt><dd class="number">${distance}</dd></div><div><dt>Last attempt received</dt><dd>${esc(date(lastDate))}</dd></div></dl></div><div class="bin-footer"><span>${esc(foot)}</span><button type="button" data-bin="${id}" aria-label="View ${meta.name.toLowerCase()} details">View details <span aria-hidden="true">↗</span></button></div></article>`;
  }).join('');
}

function renderHistory() {
  const filter = $('historyResult').value;
  const binFilter = $('historyBin').value;
  const loaded = state.rows.filter(row => !binFilter || row.bin_id === binFilter);
  const rows = loaded.filter(row => filter === 'all' || (filter === 'valid' ? row.valid === true : row.valid === false));
  state.visibleRows = rows;
  $('historyCount').textContent = state.historyLoaded ? `${rows.length} shown · ${loaded.length} loaded` : state.historyError ? 'Unavailable' : 'Loading records';
  $('historyScope').textContent = `${filter === 'all' ? 'Newest received first' : 'Filtered within the loaded records'} · up to ${$('historyLimit').value} records`;
  if (!rows.length) {
    const title = !state.historyLoaded ? (state.historyError ? 'History is currently unavailable' : 'Loading measurements…') : loaded.length ? 'No matching measurements' : binFilter ? 'No measurements for this bin yet' : 'No measurements yet';
    const hint = !state.historyLoaded ? 'The page will retry while live refresh is enabled.' : loaded.length ? 'Try a different result filter.' : 'Device uploads will appear here, including failed attempts.';
    $('historyBody').innerHTML = `<tr><td colspan="7" class="empty-cell"><strong>${esc(title)}</strong><p>${esc(hint)}</p></td></tr>`;
    return;
  }
  $('historyBody').innerHTML = rows.map((row, i) => {
    const meta = BIN_META[row.bin_id] || {name: 'Unknown bin'};
    const binClass = BIN_META[row.bin_id] ? row.bin_id : 'unknown';
    const distance = finiteNumber(row.distance_mm);
    return `<tr><td class="row-number">#${esc(row.measurement_id)}<small title="${esc(row.boot_id)}">${esc(row.boot_id)}</small></td><td><span class="history-bin ${binClass}"><i></i>${meta.name}</span></td><td class="mono">${distance === null ? '—' : `${number(distance)} <span class="unit">mm</span>`}</td><td>${esc(fullLabel(row.is_full))}</td><td>${badge(row.valid ? 'Successful' : 'Failed', row.valid ? 'good' : 'danger')}</td><td class="mono">${esc(date(row.received_at))}</td><td><button class="row-detail" type="button" data-record="${i}" aria-label="View measurement ${esc(row.measurement_id)} details">${icon('arrow-up-right')}</button></td></tr>`;
  }).join('');
}

function renderClock() {
  $('headerClock').textContent = new Intl.DateTimeFormat(getLocale(), {day: '2-digit', month: 'short', year: 'numeric'}).format(new Date());
  const age = finiteNumber(state.status?.device?.heartbeat_age_ms);
  $('heartbeatAge').textContent = age === null ? '—' : translateText(formatDuration(age + Math.max(0, Date.now() - state.fetchedAt)), getLanguage());
  $('lastSync').textContent = translateText(state.fetchedAt ? `${state.polling ? 'Last sync' : 'Paused at'} ${new Intl.DateTimeFormat(getLocale(), {hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false}).format(new Date(state.fetchedAt))}` : 'Waiting for first sync', getLanguage());
}

function render() {renderNotices(); renderDevice(); renderBins(); renderHistory(); translatePage();}

function schedule() {
  clearTimeout(state.timer);
  if (state.polling) state.timer = setTimeout(() => {if (document.hidden) schedule(); else refresh();}, 3000);
}

async function refresh() {
  if (state.busy) {state.pending = true; return;}
  clearTimeout(state.timer);
  state.busy = true;
  $('refreshButton').disabled = true;
  $('refreshButton').classList.add('spinning');
  const requestedBin = $('historyBin').value;
  const requestedLimit = $('historyLimit').value;
  const params = new URLSearchParams({limit: requestedLimit});
  if (requestedBin) params.set('bin_id', requestedBin);
  try {
    const results = await Promise.allSettled([readJSON('/api/status'), readJSON(`/api/measurements?${params}`)]);
    const statusResult = results[0];
    if (statusResult.status === 'fulfilled' && statusResult.value?.device && Array.isArray(statusResult.value.bins)) {
      state.status = statusResult.value;
      state.fetchedAt = Date.now();
      state.statusError = false;
    } else {state.statusError = true;}
    const historyResult = results[1];
    if (historyResult.status === 'fulfilled' && Array.isArray(historyResult.value?.items)) {
      // A changed filter schedules a new request; a late response must not replace its rows.
      if (requestedBin === $('historyBin').value && requestedLimit === $('historyLimit').value) {
        state.rows = historyResult.value.items.filter(row => row && typeof row === 'object');
        state.historyLoaded = true;
        state.historyError = false;
      }
    } else {state.historyError = true;}
    state.initial = false;
    render();
  } finally {
    state.busy = false;
    $('refreshButton').disabled = false;
    $('refreshButton').classList.remove('spinning');
    if (state.pending) {state.pending = false; refresh();} else schedule();
  }
}

function openDialog(title, html) {
  $('dialogTitle').textContent = title;
  $('dialogBody').innerHTML = html;
  translatePage();
  if (!$('detailDialog').open) $('detailDialog').showModal();
}

function detailList(pairs) {
  return `<dl class="detail-list">${pairs.map(([key, value]) => `<div><dt>${esc(key)}</dt><dd>${esc(value)}</dd></div>`).join('')}</dl>`;
}

function recordDialog(record) {
  openDialog(`Measurement #${record.measurement_id}`, detailList([
    ['Collection bin', BIN_META[record.bin_id]?.name || 'Unknown bin'],
    ['Result', record.valid ? 'Successful' : 'Failed'], ['Distance', finiteNumber(record.distance_mm) === null ? '—' : `${number(record.distance_mm)} mm`],
    ['Full state', fullLabel(record.is_full)], ['Error', record.error_code ? ERROR_LABELS[record.error_code] || record.error_code : 'None'],
    ['Received at', date(record.received_at, true)], ['Device time at measurement', formatDuration(record.measured_uptime_ms)],
    ['Session', record.boot_id], ['Calibration version', record.config_version],
  ]) + `<details><summary>Show original record</summary><pre>${esc(JSON.stringify(record, null, 2))}</pre></details>`);
}

function binDialog(id) {
  const bin = state.status?.bins?.find(item => item.bin_id === id);
  const meta = BIN_META[id];
  if (!bin) {openDialog(meta.name, '<p>No synchronized status is available yet.</p>'); return;}
  const latest = bin.latest_attempt;
  const valid = bin.last_valid_measurement;
  openDialog(meta.name, detailList([
    ['Reported state', (DISPLAY_STATES[bin.display_state] || ['Unconfirmed'])[0]],
    ['Calibration', bin.calibration_status === 'ready' ? 'Configured' : 'Not ready'],
    ['Estimated remaining', finiteNumber(bin.remaining_percent) === null ? '—' : `${number(bin.remaining_percent)}%${bin.capacity_fresh && currentSnapshot() ? '' : ' · last valid'}`],
    ['Latest attempt', latest ? `#${latest.measurement_id} · ${latest.valid ? 'Successful' : 'Failed'}` : 'Not measured in this session'],
    ['Latest attempt received', date(latest?.received_at, true)],
    ['Last valid distance', finiteNumber(valid?.distance_mm) === null ? '—' : `${number(valid.distance_mm)} mm`],
    ['Last valid received', date(valid?.received_at, true)],
    ['Latest sensor error', latest?.error_code ? ERROR_LABELS[latest.error_code] || latest.error_code : 'None reported'],
  ]) + '<p class="detail-note">A new failed attempt keeps the previous valid reading. Device availability, freshness and calibration must be checked before treating a value as current.</p>');
}

function helpDialog() {
  const thresholds = state.status?.thresholds || {};
  const errors = state.status?.configuration?.errors || [];
  openDialog('Understanding the data', `<h3>Online does not mean a fresh reading</h3><p>The device is marked offline after ${esc(number((thresholds.device_offline_after_ms ?? 30000) / 1000))} seconds without a new accepted heartbeat. A bin reading needs an update after ${esc(number((thresholds.measurement_stale_after_ms ?? 120000) / 1000))} seconds. These are independent checks.</p><h3>Estimated remaining capacity</h3><p>Each bin needs its own measured empty, full and clear distances. A missing percentage is shown as a dash, never as zero. The estimate comes from ultrasonic height measurements, not exact volume.</p><h3>Last valid values are kept</h3><p>If a measurement fails, the device goes offline, or a reading expires, the last valid value may remain visible with a clear label. An unconfirmed full state is never presented as ready to accept an item.</p><h3>This page only monitors</h3><p>Refreshing this page does not send a heartbeat or create measurements. Positioning and release protection remain on the device.</p>${errors.length ? `<details><summary>Configuration check details</summary><pre>${esc(errors.join('\n'))}</pre></details>` : ''}`);
}

$('refreshButton').addEventListener('click', refresh);
$('languageToggle').addEventListener('click', () => {
  setLanguage(getLanguage() === 'en' ? 'zh' : 'en');
  $('pollText').textContent = state.polling ? 'Live · every 3s' : 'Resume live';
  render();
});
$('pollToggle').addEventListener('click', () => {
  state.polling = !state.polling;
  $('pollToggle').setAttribute('aria-pressed', String(!state.polling));
  $('pollText').textContent = state.polling ? 'Live · every 3s' : 'Resume live';
  clearTimeout(state.timer);
  render();
  if (state.polling) refresh();
});
$('historyBin').addEventListener('change', () => {renderHistory(); translatePage(); refresh();});
$('historyLimit').addEventListener('change', refresh);
$('historyResult').addEventListener('change', () => {renderHistory(); translatePage();});
$('historyBody').addEventListener('click', event => {
  const button = event.target.closest('[data-record]');
  if (button && state.visibleRows[Number(button.dataset.record)]) recordDialog(state.visibleRows[Number(button.dataset.record)]);
});
$('binGrid').addEventListener('click', event => {
  const button = event.target.closest('[data-bin]');
  if (button && BIN_META[button.dataset.bin]) binDialog(button.dataset.bin);
});
document.querySelectorAll('[data-help]').forEach(button => button.addEventListener('click', helpDialog));
$('dialogClose').addEventListener('click', () => $('detailDialog').close());
$('detailDialog').addEventListener('click', event => {if (event.target === $('detailDialog')) $('detailDialog').close();});
document.querySelectorAll('.nav-item').forEach(link => link.addEventListener('click', () => {
  document.querySelectorAll('.nav-item').forEach(item => {item.classList.remove('active'); item.removeAttribute('aria-current');});
  link.classList.add('active'); link.setAttribute('aria-current', 'location');
}));
document.addEventListener('visibilitychange', () => {if (!document.hidden && state.polling) refresh();});
window.addEventListener('pagehide', () => clearTimeout(state.timer));
setInterval(renderClock, 1000);
render();
refresh();
