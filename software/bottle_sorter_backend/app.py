"""第四课：共用标定配置、容量计算和供前端使用的显示状态。"""

from contextlib import asynccontextmanager
import logging
import mimetypes
import os
from pathlib import Path
import sqlite3

from fastapi import FastAPI, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from configuration import load_configuration
from schemas import DEMO_HEARTBEAT, DEMO_MEASUREMENT, BinId, HeartbeatAcknowledgement, HeartbeatRequest, MeasurementAcknowledgement, MeasurementRequest
from status import get_status
from storage import MeasurementConflict, initialize_database, list_measurements, save_heartbeat, save_measurement
from rewards import make_reward_router


PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_PATH = Path(os.environ.get("BOTTLE_SORTER_DATABASE", str(PROJECT_ROOT / "data" / "measurements.sqlite3")))
CONFIGURATION_PATH = Path(os.environ.get("BOTTLE_SORTER_CONFIG", str(PROJECT_ROOT / "bin_config.json")))
CONFIGURATION = load_configuration(CONFIGURATION_PATH)
DEVICE_ID = "sorter_01"
CONFIG_VERSION = CONFIGURATION.config_version
FRONTEND_DIRECTORY = PROJECT_ROOT / "frontend" / "dist"
# Some Windows file associations classify .mjs as plain text; browsers require JavaScript MIME.
mimetypes.add_type("application/javascript", ".mjs")
logger = logging.getLogger("uvicorn.error")


@asynccontextmanager
async def lifespan(application: FastAPI):
    initialize_database(DATABASE_PATH)
    yield


app = FastAPI(
    title="Bottle Sorter 后端入门",
    version="0.5.0",
    description="监测页面与数据接口。缺少实测标定时不生成容量百分比。",
    lifespan=lifespan,
)
app.mount("/assets", StaticFiles(directory=FRONTEND_DIRECTORY / "assets"), name="frontend-assets")
app.include_router(make_reward_router(DATABASE_PATH))


class EchoRequest(BaseModel):
    # 定义请求应当具有的形状；只接受 message 这一个字段。
    model_config = ConfigDict(extra="forbid", strict=True)
    message: str = Field(min_length=1, max_length=200, examples=["你好，后端！"])


class EchoResponse(BaseModel):
    received_message: str
    reply: str


@app.exception_handler(RequestValidationError)
async def invalid_request(request: Request, exc: RequestValidationError):
    # 后续设备协议要求错误请求使用 HTTP 400，这里提前保持一致。
    return JSONResponse(
        status_code=400,
        content={
            "error": "invalid_payload",
            "details": [
                {"field": ".".join(map(str, item["loc"])), "message": item["msg"]}
                for item in exc.errors()
            ],
        },
    )


@app.exception_handler(sqlite3.Error)
async def database_failure(request: Request, exc: sqlite3.Error):
    logger.error("Database operation failed", exc_info=exc)
    # 设备可重试 5xx；没有写入成功时，绝不回复 accepted=true。
    return JSONResponse(status_code=503, content={"error": "storage_unavailable"})


@app.get("/", include_in_schema=False)
def home():
    return FileResponse(FRONTEND_DIRECTORY / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/health", summary="检查后端是否运行")
def health():
    return {"status": "ok", "stage": "lesson_05", "storage_enabled": True}


@app.post("/api/echo", response_model=EchoResponse, summary="发送一句话并取得回复")
def echo(body: EchoRequest):
    # body.message 是检查合格的请求内容；return 的结果会转成 JSON 回复。
    return EchoResponse(received_message=body.message, reply=f"后端收到：{body.message}")


@app.post(
    "/api/measurements",
    summary="保存一次测量（成功或失败均记录）",
    response_model=MeasurementAcknowledgement,
    response_model_exclude_none=True,
    responses={400: {"description": "invalid_payload"}, 409: {"description": "config_mismatch"}, 503: {"description": "storage_unavailable"}},
)
def upload_measurement(body: MeasurementRequest):
    if not CONFIGURATION.protocol_ready:
        return JSONResponse(status_code=503, content={"error": "configuration_unavailable"})
    if body.device_id != DEVICE_ID:
        return JSONResponse(status_code=400, content={"error": "invalid_payload", "reason": "unknown device_id"})
    if body.config_version != CONFIG_VERSION:
        return JSONResponse(status_code=409, content={"error": "config_mismatch", "expected_config_version": CONFIG_VERSION})
    try:
        duplicate = save_measurement(DATABASE_PATH, body)
    except MeasurementConflict as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_payload", "reason": str(exc)})
    response = {"accepted": True, "measurement_id": body.measurement_id}
    if duplicate:
        response["duplicate"] = True
    return response


@app.get("/api/measurements", response_model=dict, summary="查询已保存的测量历史（最新收录的在前）")
def measurement_history(
    device_id: str = Query(default=DEVICE_ID, min_length=1),
    boot_id: str | None = Query(default=None, min_length=1),
    bin_id: BinId | None = None,
    limit: int = Query(default=20, ge=1, le=100),
):
    items = list_measurements(DATABASE_PATH, device_id=device_id, boot_id=boot_id, bin_id=bin_id, limit=limit)
    return {"items": items, "count": len(items)}


@app.post(
    "/api/heartbeat", summary="接收设备心跳并识别当前启动",
    response_model=HeartbeatAcknowledgement,
    responses={400: {"description": "invalid_payload"}, 409: {"description": "config_mismatch"}, 503: {"description": "storage_unavailable"}},
)
def upload_heartbeat(body: HeartbeatRequest):
    if not CONFIGURATION.protocol_ready:
        return JSONResponse(status_code=503, content={"error": "configuration_unavailable"})
    if body.device_id != DEVICE_ID:
        return JSONResponse(status_code=400, content={"error": "invalid_payload", "reason": "unknown device_id"})
    if body.config_version != CONFIG_VERSION:
        return JSONResponse(status_code=409, content={"error": "config_mismatch", "expected_config_version": CONFIG_VERSION})
    outcome = save_heartbeat(DATABASE_PATH, body)
    return {"accepted": True, **outcome}


@app.get("/api/status", response_model=dict, summary="读取设备在线情况与三桶状态")
def current_status():
    return get_status(DATABASE_PATH, DEVICE_ID, configuration=CONFIGURATION)


def custom_openapi():
    # 实际检查错误返回 400，文档同步移除框架自动添加的 422。
    if app.openapi_schema is None:
        schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
        for path in schema["paths"].values():
            for operation in path.values():
                responses = operation.get("responses", {})
                if responses.pop("422", None) is not None:
                    responses.setdefault("400", {"description": "invalid_payload"})
        # get_openapi 会省略嵌套示例里的 None。生成后恢复，确保必填 null
        # 字段确实出现在 Swagger 编辑框中，用户可直接发送完整示例。
        for name, endpoint, example in [
            ("HeartbeatRequest", "/api/heartbeat", DEMO_HEARTBEAT),
            ("MeasurementRequest", "/api/measurements", DEMO_MEASUREMENT),
        ]:
            schema["components"]["schemas"][name]["examples"] = [example.copy()]
            schema["paths"][endpoint]["post"]["requestBody"]["content"]["application/json"]["example"] = example.copy()
        app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi
