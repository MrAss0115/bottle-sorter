"""容量公式、显示状态和配置错误的独立测试；数值仅为测试夹具。"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from configuration import load_configuration, remaining_percent
from schemas import HeartbeatRequest, MeasurementRequest
from status import get_status
from storage import initialize_database, save_heartbeat, save_measurement

ROOT = Path(__file__).resolve().parents[1]
BASE = datetime(2026, 11, 9, tzinfo=timezone.utc)


class ConfigurationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="lesson04_test_", dir=ROOT / "outputs")
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "bin_config.json"
        self.database = Path(self.temporary.name) / "measurements.sqlite3"
        initialize_database(self.database)
        self.raw = {
            "config_version": "bins_v1", "sensor_min_mm": 20, "sensor_max_mm": 450,
            "bins": [{"bin_id": b, "empty_distance_mm": 400, "clear_distance_mm": 130,
                      "full_distance_mm": 100} for b in ["plastic", "can", "temporary"]],
        }
        self.heartbeat = dict(schema_version=1, config_version="bins_v1", device_id="sorter_01", boot_id="test",
                              uptime_ms=130000, scan_state="idle", current_bin_id=None, dropped_uploads=0)
        self.measurement = dict(schema_version=1, config_version="bins_v1", device_id="sorter_01", boot_id="test",
                                measurement_id=1, measured_uptime_ms=125000, bin_id="plastic", distance_mm=250,
                                valid=True, is_full=False, error_code=None)

    def configuration(self):
        self.path.write_text(json.dumps(self.raw), encoding="utf-8")
        return load_configuration(self.path)

    def state(self, *, at=BASE):
        return get_status(self.database, "sorter_01", now=at, configuration=self.configuration())

    def seed(self):
        save_heartbeat(self.database, HeartbeatRequest(**self.heartbeat), now=BASE)
        save_measurement(self.database, MeasurementRequest(**self.measurement), now=BASE)

    def test_no_real_config_and_template_never_generate_capacity(self):
        absent = load_configuration(self.path)
        self.assertEqual(absent.status, "not_configured")
        self.assertTrue(absent.protocol_ready)
        template = load_configuration(ROOT / "bin_config.template.json")
        self.assertEqual(template.status, "not_configured")
        self.assertIsNone(remaining_percent(self.measurement, "plastic", template))

    def test_formula_clamps_and_exact_midpoint(self):
        configuration = self.configuration()
        self.assertEqual(configuration.status, "ready")
        for distance, expected in [(250, 50), (100, 0), (400, 100), (80, 0), (420, 100)]:
            self.assertAlmostEqual(remaining_percent(dict(self.measurement, distance_mm=distance), "plastic", configuration), expected)

    def test_bad_parameters_are_rejected(self):
        changes = [
            lambda c: c["bins"][0].update(clear_distance_mm=400),
            lambda c: c["bins"][0].update(full_distance_mm=500),
            lambda c: c["bins"][0].update(empty_distance_mm="400"),
            lambda c: c["bins"][0].update(bin_id="can"),
            lambda c: c.update(sensor_min_mm=500),
            lambda c: c.update(near_full_remaining_pct=101),
        ]
        original = json.dumps(self.raw)
        for change in changes:
            self.raw = json.loads(original)
            change(self.raw)
            with self.subTest(configuration=self.raw):
                configuration = self.configuration()
                self.assertEqual(configuration.status, "invalid")
                self.assertIsNone(remaining_percent(self.measurement, "plastic", configuration))

    def test_m1_calibrated_bin_does_not_need_invented_other_bin_values(self):
        for other_bin in self.raw["bins"][1:]:
            for key in ("empty_distance_mm", "full_distance_mm", "clear_distance_mm"):
                other_bin[key] = None
        configuration = self.configuration()
        self.assertEqual(configuration.status, "not_configured")
        self.assertEqual(configuration.calibration_status("plastic"), "ready")
        self.assertEqual(configuration.calibration_status("can"), "not_configured")
        self.assertEqual(remaining_percent(self.measurement, "plastic", configuration), 50)
        can_measurement = dict(self.measurement, measurement_id=2, bin_id="can")
        self.assertIsNone(remaining_percent(can_measurement, "can", configuration))
        self.seed()
        save_measurement(self.database, MeasurementRequest(**can_measurement), now=BASE)
        snapshot = self.state()
        self.assertEqual(snapshot["bins"][0]["display_state"], "normal")
        self.assertTrue(snapshot["bins"][0]["capacity_fresh"])
        self.assertEqual(snapshot["bins"][0]["calibration_status"], "ready")
        self.assertEqual(snapshot["bins"][1]["display_state"], "calibration_required")
        self.assertIsNone(snapshot["bins"][1]["remaining_percent"])
        self.assertFalse(snapshot["bins"][1]["capacity_fresh"])

    def test_m1_still_requires_sensor_range_and_all_local_thresholds(self):
        for key in ("sensor_min_mm", "sensor_max_mm"):
            saved = self.raw[key]
            self.raw[key] = None
            configuration = self.configuration()
            self.assertEqual(configuration.calibration_status("plastic"), "not_configured")
            self.assertIsNone(remaining_percent(self.measurement, "plastic", configuration))
            self.raw[key] = saved
        self.raw["bins"][0]["clear_distance_mm"] = None
        configuration = self.configuration()
        self.assertEqual(configuration.calibration_status("plastic"), "not_configured")
        self.assertIsNone(remaining_percent(self.measurement, "plastic", configuration))

    def test_demo_thresholds_are_explicitly_identified(self):
        self.raw["calibration_mode"] = "demo"
        configuration = self.configuration()
        self.assertEqual(configuration.summary()["calibration_mode"], "demo")
        self.assertEqual(remaining_percent(self.measurement, "plastic", configuration), 50)
        self.raw["calibration_mode"] = "unverified_other_mode"
        self.assertEqual(self.configuration().status, "invalid")

    def test_bad_json_or_version_cannot_accept_protocol_data(self):
        self.path.write_text("{bad", encoding="utf-8")
        self.assertFalse(load_configuration(self.path).protocol_ready)
        for version in [None, 1, " "]:
            self.path.write_text(json.dumps({"config_version": version}), encoding="utf-8")
            self.assertFalse(load_configuration(self.path).protocol_ready)

    def test_near_full_boundary_and_local_full_override(self):
        self.seed()
        self.assertEqual(self.state()["bins"][0]["display_state"], "normal")
        for index, distance, is_full, expected in [(2, 160, False, "near_full"),
                                                   (3, 160.01, False, "normal"),
                                                   (4, 250, True, "full"),
                                                   (5, 250, None, "unknown")]:
            body = dict(self.measurement, measurement_id=index, distance_mm=distance, is_full=is_full)
            save_measurement(self.database, MeasurementRequest(**body), now=BASE)
            self.assertEqual(self.state()["bins"][0]["display_state"], expected)

    def test_failure_offline_and_stale_preserve_last_known_capacity(self):
        self.seed()
        failed = dict(self.measurement, measurement_id=2, valid=False, distance_mm=None, is_full=None, error_code="no_echo")
        save_measurement(self.database, MeasurementRequest(**failed), now=BASE)
        bin_status = self.state()["bins"][0]
        self.assertEqual(bin_status["remaining_percent"], 50)
        self.assertEqual(bin_status["capacity_measurement_id"], 1)
        self.assertFalse(bin_status["capacity_fresh"])
        self.assertEqual(bin_status["display_state"], "measurement_failed")
        offline = self.state(at=BASE + timedelta(seconds=31))["bins"][0]
        self.assertEqual(offline["remaining_percent"], 50)
        self.assertFalse(offline["capacity_fresh"])
        self.assertEqual(offline["display_state"], "offline")
        newer = dict(self.measurement, measurement_id=3)
        save_measurement(self.database, MeasurementRequest(**newer), now=BASE)
        save_heartbeat(self.database, HeartbeatRequest(**dict(self.heartbeat, uptime_ms=245000)), now=BASE + timedelta(seconds=115))
        stale = self.state(at=BASE + timedelta(seconds=115))["bins"][0]
        self.assertEqual(stale["display_state"], "stale")
        self.assertEqual(stale["remaining_percent"], 50)
        self.assertFalse(stale["capacity_fresh"])

    def test_old_configuration_records_are_not_recalculated(self):
        self.seed()
        self.raw["config_version"] = "bins_v2"
        state = self.state()
        self.assertFalse(state["device"]["config_matches"])
        self.assertEqual(state["bins"][0]["display_state"], "config_mismatch")
        self.assertIsNone(state["bins"][0]["remaining_percent"])
        self.assertIsNone(state["bins"][0]["current_is_full"])

    def test_custom_timing_and_warning_settings(self):
        self.seed()
        self.raw.update(device_offline_after_ms=1000, measurement_stale_after_ms=2000, near_full_remaining_pct=25)
        state = self.state()
        self.assertEqual(state["thresholds"]["device_offline_after_ms"], 1000)
        self.assertEqual(state["bins"][0]["display_state"], "stale")
        self.assertFalse(self.state(at=BASE + timedelta(seconds=1))["device"]["online"])
