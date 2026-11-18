"""固定 reward-v1 设备协议与独立、受保护的网页查询接口。"""
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Security
from fastapi.responses import PlainTextResponse
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.concurrency import run_in_threadpool

from reward_store import RewardConflict, query_rewards, save_reward

EXAMPLE = dict(device='docs-test-sorter', batch=42, uid='DEADBEEF', earned=20,
               total=120, bottles=1, cans=1, rejected=0)


class RewardEvent(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, json_schema_extra={'examples': [EXAMPLE]})
    device: str = Field(min_length=1, max_length=32, pattern=r'^[A-Za-z0-9_-]+$')
    batch: int = Field(ge=1, le=4294967295)
    uid: str = Field(pattern=r'^(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})$')
    earned: int = Field(ge=0, le=4294967295)
    total: int = Field(ge=0, le=4294967295)
    bottles: int = Field(ge=0, le=5)
    cans: int = Field(ge=0, le=5)
    rejected: int = Field(ge=0, le=5)

    @model_validator(mode='after')
    def check_relationships(self):
        eligible = self.bottles + self.cans
        if not 1 <= eligible + self.rejected <= 5 or self.earned > self.total:
            raise ValueError('invalid counts or total')
        if (eligible == 0 and self.earned != 0) or (eligible > 0 and
                (self.earned == 0 or self.earned % eligible != 0)):
            raise ValueError('invalid earned points')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', self.device) or not re.fullmatch(
                r'(?:[0-9A-F]{8}|[0-9A-F]{14}|[0-9A-F]{20})', self.uid):
            raise ValueError('invalid identity')
        return self


def load_credentials():
    path = Path(os.environ.get('BOTTLE_SORTER_REWARD_CREDENTIALS',
        str(Path(__file__).parent / 'data' / 'reward_credentials.json')))
    try:
        config = json.loads(path.read_text(encoding='utf-8'))
        devices, viewer = config['devices'], config['viewer_token']
        if not isinstance(devices, dict) or not devices or not re.fullmatch(r'[0-9a-f]{64}', viewer):
            raise ValueError()
        if any(not re.fullmatch(r'[A-Za-z0-9_-]{1,32}', d) or not isinstance(k, str)
               or not re.fullmatch(r'[0-9a-f]{32}', k) for d, k in devices.items()):
            raise ValueError()
        return config
    except (OSError, ValueError, KeyError, TypeError):
        raise HTTPException(503, 'rewards_not_configured') from None


device_key = APIKeyHeader(name='X-API-Key', scheme_name='RewardDeviceKey', auto_error=False)
viewer_key = HTTPBearer(scheme_name='RewardViewer', auto_error=False)


def authenticate_device(key: Annotated[str | None, Security(device_key)]):
    config = load_credentials()
    if key is None or not re.fullmatch(r'[0-9a-f]{32}', key):
        raise HTTPException(401, 'invalid_device_key')
    allowed = [d for d, stored in config['devices'].items() if secrets.compare_digest(key, stored)]
    if not allowed:
        raise HTTPException(401, 'invalid_device_key')
    return allowed


def authenticate_viewer(credentials: Annotated[HTTPAuthorizationCredentials | None, Security(viewer_key)]):
    config = load_credentials()
    token = credentials.credentials if credentials else ''
    if not re.fullmatch(r'[0-9a-f]{64}', token) or not secrets.compare_digest(token, config['viewer_token']):
        raise HTTPException(401, 'viewer_auth_required', headers={'WWW-Authenticate': 'Bearer'})


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate field')
        result[key] = value
    return result


def make_reward_router(database_path: Path):
    router = APIRouter(tags=['RFID 回收積分'])

    @router.post('/api/rewards', response_class=PlainTextResponse,
        summary='設備上傳積分：成功後回覆 ACK',
        description='在 Authorize 的 RewardDeviceKey 輸入設備密鑰。僅資料庫提交成功才回覆 ACK；total 已包含本次 earned。',
        openapi_extra={'requestBody': {'required': True, 'content': {'application/json': {
            'schema': RewardEvent.model_json_schema(), 'example': EXAMPLE}}}},
        responses={400: {'description': 'invalid_payload'}, 401: {'description': 'invalid_device_key'},
                   409: {'description': 'batch_conflict'}, 503: {'description': 'storage_unavailable'}})
    async def upload(request: Request, allowed=Depends(authenticate_device)):
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 2048:
                return PlainTextResponse('invalid_payload\n', status_code=400)
        try:
            payload = json.loads(body, object_pairs_hook=unique_object)
            event = RewardEvent.model_validate(payload)
        except (ValueError, TypeError, UnicodeError):
            return PlainTextResponse('invalid_payload\n', status_code=400)
        if event.device not in allowed:
            return PlainTextResponse('invalid_device_key\n', status_code=401)
        try:
            await run_in_threadpool(save_reward, database_path, event.model_dump())
        except RewardConflict:
            return PlainTextResponse('batch_conflict\n', status_code=409)
        except sqlite3.Error:
            return PlainTextResponse('storage_unavailable\n', status_code=503)
        return PlainTextResponse(f'ACK {event.batch}\n', headers={'Connection': 'close'})

    @router.get('/api/rewards', summary='查詢積分流水（需要查看口令）', dependencies=[Depends(authenticate_viewer)])
    def history(device: str | None = Query(None, min_length=1, max_length=32),
                uid: str | None = Query(None, min_length=1, max_length=20),
                limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        return query_rewards(database_path, device=device, uid=uid, limit=limit, offset=offset)

    @router.get('/api/reward-balances', summary='各卡各設備最新餘額（按最大 batch）', dependencies=[Depends(authenticate_viewer)])
    def balances(device: str | None = Query(None, min_length=1, max_length=32),
                 uid: str | None = Query(None, min_length=1, max_length=20),
                 limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        return query_rewards(database_path, device=device, uid=uid, limit=limit, offset=offset, balances=True)

    return router
