#!/usr/bin/env bash
set -euo pipefail
unit='bottlesorter-tunnel.service'
if ! systemctl is-active --quiet "$unit"; then
    printf 'Tunnel service is not active. Inspect:\nsudo journalctl -u %s -n 60 --no-pager\n' "$unit" >&2
    exit 1
fi
started="$(systemctl show "$unit" -p ExecMainStartTimestamp --value)"
[[ -n "$started" ]] || { printf 'No service start timestamp found.\n' >&2; exit 1; }
logs="$(sudo journalctl -u "$unit" --since "$started" --no-pager -o cat)"
url="$(printf '%s\n' "$logs" | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -n 1 || true)"
if [[ -z "$url" ]]; then
    printf 'No URL in the current process logs yet. Wait briefly, then rerun.\n'
    printf 'For errors: sudo journalctl -u %s -n 60 --no-pager\n' "$unit"
    exit 1
fi
printf 'Current temporary URL: %s\nHealth check: %s/api/health\nPostman base_url: %s\n' "$url" "$url" "$url"
