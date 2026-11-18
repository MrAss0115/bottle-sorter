#!/usr/bin/env python3
"""Send clearly labelled test events to a TEST backend. Python standard library only.
Requires --allow-test-writes. Never use real device IDs or production credentials.
The probe checks HTTP behavior; independently verify DB rows, transactions and UI.
"""
import argparse
import ipaddress
import json
from pathlib import Path
import re
import secrets
import socket
import time
from urllib.parse import urlsplit


def endpoint(url):
    parsed = urlsplit(url)
    if parsed.scheme != 'http' or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path != '/api/rewards':
        raise ValueError('Use http://IPv4:port/api/rewards, matching current firmware')
    ipaddress.IPv4Address(parsed.hostname)
    port = parsed.port or 80
    if not 1 <= port <= 65535: raise ValueError('Invalid port')
    return parsed.hostname, port, parsed.path


def headers(raw):
    lines = raw.split(b'\r\n')
    if any(len(line) > 127 for line in lines):
        raise ValueError('Response header exceeds firmware 127-byte line capacity')
    match = re.fullmatch(rb'HTTP/1\.[01] ([1-5][0-9]{2}) [^\r\n]*', lines[0])
    if not match: raise ValueError('Expected HTTP/1.x status with reason phrase')
    values = {}
    for line in lines[1:]:
        if b':' not in line: raise ValueError('Malformed HTTP header')
        name, value = line.split(b':', 1)
        name = name.lower()
        if name in values: raise ValueError('Duplicate response header')
        values[name] = value.lstrip(b' ')
    if b'transfer-encoding' in values or b'content-encoding' in values:
        raise ValueError('Do not use chunked or compressed ACK responses')
    length = values.get(b'content-length', b'')
    if not re.fullmatch(rb'[0-9]+', length): raise ValueError('Explicit integer Content-Length required')
    length = int(length)
    if length > 4096: raise ValueError('Unexpectedly large response')
    return int(match.group(1)), length


def parse_http_response(raw, batch=None):
    if b'\r\n\r\n' not in raw: raise ValueError('Missing HTTP header/body separator')
    head, body = raw.split(b'\r\n\r\n', 1)
    status, length = headers(head)
    if len(body) != length: raise ValueError('Response Content-Length/body mismatch')
    if status == 200 and batch is not None:
        expected = ('ACK %d\n' % batch).encode('ascii')
        if len(body) >= 32 or body != expected:
            raise ValueError('Expected exact plaintext batch ACK with one LF')
    return status, body


def post(url, token, payload):
    host, port, path = endpoint(url)
    if not re.fullmatch(r'[0-9a-f]{32}', token): raise ValueError('Invalid key format')
    body = json.dumps(payload, separators=(',', ':'), ensure_ascii=True).encode('ascii')
    head = ('POST %s HTTP/1.0\r\nHost: %s:%d\r\nX-API-Key: %s\r\n'
            'Content-Type: application/json\r\nContent-Length: %d\r\nConnection: close\r\n\r\n'
            % (path, host, port, token, len(body))).encode('ascii')
    deadline = time.monotonic() + 20
    with socket.create_connection((host, port), timeout=5) as connection:
        connection.settimeout(max(0.01, deadline-time.monotonic()))
        connection.sendall(head + body)
        raw = b''
        while len(raw) <= 8192:
            remaining = deadline-time.monotonic()
            if remaining <= 0: raise TimeoutError('No complete ACK within 20 seconds')
            connection.settimeout(remaining)
            chunk = connection.recv(2048)
            if not chunk: break
            raw += chunk
            if b'\r\n\r\n' in raw:
                response_head, response_body = raw.split(b'\r\n\r\n', 1)
                _, length = headers(response_head)
                if len(response_body) >= length: break
        return parse_http_response(raw, payload.get('batch'))


def run_contract(url, token, device, report=print):
    if not re.fullmatch(r'contract-test-[0-9a-f]{8}', device):
        raise ValueError('Tests require a separate contract-test-xxxxxxxx device ID')
    first = dict(device=device, batch=2, uid='DEADBEEF', earned=20, total=120, bottles=1, cans=1, rejected=0)
    bad_key = ('1' if token[0] != '1' else '0') + token[1:]
    missing = dict(first); del missing['total']
    cases = [
        ('wrong_key', first, 401, bad_key),
        ('first', first, 200, token),
        ('identical_retry', dict(first), 200, token),
        ('conflicting_uid', dict(first, uid='CAFEBABE'), 409, token),
        ('newer', dict(first, batch=4, earned=10, total=130, cans=0), 200, token),
        ('older_arrives_late', dict(first, batch=1, earned=10, total=100, cans=0), 200, token),
        ('all_rejected', dict(first, batch=5, earned=0, total=130, bottles=0, cans=0, rejected=1), 200, token),
        ('missing_field', missing, 400, token),
        ('extra_field', dict(first, timestamp=123), 400, token),
        ('too_many_items', dict(first, batch=6, bottles=5, cans=1), 400, token),
        ('boolean_points', dict(first, batch=6, earned=True), 400, token),
        ('fractional_points', dict(first, batch=6, earned=1.5), 400, token),
        ('malformed_uid', dict(first, batch=6, uid='DE:AD:BE:EF'), 400, token),
    ]
    errors = []
    for name, payload, expected, key in cases:
        try:
            status, _ = post(url, key, payload)
            if status != expected: raise ValueError('Expected HTTP %d, received %d' % (expected, status))
            report('PASS ' + name)
        except (OSError, ValueError) as error:
            errors.append(name); report('FAIL %s: %s' % (name, error))
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='http://LAN_IP:port/api/rewards')
    parser.add_argument('--token-file', type=Path, required=True)
    parser.add_argument('--allow-test-writes', action='store_true')
    args = parser.parse_args()
    if not args.allow_test_writes:
        parser.error('This creates test records. Use a TEST backend and add --allow-test-writes.')
    endpoint(args.url)
    token = args.token_file.read_text(encoding='ascii').strip()
    if not re.fullmatch(r'[0-9a-f]{32}', token): parser.error('Token file must contain 32 lowercase hex characters')
    device = 'contract-test-' + secrets.token_hex(4)
    print('Test device:', device)
    errors = run_contract(args.url, token, device)
    print('HTTP checks: %s' % ('PASS' if not errors else 'FAIL'))
    print('Verify DB independently: exactly 4 rows for this device, batches 1,2,4,5.')
    print('DEADBEEF latest device balance must be 130 at batch 5; verify website too.')
    raise SystemExit(1 if errors else 0)


if __name__ == '__main__': main()
