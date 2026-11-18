#!/usr/bin/env bash
# SSH-independent backend and temporary Cloudflare Tunnel.
set -euo pipefail
project_dir='/home/ubuntu/bottlesorter'
python_exe="$project_dir/.venv312/bin/python"
marker='# Managed by BottleSorter session-persistence setup'
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }

[[ "$(id -un)" == ubuntu ]] || fail 'Run as ubuntu, without sudo bash.'
[[ -f "$project_dir/app.py" ]] || fail "Missing $project_dir/app.py"
[[ -x "$python_exe" ]] || fail "Missing $python_exe"
[[ -f "$project_dir/data/reward_credentials.json" ]] || fail 'Existing credentials file is missing. No keys were changed.'
cloudflared_exe="$(command -v cloudflared || true)"
[[ -n "$cloudflared_exe" && -x "$cloudflared_exe" ]] || fail 'cloudflared is not installed or not in PATH.'
cd "$project_dir"
"$python_exe" -B -c 'import sys, uvicorn; assert sys.version_info >= (3, 11); import app; print("Backend imports: OK")'

for name in bottlesorter.service bottlesorter-tunnel.service; do
    unit="/etc/systemd/system/$name"
    fragment="$(systemctl show "$name" -p FragmentPath --value 2>/dev/null || true)"
    if [[ -n "$fragment" && "$fragment" != "$unit" ]]; then
        fail "Existing $name is managed elsewhere: $fragment. Inspect it first."
    fi
    if [[ -e "$unit" ]] && ! grep -Fqx "$marker" "$unit"; then
        fail "Existing $unit was not overwritten; it has no setup marker."
    fi
    overrides="$(systemctl show "$name" -p DropInPaths --value 2>/dev/null || true)"
    [[ -z "$overrides" ]] || fail "Existing overrides need review: $overrides"
done

if ! systemctl is-active --quiet bottlesorter.service; then
    "$python_exe" -B - <<'PY'
import socket
with socket.socket() as probe:
    try:
        probe.bind(('127.0.0.1', 8000))
    except OSError:
        raise SystemExit('ERROR: Port 8000 is occupied. Stop the old foreground backend with Ctrl+C, then rerun. No process was killed.')
PY
fi

staging="$project_dir/deploy/session-services"
mkdir -p "$staging"
cat > "$staging/bottlesorter.service" <<EOF
$marker
[Unit]
Description=BottleSorter capacity and RFID backend
Wants=network-online.target
After=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$project_dir
Environment=PYTHONDONTWRITEBYTECODE=1
Environment=PYTHONUTF8=1
Environment=BOTTLE_SORTER_DATABASE=$project_dir/data/measurements.sqlite3
Environment=BOTTLE_SORTER_REWARD_CREDENTIALS=$project_dir/data/reward_credentials.json
ExecStart=$python_exe -B -m uvicorn app:app --host 127.0.0.1 --port 8000 --workers 1
Restart=always
RestartSec=5
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

cat > "$staging/bottlesorter-tunnel.service" <<EOF
$marker
[Unit]
Description=BottleSorter temporary Cloudflare Tunnel
Wants=network-online.target bottlesorter.service
After=network-online.target bottlesorter.service
StartLimitIntervalSec=0

[Service]
Type=simple
User=ubuntu
WorkingDirectory=$project_dir
Environment=HOME=/home/ubuntu
ExecStart=$cloudflared_exe tunnel --url http://127.0.0.1:8000
Restart=always
RestartSec=10
TimeoutStopSec=30
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

sudo -v
sudo systemd-analyze verify "$staging/bottlesorter.service" "$staging/bottlesorter-tunnel.service"
sudo install -m 0644 "$staging/bottlesorter.service" /etc/systemd/system/bottlesorter.service
sudo install -m 0644 "$staging/bottlesorter-tunnel.service" /etc/systemd/system/bottlesorter-tunnel.service
sudo systemctl daemon-reload
sudo systemctl enable bottlesorter.service bottlesorter-tunnel.service
sudo systemctl restart bottlesorter.service

ready=false
for attempt in {1..30}; do
    if "$python_exe" -B - <<'PY'
import json
import urllib.request
try:
    with urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=1) as response:
        assert response.status == 200 and json.load(response)['status'] == 'ok'
except Exception:
    raise SystemExit(1)
PY
    then
        ready=true
        break
    fi
    sleep 1
done
if [[ "$ready" != true ]]; then
    sudo journalctl -u bottlesorter.service -n 40 --no-pager
    fail 'Backend health check failed. Units were installed, but tunnel startup was not requested.'
fi
sudo systemctl restart bottlesorter-tunnel.service
printf '\nBackend health: OK. Both units are enabled for boot.\n'
printf 'Tunnel startup is asynchronous; check external access after obtaining the URL.\n'
printf '\nCheck services:\nsudo systemctl status bottlesorter bottlesorter-tunnel --no-pager\n'
printf '\nFind current URL:\nbash /home/ubuntu/bottlesorter/show-bottlesorter-url.sh\n'
printf '\nTemporary URL may change after tunnel restart. Existing data and keys were kept.\n'
