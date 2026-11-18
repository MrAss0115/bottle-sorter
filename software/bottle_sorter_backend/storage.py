"""SQLite 持久保存；用唯一约束保证网络重发不会产生重复记录。"""

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from schemas import HeartbeatRequest, MeasurementRequest
from reward_store import migrate_rewards


class MeasurementConflict(ValueError):
    """相同身份却提交不同内容，不是真正的重复请求。"""


def initialize_database(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        with connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS measurements (
                    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    device_id TEXT NOT NULL,
                    boot_id TEXT NOT NULL,
                    measurement_id INTEGER NOT NULL,
                    bin_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    UNIQUE(device_id, boot_id, measurement_id)
                )
            """)
            connection.execute("""
                CREATE INDEX IF NOT EXISTS measurements_by_bin
                ON measurements(device_id, boot_id, bin_id, measurement_id DESC)
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS device_sessions (
                    device_id TEXT NOT NULL,
                    boot_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    last_heartbeat_at TEXT NOT NULL,
                    PRIMARY KEY(device_id, boot_id)
                )
            """)
            connection.execute("""
                CREATE TABLE IF NOT EXISTS current_sessions (
                    device_id TEXT PRIMARY KEY,
                    boot_id TEXT NOT NULL
                )
            """)


    migrate_rewards(path)


def save_measurement(path: Path, measurement: MeasurementRequest, *, now: datetime | None = None) -> bool:
    """提交成功后返回是否重复。保存失败则抛异常，调用者不能回复 accepted。"""
    payload = json.dumps(measurement.model_dump(), sort_keys=True, ensure_ascii=False)
    identity = (measurement.device_id, measurement.boot_id, measurement.measurement_id)
    received_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="milliseconds")
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        with connection:
            cursor = connection.execute(
                """INSERT INTO measurements
                   (device_id, boot_id, measurement_id, bin_id, payload_json, received_at)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(device_id, boot_id, measurement_id) DO NOTHING""",
                (*identity, measurement.bin_id, payload, received_at),
            )
            duplicate = cursor.rowcount == 0
            if duplicate:
                existing = connection.execute(
                    """SELECT payload_json FROM measurements
                       WHERE device_id=? AND boot_id=? AND measurement_id=?""",
                    identity,
                ).fetchone()
                if existing[0] != payload:
                    raise MeasurementConflict("measurement identity reused with different content")
        # 离开事务 with 块时，SQLite 已完成 commit，随后才返回。
    return duplicate


def list_measurements(
    path: Path,
    *,
    device_id: str,
    boot_id: str | None = None,
    bin_id: str | None = None,
    limit: int = 20,
) -> list[dict]:
    conditions = ["device_id=?"]
    parameters: list = [device_id]
    if boot_id is not None:
        conditions.append("boot_id=?")
        parameters.append(boot_id)
    if bin_id is not None:
        conditions.append("bin_id=?")
        parameters.append(bin_id)
    parameters.append(limit)
    # SQL 中只拼接程序自身的条件；用户输入始终作为 ? 参数传入。
    sql = (
        "SELECT payload_json, received_at FROM measurements WHERE "
        + " AND ".join(conditions)
        + " ORDER BY record_id DESC LIMIT ?"
    )
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        rows = connection.execute(sql, parameters).fetchall()
    return [dict(json.loads(payload), received_at=received_at) for payload, received_at in rows]


def save_heartbeat(path: Path, heartbeat: HeartbeatRequest, *, now: datetime | None = None) -> dict:
    """心跳选择当前启动；已退役启动、同启动旧心跳不能刷新在线时间。"""
    timestamp = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="milliseconds")
    payload = json.dumps(heartbeat.model_dump(), sort_keys=True, ensure_ascii=False)
    identity = (heartbeat.device_id, heartbeat.boot_id)
    outcome = {"heartbeat_updated": False, "reason": "retired_boot"}
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        with connection:
            # 先取得写事务，避免同时到达的两条心跳互相覆盖会话判断。
            connection.execute("BEGIN IMMEDIATE")
            current = connection.execute("SELECT boot_id FROM current_sessions WHERE device_id=?", (heartbeat.device_id,)).fetchone()
            existing = connection.execute(
                "SELECT payload_json FROM device_sessions WHERE device_id=? AND boot_id=?", identity,
            ).fetchone()
            if existing is None:
                connection.execute(
                    "INSERT INTO device_sessions VALUES (?, ?, ?, ?)", (*identity, payload, timestamp),
                )
                connection.execute(
                    """INSERT INTO current_sessions VALUES (?, ?)
                       ON CONFLICT(device_id) DO UPDATE SET boot_id=excluded.boot_id""", identity,
                )
                outcome = {"heartbeat_updated": True, "reason": "new_boot"}
            elif current and current[0] == heartbeat.boot_id:
                old_uptime = json.loads(existing[0])["uptime_ms"]
                elapsed = (heartbeat.uptime_ms - old_uptime) % (2**32)
                outcome = {"heartbeat_updated": False, "reason": "duplicate_uptime" if elapsed == 0 else "older_uptime"}
                # millis 为 32 位计数；允许正常回绕，忽略相同或倒退的旧心跳。
                if 0 < elapsed < 2**31:
                    connection.execute(
                        "UPDATE device_sessions SET payload_json=?, last_heartbeat_at=? WHERE device_id=? AND boot_id=?",
                        (payload, timestamp, *identity),
                    )
                    outcome = {"heartbeat_updated": True, "reason": "advanced_uptime"}
    return outcome
