export const BIN_META = {
  plastic: {name: 'Plastic bottles', short: 'Plastic', subtitle: 'PET / PLASTIC', icon: 'bottle-wine', number: '01'},
  can: {name: 'Aluminium cans', short: 'Cans', subtitle: 'ALUMINIUM / METAL', icon: 'cylinder', number: '02'},
  temporary: {name: 'Temporary bin', short: 'Temporary', subtitle: 'OTHER / OVERFLOW', icon: 'archive', number: '03'},
};

export const DISPLAY_STATES = {
  awaiting_heartbeat: ['Awaiting device', 'neutral'], offline: ['Offline', 'neutral'],
  unmeasured: ['Not measured', 'neutral'], config_mismatch: ['Config mismatch', 'danger'],
  measurement_failed: ['Reading failed', 'danger'], stale: ['Update needed', 'warning'],
  unknown: ['Unconfirmed', 'warning'], full: ['Full', 'danger'],
  calibration_required: ['Needs calibration', 'warning'], configuration_error: ['Config error', 'danger'],
  near_full: ['Nearly full', 'warning'], normal: ['Normal', 'good'],
};

export const ERROR_LABELS = {
  no_echo: 'No sensor echo', out_of_range: 'Out of sensor range',
  unstable: 'Unstable readings', measurement_failed: 'Measurement failed',
};

export function escapeHtml(value) {
  return String(value ?? '—').replace(/[&<>"']/g, ch => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[ch]));
}

export function finiteNumber(value) {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

export function fullLabel(value) {
  return value === true ? 'Full' : value === false ? 'Clear' : 'Unconfirmed';
}

export function formatDuration(value) {
  const ms = finiteNumber(value);
  if (ms === null || ms < 0) return '—';
  const seconds = Math.floor(ms / 1000);
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor(seconds % 3600 / 60)}m`;
  return `${Math.floor(seconds / 86400)}d ${Math.floor(seconds % 86400 / 3600)}h`;
}

export function binPresentation(bin, {hasSnapshot = false, current = true} = {}) {
  const raw = finiteNumber(bin?.remaining_percent);
  const percent = raw !== null && raw >= 0 && raw <= 100 ? raw : null;
  const fresh = !!(current && bin?.capacity_fresh && percent !== null);
  const knownState = DISPLAY_STATES[bin?.display_state] || ['Awaiting sync', 'neutral'];
  const badge = hasSnapshot && !current ? ['Last known', 'neutral'] : knownState;
  const latest = bin?.latest_attempt;
  const lastValid = bin?.last_valid_measurement;
  const distance = latest?.valid ? finiteNumber(latest.distance_mm) : finiteNumber(lastValid?.distance_mm);
  let hint = 'Waiting for device data';
  if (hasSnapshot) {
    if (!current) hint = 'Showing the last synchronized data';
    else if (latest && !latest.valid) hint = ERROR_LABELS[latest.error_code] || 'Measurement failed';
    else if (bin?.display_state === 'offline') hint = 'Device offline · last known data';
    else if (!latest) hint = 'No reading in this session';
    else if (latest.stale) hint = 'This reading needs an update';
    else if (bin.calibration_status !== 'ready') hint = 'Measured calibration is not available';
    else if (latest.is_full === null) hint = 'Full state has not been confirmed';
    else hint = 'Based on the latest device measurement';
  }
  return {percent, fresh, badge, distance, hint, latest, lastValid};
}
