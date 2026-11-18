import test from 'node:test';
import assert from 'node:assert/strict';
import {binPresentation, escapeHtml, fullLabel, formatDuration} from '../frontend/dist/assets/view-model.mjs';

test('null capacity is unknown, never zero', () => {
  const view = binPresentation({remaining_percent: null, display_state: 'calibration_required'}, {hasSnapshot: true});
  assert.equal(view.percent, null);
  assert.equal(view.fresh, false);
  assert.equal(view.badge[0], 'Needs calibration');
});

test('a real zero percent reading is preserved', () => {
  const view = binPresentation({remaining_percent: 0, capacity_fresh: true, display_state: 'full'}, {hasSnapshot: true});
  assert.equal(view.percent, 0);
  assert.equal(view.fresh, true);
});

test('cached or paused snapshots cannot appear fresh', () => {
  const view = binPresentation({remaining_percent: 50, capacity_fresh: true, display_state: 'normal'}, {hasSnapshot: true, current: false});
  assert.equal(view.percent, 50);
  assert.equal(view.fresh, false);
  assert.equal(view.badge[0], 'Last known');
});

test('a failed attempt shows the last valid distance with an error', () => {
  const view = binPresentation({remaining_percent: 50, capacity_fresh: false, display_state: 'measurement_failed',
    latest_attempt: {valid: false, distance_mm: null, error_code: 'no_echo'},
    last_valid_measurement: {valid: true, distance_mm: 250}}, {hasSnapshot: true});
  assert.equal(view.distance, 250);
  assert.equal(view.hint, 'No sensor echo');
  assert.equal(view.fresh, false);
});

test('untrusted record text is escaped before HTML insertion', () => {
  assert.equal(escapeHtml('<img src=x onerror="x">'), '&lt;img src=x onerror=&quot;x&quot;&gt;');
});

test('full-state null is distinct from clear', () => {
  assert.equal(fullLabel(null), 'Unconfirmed');
  assert.equal(fullLabel(false), 'Clear');
  assert.equal(fullLabel(true), 'Full');
});

test('invalid numeric values do not produce fabricated capacity', () => {
  for (const value of ['50', NaN, Infinity, -1, 101]) assert.equal(binPresentation({remaining_percent: value}).percent, null);
  assert.equal(formatDuration(null), '—');
  assert.equal(formatDuration(30000), '30s');
});
