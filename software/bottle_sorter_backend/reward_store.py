"""RFID 流水：数据库唯一键去重；余额从最大批次读取，不重复加分。"""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import sqlite3

FIELDS = ('device', 'batch', 'uid', 'earned', 'total', 'bottles', 'cans', 'rejected')


class RewardConflict(ValueError):
    pass


def migrate_rewards(path: Path):
    # 沿用现有项目启动时建表的方式；独立 SQL 文件可供审阅与重复执行。
    sql = (Path(__file__).parent / 'migrations' / '001_rewards.sql').read_text(encoding='utf-8')
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        connection.executescript('BEGIN IMMEDIATE;\n' + sql + '\nCOMMIT;')


def save_reward(path: Path, payload: dict):
    values = tuple(payload[field] for field in FIELDS)
    timestamp = datetime.now(timezone.utc).isoformat(timespec='milliseconds')
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        with connection:
            connection.execute('BEGIN IMMEDIATE')
            cursor = connection.execute('''INSERT INTO reward_events
                (device,batch,uid,earned,total,bottles,cans,rejected,received_at)
                VALUES (?,?,?,?,?,?,?,?,?) ON CONFLICT(device,batch) DO NOTHING''', (*values, timestamp))
            if cursor.rowcount == 0:
                stored = connection.execute('SELECT ' + ','.join(FIELDS) +
                    ' FROM reward_events WHERE device=? AND batch=?', values[:2]).fetchone()
                if stored != values:
                    raise RewardConflict('batch_conflict')
        # with 成功退出才完成 COMMIT。任何提交异常向上传递，不能提前 ACK。


def query_rewards(path: Path, *, device=None, uid=None, limit=20, offset=0, balances=False):
    conditions, parameters = [], []
    for field, value in [('device', device), ('uid', uid)]:
        if value is not None:
            conditions.append(f'e.{field}=?')
            parameters.append(value)
    if balances:
        conditions.append('''NOT EXISTS (SELECT 1 FROM reward_events newer
            WHERE newer.device=e.device AND newer.uid=e.uid AND newer.batch>e.batch)''')
    where = ' WHERE ' + ' AND '.join(conditions) if conditions else ''
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        connection.row_factory = sqlite3.Row
        with connection:
            connection.execute('BEGIN')
            count = connection.execute('SELECT COUNT(*) FROM reward_events e' + where, parameters).fetchone()[0]
            rows = connection.execute('SELECT e.* FROM reward_events e' + where +
                ' ORDER BY e.record_id DESC LIMIT ? OFFSET ?', (*parameters, limit, offset)).fetchall()
    items = [dict(row) for row in rows]
    if balances:
        items = [dict(device=r['device'], uid=r['uid'], total=r['total'],
                      last_batch=r['batch'], received_at=r['received_at']) for r in items]
    else:
        for item in items:
            item.pop('record_id')
    return dict(items=items, count=len(items), total=count, limit=limit, offset=offset)
