"""读取共用标定清单；缺少或错误的实测参数不能用于计算容量。"""

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from schemas import BinId


class BinCalibration(BaseModel):
    # 清单还可包含桶架角度等固件参数；后端保留自己的校验边界。
    model_config = ConfigDict(strict=True, extra="allow", allow_inf_nan=False)
    bin_id: BinId
    empty_distance_mm: float | None = Field(default=None, gt=0)
    full_distance_mm: float | None = Field(default=None, gt=0)
    clear_distance_mm: float | None = Field(default=None, gt=0)


class BinConfiguration(BaseModel):
    model_config = ConfigDict(strict=True, extra="allow", allow_inf_nan=False)
    config_version: str = Field(min_length=1)
    calibration_mode: Literal["measured", "demo"] = "measured"
    bins: list[BinCalibration] = Field(min_length=3, max_length=3)
    sensor_min_mm: float | None = Field(default=None, gt=0)
    sensor_max_mm: float | None = Field(default=None, gt=0)
    device_offline_after_ms: int = Field(default=30000, gt=0)
    measurement_stale_after_ms: int = Field(default=120000, gt=0)
    near_full_remaining_pct: float = Field(default=20, ge=0, le=100)

    @model_validator(mode="after")
    def check_calibration(self) -> Self:
        if {b.bin_id for b in self.bins} != {"plastic", "can", "temporary"}:
            raise ValueError("bins must contain each bin_id exactly once")
        if self.sensor_min_mm is not None and self.sensor_max_mm is not None:
            if self.sensor_min_mm >= self.sensor_max_mm:
                raise ValueError("sensor_min_mm must be less than sensor_max_mm")
        for bin_config in self.bins:
            distances = [bin_config.empty_distance_mm, bin_config.clear_distance_mm, bin_config.full_distance_mm]
            if all(value is not None for value in distances):
                if not distances[0] > distances[1] > distances[2]:
                    raise ValueError(f"{bin_config.bin_id}: require empty > clear > full")
            for value in distances:
                if value is not None:
                    if self.sensor_min_mm is not None and value < self.sensor_min_mm:
                        raise ValueError(f"{bin_config.bin_id}: calibration below sensor range")
                    if self.sensor_max_mm is not None and value > self.sensor_max_mm:
                        raise ValueError(f"{bin_config.bin_id}: calibration above sensor range")
        return self


@dataclass(frozen=True)
class BackendConfiguration:
    config_version: str = "bins_v1"
    status: str = "not_configured"
    protocol_ready: bool = True
    data: BinConfiguration | None = None
    errors: tuple[str, ...] = ()

    def summary(self) -> dict:
        return {"config_version": self.config_version, "status": self.status,
                "calibration_mode": self.data.calibration_mode if self.data else None,
                "errors": list(self.errors)}

    def calibration_status(self, bin_id: str) -> str:
        """M1 可只标定一个桶，其余桶继续明确标为未配置。"""
        if self.status == "invalid":
            return "invalid"
        if self.data is None or self.data.sensor_min_mm is None or self.data.sensor_max_mm is None:
            return "not_configured"
        calibration = next((b for b in self.data.bins if b.bin_id == bin_id), None)
        if calibration is None:
            return "not_configured"
        values = (calibration.empty_distance_mm, calibration.full_distance_mm, calibration.clear_distance_mm)
        return "ready" if all(value is not None for value in values) else "not_configured"

    @property
    def device_offline_after_ms(self) -> int:
        return self.data.device_offline_after_ms if self.data else 30000

    @property
    def measurement_stale_after_ms(self) -> int:
        return self.data.measurement_stale_after_ms if self.data else 120000

    @property
    def near_full_remaining_pct(self) -> float:
        return self.data.near_full_remaining_pct if self.data else 20


def load_configuration(path: Path) -> BackendConfiguration:
    try:
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        return BackendConfiguration(errors=("No measured calibration file has been provided.",))
    except (OSError, ValueError):
        return BackendConfiguration(status="invalid", protocol_ready=False, errors=("Calibration file cannot be read as JSON.",))
    if not isinstance(raw, dict) or not isinstance(raw.get("config_version"), str) or not raw["config_version"].strip():
        return BackendConfiguration(status="invalid", protocol_ready=False, errors=("config_version must be a nonblank string.",))
    version = raw["config_version"]
    try:
        data = BinConfiguration.model_validate(raw)
    except ValidationError as exc:
        errors = tuple(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
        return BackendConfiguration(config_version=version, status="invalid", errors=errors)
    missing = []
    for key in ("sensor_min_mm", "sensor_max_mm"):
        if getattr(data, key) is None:
            missing.append(key)
    for bin_config in data.bins:
        for key in ("empty_distance_mm", "full_distance_mm", "clear_distance_mm"):
            if getattr(bin_config, key) is None:
                missing.append(f"{bin_config.bin_id}.{key}")
    return BackendConfiguration(
        config_version=version,
        status="not_configured" if missing else "ready",
        data=data,
        errors=tuple(f"Missing measured parameter: {key}" for key in missing),
    )


def remaining_percent(measurement: dict | None, bin_id: str, configuration: BackendConfiguration) -> float | None:
    if not measurement or not measurement["valid"] or configuration.calibration_status(bin_id) != "ready":
        return None
    if measurement["config_version"] != configuration.config_version:
        return None
    calibration = next(b for b in configuration.data.bins if b.bin_id == bin_id)
    fraction = (measurement["distance_mm"] - calibration.full_distance_mm) / (calibration.empty_distance_mm - calibration.full_distance_mm)
    return max(0.0, min(100.0, 100.0 * fraction))
