"""把需求文件中的测量字段，写成可以执行的检查规则。"""

from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


BinId = Literal["plastic", "can", "temporary"]
ErrorCode = Literal["no_echo", "out_of_range", "unstable", "measurement_failed"]

DEMO_MEASUREMENT = {
    "schema_version": 1,
    "config_version": "bins_v1",
    "device_id": "sorter_01",
    "boot_id": "lesson03_demo",
    "measurement_id": 1,
    "measured_uptime_ms": 125000,
    "bin_id": "plastic",
    "distance_mm": 250,
    "valid": True,
    "is_full": False,
    "error_code": None,
}


class MeasurementRequest(BaseModel):
    # strict 避免把 "false"、"250" 等错误类型悄悄转换后接受。
    model_config = ConfigDict(
        strict=True,
        extra="forbid",
        allow_inf_nan=False,
        json_schema_extra={"examples": [DEMO_MEASUREMENT]},
    )

    schema_version: int = Field(ge=1, le=1)
    config_version: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    boot_id: str = Field(min_length=1)
    measurement_id: int = Field(ge=1)
    measured_uptime_ms: int = Field(ge=0, le=4294967295)
    bin_id: BinId
    # 没有默认值：这三个字段可以为 null，但不能省略。
    distance_mm: float | None = Field(gt=0)
    valid: bool
    is_full: bool | None
    error_code: ErrorCode | None

    @field_validator("config_version", "device_id", "boot_id")
    @classmethod
    def nonblank_identifier(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identifier must not be blank")
        return value

    @model_validator(mode="after")
    def check_measurement_consistency(self) -> Self:
        # 字段分别合法还不够，还要检查它们之间的关系。
        if self.valid:
            if self.distance_mm is None or self.error_code is not None:
                raise ValueError("valid measurement needs distance_mm and error_code=null")
        elif (
            self.distance_mm is not None
            or self.is_full is not None
            or self.error_code is None
        ):
            raise ValueError("failed measurement needs distance_mm=null, is_full=null and an error_code")
        return self


DEMO_HEARTBEAT = {
    "schema_version": 1,
    "config_version": "bins_v1",
    "device_id": "sorter_01",
    "boot_id": "lesson03_demo",
    "uptime_ms": 130000,
    "scan_state": "idle",
    "current_bin_id": None,
    "dropped_uploads": 0,
}


class HeartbeatRequest(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", json_schema_extra={"examples": [DEMO_HEARTBEAT]})

    schema_version: int = Field(ge=1, le=1)
    config_version: str = Field(min_length=1)
    device_id: str = Field(min_length=1)
    boot_id: str = Field(min_length=1)
    uptime_ms: int = Field(ge=0, le=4294967295)
    scan_state: Literal["idle", "rotating", "settling", "measuring", "error"]
    current_bin_id: BinId | None
    dropped_uploads: int = Field(ge=0)

    @field_validator("config_version", "device_id", "boot_id")
    @classmethod
    def nonblank_identifier(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identifier must not be blank")
        return value

    @model_validator(mode="after")
    def check_idle_bin(self) -> Self:
        if self.scan_state == "idle" and self.current_bin_id is not None:
            raise ValueError("idle heartbeat requires current_bin_id=null")
        return self


class MeasurementAcknowledgement(BaseModel):
    accepted: bool
    measurement_id: int
    duplicate: bool | None = None


class HeartbeatAcknowledgement(BaseModel):
    accepted: bool
    heartbeat_updated: bool
    reason: Literal["new_boot", "advanced_uptime", "duplicate_uptime", "older_uptime", "retired_boot"]
