"""使用受控时间验证离线、旧数据、乱序消息、重启会话与计数回绕。"""

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from schemas import HeartbeatRequest, MeasurementRequest
from status import get_status
from storage import initialize_database, list_measurements, save_heartbeat, save_measurement


ROOT = Path(__file__).resolve().parents[1]
BASE = datetime(2026, 11, 9, 0, 0, tzinfo=timezone.utc)


class StatusLogicTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lesson03_test_", dir=ROOT / "outputs")
        self.addCleanup(self.temporary.cleanup)
        self.database = Path(self.temporary.name) / "measurements.sqlite3"
        initialize_database(self.database)

    def heartbeat(self, *, at=BASE, **changes):
        body = dict(schema_version=1, config_version="bins_v1", device_id="sorter_01", boot_id="boot_A",
                    uptime_ms=130000, scan_state="idle", current_bin_id=None, dropped_uploads=0)
        body.update(changes)
        return save_heartbeat(self.database, HeartbeatRequest(**body), now=at)

    def measurement(self, *, at=BASE, **changes):
        body = dict(schema_version=1, config_version="bins_v1", device_id="sorter_01", boot_id="boot_A",
                    measurement_id=1, measured_uptime_ms=125000, bin_id="plastic", distance_mm=250,
                    valid=True, is_full=False, error_code=None)
        body.update(changes)
        save_measurement(self.database, MeasurementRequest(**body), now=at)

    def state(self, at=BASE):
        return get_status(self.database, "sorter_01", now=at)

    def test_no_heartbeat_does_not_promote_history_to_current(self):
        self.measurement()
        state = self.state()
        self.assertEqual(state["device"]["connection_state"], "awaiting_heartbeat")
        self.assertTrue(all(b["latest_attempt"] is None for b in state["bins"]))
        self.assertEqual(len(list_measurements(self.database, device_id="sorter_01")), 1)

    def test_exact_offline_boundary(self):
        self.heartbeat()
        self.assertTrue(self.state(BASE + timedelta(milliseconds=29999))["device"]["online"])
        self.assertEqual(self.state(BASE + timedelta(seconds=30))["device"]["connection_state"], "offline")

    def test_out_of_order_and_failed_attempt_keep_last_valid(self):
        self.heartbeat()
        self.measurement(measurement_id=5, distance_mm=200)
        self.measurement(measurement_id=3, distance_mm=300, at=BASE + timedelta(seconds=1))
        plastic = self.state(BASE + timedelta(seconds=1))["bins"][0]
        self.assertEqual(plastic["latest_attempt"]["measurement_id"], 5)
        self.assertIs(plastic["current_is_full"], False)
        self.measurement(measurement_id=6, valid=False, distance_mm=None, is_full=None, error_code="no_echo")
        self.measurement(measurement_id=4, distance_mm=400, at=BASE + timedelta(seconds=2))
        plastic = self.state(BASE + timedelta(seconds=2))["bins"][0]
        self.assertEqual(plastic["measurement_state"], "failed")
        self.assertEqual(plastic["latest_attempt"]["measurement_id"], 6)
        self.assertIsNone(plastic["latest_attempt"]["distance_mm"])
        self.assertEqual(plastic["last_valid_measurement"]["distance_mm"], 200)
        self.assertIsNone(plastic["current_is_full"])

    def test_device_online_but_measurement_stale_at_boundary(self):
        self.heartbeat()
        self.measurement()
        self.heartbeat(at=BASE + timedelta(seconds=115), uptime_ms=245000)
        state = self.state(BASE + timedelta(seconds=115))
        self.assertTrue(state["device"]["online"])
        self.assertEqual(state["bins"][0]["latest_attempt"]["age_ms"], 120000)
        self.assertTrue(state["bins"][0]["latest_attempt"]["stale"])
        self.assertIsNone(state["bins"][0]["current_is_full"])
        self.assertIsNone(state["bins"][0]["remaining_percent"])

    def test_delayed_upload_is_not_fresh_and_duplicate_does_not_rejuvenate(self):
        self.heartbeat(uptime_ms=300000)
        self.measurement(measured_uptime_ms=0)
        latest = self.state()["bins"][0]["latest_attempt"]
        self.assertEqual(latest["age_ms"], 300000)
        self.assertTrue(latest["stale"])
        self.measurement(measured_uptime_ms=0, at=BASE + timedelta(seconds=5))
        after_retry = self.state(BASE + timedelta(seconds=5))["bins"][0]["latest_attempt"]
        self.assertEqual(after_retry["received_at"], latest["received_at"])
        self.assertEqual(after_retry["age_ms"], 305000)

    def test_new_boot_and_retired_heartbeat_cannot_restore_old_session(self):
        self.heartbeat()
        self.measurement()
        self.heartbeat(boot_id="boot_B", uptime_ms=100, at=BASE + timedelta(seconds=1))
        state = self.state(BASE + timedelta(seconds=1))
        self.assertEqual(state["device"]["boot_id"], "boot_B")
        self.assertTrue(all(b["measurement_state"] == "unmeasured" for b in state["bins"]))
        self.measurement(measurement_id=2)
        self.heartbeat(uptime_ms=150000, at=BASE + timedelta(seconds=2))
        self.assertEqual(self.state(BASE + timedelta(seconds=2))["device"]["boot_id"], "boot_B")
        self.assertIsNone(self.state(BASE + timedelta(seconds=2))["bins"][0]["latest_attempt"])
        self.measurement(boot_id="boot_B", measured_uptime_ms=50)
        self.assertEqual(self.state(BASE + timedelta(seconds=2))["bins"][0]["latest_attempt"]["boot_id"], "boot_B")

    def test_replayed_heartbeat_does_not_keep_device_online(self):
        self.assertEqual(self.heartbeat(), {"heartbeat_updated": True, "reason": "new_boot"})
        self.assertEqual(self.heartbeat(at=BASE + timedelta(seconds=25)), {"heartbeat_updated": False, "reason": "duplicate_uptime"})
        self.assertEqual(self.heartbeat(uptime_ms=120000, at=BASE + timedelta(seconds=29)), {"heartbeat_updated": False, "reason": "older_uptime"})
        self.assertFalse(self.state(BASE + timedelta(seconds=30))["device"]["online"])
        self.assertEqual(self.heartbeat(uptime_ms=161000, at=BASE + timedelta(seconds=31)), {"heartbeat_updated": True, "reason": "advanced_uptime"})
        self.assertTrue(self.state(BASE + timedelta(seconds=31))["device"]["online"])

    def test_millis_rollover(self):
        self.heartbeat(uptime_ms=2**32 - 500)
        self.measurement(measured_uptime_ms=2**32 - 800)
        self.heartbeat(uptime_ms=500, at=BASE + timedelta(seconds=1))
        state = self.state(BASE + timedelta(seconds=1))
        self.assertTrue(state["device"]["online"])
        self.assertEqual(state["bins"][0]["latest_attempt"]["age_ms"], 1300)

    def test_initialization_preserves_data_and_persisted_session(self):
        self.heartbeat()
        self.measurement()
        initialize_database(self.database)
        self.assertEqual(self.state()["device"]["boot_id"], "boot_A")
        self.assertEqual(self.state()["bins"][0]["latest_attempt"]["distance_mm"], 250)
