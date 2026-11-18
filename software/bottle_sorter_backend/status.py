"""把已保存的心跳、测量历史组合为网页需要的当前状态。"""

from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import sqlite3

from configuration import BackendConfiguration, remaining_percent

BIN_IDS = ("plastic", "can", "temporary")


def elapsed_ms(now: datetime, timestamp: str) -> int:
    return max(0, int((now - datetime.fromisoformat(timestamp)).total_seconds() * 1000))


def measurement_view(row, heartbeat: dict, heartbeat_age: int, now: datetime, stale_after_ms: int):
    if row is None:
        return None
    measurement = dict(json.loads(row[0]), received_at=row[1])
    # 排队上传的旧测量不能因为刚被接收就变成新测量。
    # 以设备运行时间差估计测量年龄，并至少保留已在服务器经过的时间。
    delta = (heartbeat["uptime_ms"] - measurement["measured_uptime_ms"]) % (2**32)
    if delta >= 2**31:
        delta -= 2**32
    age = max(0, elapsed_ms(now, row[1]), delta + heartbeat_age)
    measurement.update(
        age_ms=age,
        stale=age >= stale_after_ms,
        age_basis="estimated_from_device_uptime_and_server_receipt",
    )
    return measurement


def display_state(device, latest, configuration: BackendConfiguration) -> str:
    if not device["online"]:
        return device["connection_state"]
    if latest is None:
        return "unmeasured"
    if not device["config_matches"] or latest["config_version"] != configuration.config_version:
        return "config_mismatch"
    if not latest["valid"]:
        return "measurement_failed"
    if latest["stale"]:
        return "stale"
    if latest["is_full"] is None:
        return "unknown"
    if latest["is_full"]:
        return "full"
    calibration_status = configuration.calibration_status(latest["bin_id"])
    if calibration_status != "ready":
        return "configuration_error" if calibration_status == "invalid" else "calibration_required"
    if latest["remaining_percent"] <= configuration.near_full_remaining_pct:
        return "near_full"
    return "normal"


def get_status(path: Path, device_id: str, *, now: datetime | None = None, configuration: BackendConfiguration | None = None) -> dict:
    now = now or datetime.now(timezone.utc)
    configuration = configuration or BackendConfiguration()
    device = {
        "device_id": device_id, "connection_state": "awaiting_heartbeat", "online": False,
        "boot_id": None, "last_heartbeat_at": None, "heartbeat_age_ms": None,
        "scan_state": None, "current_bin_id": None, "dropped_uploads": None,
        "config_version": None, "config_matches": None,
    }
    bins = []
    with closing(sqlite3.connect(path, timeout=5)) as connection:
        with connection:
            # 同一个读事务确保设备会话与三桶数据来自一致的数据库状态。
            connection.execute("BEGIN")
            session = connection.execute(
                """SELECT s.boot_id, s.payload_json, s.last_heartbeat_at
                   FROM current_sessions AS c JOIN device_sessions AS s
                   ON c.device_id=s.device_id AND c.boot_id=s.boot_id
                   WHERE c.device_id=?""", (device_id,),
            ).fetchone()
            if session:
                heartbeat = json.loads(session[1])
                heartbeat_age = elapsed_ms(now, session[2])
                online = heartbeat_age < configuration.device_offline_after_ms
                device.update(
                    connection_state="online" if online else "offline", online=online,
                    boot_id=session[0], last_heartbeat_at=session[2], heartbeat_age_ms=heartbeat_age,
                    scan_state=heartbeat["scan_state"], current_bin_id=heartbeat["current_bin_id"],
                    dropped_uploads=heartbeat["dropped_uploads"],
                    config_version=heartbeat["config_version"],
                    config_matches=heartbeat["config_version"] == configuration.config_version,
                )
            for bin_id in BIN_IDS:
                latest = last_valid = None
                if session:
                    identity = (device_id, session[0], bin_id)
                    query = "SELECT payload_json, received_at FROM measurements WHERE device_id=? AND boot_id=? AND bin_id=?"
                    latest_row = connection.execute(query + " ORDER BY measurement_id DESC LIMIT 1", identity).fetchone()
                    valid_row = connection.execute(
                        query + " AND json_extract(payload_json, '$.valid')=1 ORDER BY measurement_id DESC LIMIT 1", identity,
                    ).fetchone()
                    latest = measurement_view(latest_row, heartbeat, heartbeat_age, now, configuration.measurement_stale_after_ms)
                    last_valid = measurement_view(valid_row, heartbeat, heartbeat_age, now, configuration.measurement_stale_after_ms)
                for measurement in (latest, last_valid):
                    if measurement is not None:
                        measurement["remaining_percent"] = remaining_percent(measurement, bin_id, configuration)
                usable = bool(device["online"] and device["config_matches"] and latest and latest["valid"]
                              and not latest["stale"] and latest["config_version"] == configuration.config_version)
                bins.append({
                    "bin_id": bin_id,
                    "measurement_state": "unmeasured" if latest is None else ("valid" if latest["valid"] else "failed"),
                    "latest_attempt": latest,
                    "last_valid_measurement": last_valid,
                    "current_is_full": latest["is_full"] if usable else None,
                    "remaining_percent": last_valid["remaining_percent"] if last_valid else None,
                    "capacity_measurement_id": last_valid["measurement_id"] if last_valid else None,
                    "capacity_fresh": bool(usable and latest["remaining_percent"] is not None),
                    "calibration_status": configuration.calibration_status(bin_id),
                    "display_state": display_state(device, latest, configuration),
                })
    return {
        "device": device,
        "bins": bins,
        "configuration": configuration.summary(),
        "thresholds": {"device_offline_after_ms": configuration.device_offline_after_ms,
                       "measurement_stale_after_ms": configuration.measurement_stale_after_ms,
                       "near_full_remaining_pct": configuration.near_full_remaining_pct},
        "generated_at": now.astimezone(timezone.utc).isoformat(timespec="milliseconds"),
    }
