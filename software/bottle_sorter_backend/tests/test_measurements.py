"""实际 HTTP 与服务重启测试；所有测试数据写入 E 盘独立临时库。"""

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


class MeasurementIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="lesson02_test_", dir=ROOT / "outputs")
        cls.database = Path(cls.temporary.name) / "measurements.sqlite3"
        cls.log = open(Path(cls.temporary.name) / "server.log", "w", encoding="utf-8")
        cls.process = None
        cls.addClassCleanup(cls.cleanup)
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 0))
            cls.port = probe.getsockname()[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.start_server()

    @classmethod
    def start_server(cls):
        environment = dict(os.environ, BOTTLE_SORTER_DATABASE=str(cls.database),
                           BOTTLE_SORTER_CONFIG=str(Path(cls.temporary.name) / "bin_config.json"),
                           PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1",
                           TEMP=cls.temporary.name, TMP=cls.temporary.name)
        cls.process = subprocess.Popen(
            [sys.executable, "-B", "-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", str(cls.port)],
            cwd=ROOT, env=environment, stdout=cls.log, stderr=subprocess.STDOUT)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if cls.process.poll() is not None:
                raise RuntimeError("Test server exited")
            try:
                if cls.request("GET", "/api/health")[0] == 200:
                    return
            except OSError:
                pass
            time.sleep(0.1)
        raise RuntimeError("Test server did not start")

    @classmethod
    def stop_server(cls):
        if cls.process is not None and cls.process.poll() is None:
            cls.process.terminate()
            try:
                cls.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.process.kill()
                cls.process.wait(timeout=5)

    @classmethod
    def cleanup(cls):
        cls.stop_server()
        cls.log.close()
        cls.temporary.cleanup()

    @classmethod
    def request(cls, method, path, payload=None, raw=None):
        data = raw if raw is not None else (None if payload is None else json.dumps(payload).encode("utf-8"))
        request = urllib.request.Request(cls.base + path, method=method, data=data,
                                        headers={"Content-Type": "application/json"} if data is not None else {})
        try:
            response = urllib.request.urlopen(request, timeout=12)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            return response.status, json.loads(response.read())

    def test_protocol_storage_and_restart(self):
        sample = {
            "schema_version": 1, "config_version": "bins_v1", "device_id": "sorter_01",
            "boot_id": "integration_test_boot", "measurement_id": 1,
            "measured_uptime_ms": 125000, "bin_id": "plastic", "distance_mm": 250,
            "valid": True, "is_full": False, "error_code": None,
        }
        self.assertEqual(self.request("POST", "/api/measurements", sample),
                         (200, {"accepted": True, "measurement_id": 1}))
        with ThreadPoolExecutor(max_workers=4) as pool:
            repeated = list(pool.map(lambda _: self.request("POST", "/api/measurements", sample), range(4)))
        self.assertTrue(all(status == 200 and body.get("duplicate") is True for status, body in repeated))
        _, history = self.request("GET", "/api/measurements")
        self.assertEqual(history["count"], 1)
        received_at = history["items"][0]["received_at"]
        self.assertEqual(self.request("POST", "/api/measurements", dict(sample, distance_mm=100))[0], 400)
        invalid_changes = [
            {"bin_id": "unknown"}, {"distance_mm": "250"}, {"distance_mm": True},
            {"distance_mm": 0}, {"distance_mm": float("nan")}, {"valid": "false"},
            {"schema_version": True}, {"measurement_id": 0}, {"boot_id": " "},
            {"distance_mm": None}, {"error_code": "no_echo"}, {"device_id": "another_device"},
            {"valid": False}, {"unexpected": 1},
        ]
        for change in invalid_changes:
            with self.subTest(invalid=change):
                status, body = self.request("POST", "/api/measurements", dict(sample, **change))
                self.assertEqual((status, body["error"]), (400, "invalid_payload"))
        for field in ("distance_mm", "is_full", "error_code"):
            missing = dict(sample)
            del missing[field]
            self.assertEqual(self.request("POST", "/api/measurements", missing)[0], 400)
        self.assertEqual(self.request("POST", "/api/measurements", raw=b"{bad")[0], 400)
        status, body = self.request("POST", "/api/measurements", dict(sample, config_version="different"))
        self.assertEqual((status, body["error"]), (409, "config_mismatch"))
        self.assertEqual(self.request("GET", "/api/measurements")[1]["count"], 1)

        failed = dict(sample, measurement_id=2, valid=False, distance_mm=None, is_full=None, error_code="no_echo")
        unknown = dict(sample, measurement_id=3, bin_id="can", is_full=None)
        temporary = dict(sample, measurement_id=4, bin_id="temporary", is_full=True)
        newer = dict(sample, measurement_id=6, measured_uptime_ms=1000)
        older = dict(sample, measurement_id=5, measured_uptime_ms=1)
        new_boot = dict(sample, boot_id="integration_test_boot_2")
        for item in [failed, unknown, temporary, newer, older, new_boot]:
            self.assertEqual(self.request("POST", "/api/measurements", item)[0], 200)
        _, plastic = self.request("GET", "/api/measurements?bin_id=plastic&boot_id=integration_test_boot")
        self.assertEqual(plastic["count"], 4)
        by_id = {item["measurement_id"]: item for item in plastic["items"]}
        self.assertEqual(by_id[1]["distance_mm"], 250)
        self.assertIsNone(by_id[2]["distance_mm"])
        self.assertEqual(by_id[2]["error_code"], "no_echo")
        self.assertEqual(by_id[1]["received_at"], received_at)
        self.assertEqual(self.request("GET", "/api/measurements?limit=101")[0], 400)
        self.assertEqual(self.request("GET", "/api/measurements?bin_id=bad")[0], 400)
        self.assertEqual(self.request("GET", "/api/measurements?limit=2")[1]["count"], 2)

        # 独占锁制造保存失败，验证不能虚报 accepted=true。
        locked_sample = dict(sample, measurement_id=7)
        lock = sqlite3.connect(self.database)
        try:
            lock.execute("BEGIN EXCLUSIVE")
            self.assertEqual(self.request("POST", "/api/measurements", locked_sample),
                             (503, {"error": "storage_unavailable"}))
        finally:
            lock.rollback()
            lock.close()
        self.assertEqual(self.request("POST", "/api/measurements", locked_sample)[0], 200)

        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("GET", "/api/measurements?limit=100")[1]["count"], 8)
        self.assertEqual(self.request("POST", "/api/measurements", sample)[1]["duplicate"], True)
        _, schema = self.request("GET", "/openapi.json")
        documented = schema["paths"]["/api/measurements"]["post"]["responses"]
        self.assertIn("400", documented)
        self.assertNotIn("422", documented)
        self.assertEqual(self.request("GET", "/api/health")[1]["stage"], "lesson_05")
        for path, expected_type in [("/", "text/html"), ("/assets/app.js", "javascript"),
                                    ("/assets/view-model.mjs", "javascript"), ("/assets/lucide.svg", "image/svg+xml")]:
            with urllib.request.urlopen(self.base + path, timeout=5) as page:
                self.assertEqual(page.status, 200)
                self.assertIn(expected_type, page.headers["Content-Type"])
                if expected_type == "image/svg+xml":
                    self.assertEqual(len(ET.fromstring(page.read())), 28)

        # HTTP 层验证心跳检查、状态组合和服务重启后的当前会话。
        before = self.request("GET", "/api/status")[1]
        self.assertEqual(before["device"]["connection_state"], "awaiting_heartbeat")
        heartbeat = dict(schema_version=1, config_version="bins_v1", device_id="sorter_01",
                         boot_id="integration_test_boot", uptime_ms=130000, scan_state="idle",
                         current_bin_id=None, dropped_uploads=0)
        self.assertEqual(self.request("POST", "/api/heartbeat", heartbeat),
                         (200, {"accepted": True, "heartbeat_updated": True, "reason": "new_boot"}))
        self.assertEqual(self.request("POST", "/api/heartbeat", heartbeat)[1]["reason"], "duplicate_uptime")
        current = self.request("GET", "/api/status")[1]
        self.assertTrue(current["device"]["online"])
        self.assertEqual(current["bins"][0]["latest_attempt"]["measurement_id"], 7)
        self.assertEqual(current["bins"][0]["last_valid_measurement"]["distance_mm"], 250)
        for changes in ({"uptime_ms": "130000"}, {"scan_state": "busy"}, {"dropped_uploads": -1},
                        {"current_bin_id": "plastic"}, {"boot_id": " "}, {"device_id": "other"}):
            self.assertEqual(self.request("POST", "/api/heartbeat", dict(heartbeat, **changes))[0], 400)
        self.assertEqual(self.request("POST", "/api/heartbeat", dict(heartbeat, config_version="wrong"))[0], 409)
        self.assertEqual(self.request("POST", "/api/heartbeat", dict(heartbeat, scan_state="measuring", current_bin_id="can", uptime_ms=140000))[0], 200)
        self.assertEqual(self.request("GET", "/api/status")[1]["device"]["current_bin_id"], "can")
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("GET", "/api/status")[1]["device"]["boot_id"], "integration_test_boot")

        # 仅在测试临时目录提供演示标定，生产配置和用户数据库均不变。
        configuration = {
            "config_version": "bins_v2", "sensor_min_mm": 20, "sensor_max_mm": 450,
            "bins": [{"bin_id": b, "empty_distance_mm": 400, "clear_distance_mm": 130,
                      "full_distance_mm": 100} for b in ["plastic", "can", "temporary"]],
        }
        config_file = Path(self.temporary.name) / "bin_config.json"
        config_file.write_text(json.dumps(configuration), encoding="utf-8")
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("POST", "/api/measurements", dict(sample, measurement_id=9))[0], 409)
        new_heartbeat = dict(heartbeat, config_version="bins_v2", uptime_ms=150000)
        self.assertTrue(self.request("POST", "/api/heartbeat", new_heartbeat)[1]["heartbeat_updated"])
        new_measurement = dict(sample, config_version="bins_v2", measurement_id=8, measured_uptime_ms=145000)
        self.assertEqual(self.request("POST", "/api/measurements", new_measurement)[0], 200)
        state = self.request("GET", "/api/status")[1]
        self.assertEqual(state["configuration"]["status"], "ready")
        self.assertEqual(state["bins"][0]["remaining_percent"], 50)
        self.assertEqual(state["bins"][0]["display_state"], "normal")
        self.assertTrue(state["bins"][0]["capacity_fresh"])
        config_file.write_text("{bad", encoding="utf-8")
        self.stop_server()
        self.start_server()
        self.assertEqual(self.request("POST", "/api/heartbeat", new_heartbeat),
                         (503, {"error": "configuration_unavailable"}))
        self.assertEqual(self.request("POST", "/api/measurements", new_measurement)[0], 503)
        self.assertEqual(self.request("GET", "/api/status")[1]["configuration"]["status"], "invalid")

        # 测试页示例也必须是可提交的完整报文，不能丢失 required null 字段。
        _, schema = self.request("GET", "/openapi.json")
        for name, path in [("HeartbeatRequest", "/api/heartbeat"), ("MeasurementRequest", "/api/measurements")]:
            component = schema["components"]["schemas"][name]
            example = schema["paths"][path]["post"]["requestBody"]["content"]["application/json"]["example"]
            self.assertTrue(set(component["required"]).issubset(example))
            self.assertEqual(component["examples"][0], example)
        self.assertIsNone(schema["components"]["schemas"]["HeartbeatRequest"]["examples"][0]["current_bin_id"])
        self.assertIsNone(schema["components"]["schemas"]["MeasurementRequest"]["examples"][0]["error_code"])

        # 恢复测试用默认配置，再直接上传 OpenAPI 示例验证完整请求链路。
        config_file.unlink()
        self.stop_server()
        self.start_server()
        for endpoint in ["/api/heartbeat", "/api/measurements"]:
            example = schema["paths"][endpoint]["post"]["requestBody"]["content"]["application/json"]["example"]
            self.assertEqual(self.request("POST", endpoint, example)[0], 200)


if __name__ == "__main__":
    unittest.main(verbosity=2)
