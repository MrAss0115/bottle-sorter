"""首次初始化本地密钥；不输出密钥、不覆盖已有配置。"""
import argparse
import json
import os
from pathlib import Path
import re
import secrets


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--device', default='sorter3070-01')
    parser.add_argument('--add-device', action='store_true', help='Add a device without changing existing keys')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', args.device):
        parser.error('Invalid device ID')
    root = Path(__file__).parent
    folder = root / 'data'
    folder.mkdir(exist_ok=True)
    path = folder / 'reward_credentials.json'
    if path.exists():
        if args.add_device:
            config = json.loads(path.read_text(encoding='utf-8'))
            if args.device not in config['devices']:
                config['devices'][args.device] = secrets.token_hex(16)
                temporary = path.with_name('reward_credentials.' + secrets.token_hex(4) + '.tmp')
                with temporary.open('x', encoding='utf-8') as f:
                    json.dump(config, f, indent=2)
                    f.write('\n')
                os.replace(temporary, path)
                print('Added device without changing existing keys:', args.device)
                return
        print('Existing credentials kept:', path)
        return
    config = dict(devices={args.device: secrets.token_hex(16)}, viewer_token=secrets.token_hex(32))
    with path.open('x', encoding='utf-8') as f:
        json.dump(config, f, indent=2)
        f.write('\n')
    print('Credentials created locally (not printed):', path)
    print('devices contains the firmware key; viewer_token is the separate website viewing password.')
    print('Keep this file private. It is inside the ignored data directory.')


if __name__ == '__main__':
    main()
