# BottleScope：容量监测与 RFID 积分后端

这是本项目的 FastAPI + SQLite 网站服务，包含配套静态前端，默认端口 **8000**。

## 功能与设备边界

| 接口 | 用途 |
|---|---|
| `GET /` | 容量监测和 RFID 积分网页，支持繁中／英文 |
| `GET /docs` | Swagger UI 手动测试 |
| `POST /api/measurements` | 保存一次容量测量，包括失败记录 |
| `POST /api/heartbeat` | 心跳及当前开机会话 |
| `GET /api/status` | 三桶状态与预计剩余容量 |
| `GET /api/measurements` | 测量历史 |
| `POST /api/rewards` | reward-v1 八字段积分上传，X-API-Key 鉴权 |
| `GET /api/rewards` | 查看积分流水，需要独立查看口令 |
| `GET /api/reward-balances` | 按设备、卡号及最大批次查询余额 |

详细设备接口：[reward-v1 契约](docs/reward-api.zh.md)。此服务监测、保存和展示数据，不控制电机、不触发刷卡，也不在服务器二次发放积分。

**当前 `bin_config.json` 为 demo 标定**：400／100／130 mm 示例阈值，百分比不能当作实测容量。实际标定要与设备的 `config_version` 一致。

## Python 和首次运行

使用 **Python 3.12 或更高版本**。锁定的 Starlette 要求 Python >=3.11；Ubuntu22.04默认Python3.10不适用本依赖文件，不要直接降低框架版本绕过安装错误。

在本目录内，用已经安装好的 Python3.12 执行：

```bash
python3.12 -m venv .venv312
./.venv312/bin/python -m pip install -r requirements.txt
./.venv312/bin/python -m pip check
./.venv312/bin/python -B setup_rewards.py
./.venv312/bin/python -B setup_rewards.py --device docs-test-sorter --add-device
chmod 700 data
chmod 600 data/reward_credentials.json
./.venv312/bin/python -B -m uvicorn app:app --host 127.0.0.1 --port 8000
```

如果Python3.12尚未安装，应先安装合适解释器，再创建环境。已部署服务器使用的 `.venv312` 不必重建。Windows可用 `py -3.12 -m venv .venv`，通过 `.venv\Scripts\python.exe` 执行同样的pip及setup命令，然后运行 `start.ps1`；`start_lan.ps1` 是显式局域网监听入口。

网页为 `http://127.0.0.1:8000/`，测试页面为 `/docs`。初次启动自动创建 `data/measurements.sqlite3`，并执行 `migrations/001_rewards.sql`；重启保留已有记录。

## 口令与数据

`setup_rewards.py` 在本机生成 `data/reward_credentials.json`，已有文件默认不覆盖：

- `devices`：设备编号到32位小写十六进制上传密钥的映射。
- `viewer_token`：独立查看口令，供网页和GET接口使用，不是RFID卡号或个人账户登录。

新设备可用 `setup_rewards.py --device NEW_DEVICE_ID --add-device` 添加，再在设备端私下配置相同编号和密钥。设备重新启动不应更换编号。不得在未清空离线队列时随意改设备身份。

真实口令、RFID记录、数据库、私钥、日志、`.venv*`、`work`、`outputs` 和 `password` 均不属于可提交源码。Postman环境模板密钥留空。换电脑或服务器不会自动同步数据库；需要保留历史时使用SQLite安全备份／迁移。

可通过环境变量指定私有位置：

```text
BOTTLE_SORTER_DATABASE
BOTTLE_SORTER_CONFIG
BOTTLE_SORTER_REWARD_CREDENTIALS
```

原容量接口没有设备密钥鉴权，RFID查看口令也不保护整个网站。公网部署需另行限制入口访问范围，不能仅因有查看口令就认定所有接口均受保护。

## Wi-Fi 和 Cloudflare

当前交接固件只支持 **可达IPv4 + 明文HTTP + 固定POST /api/rewards**，默认固件端口8080，需要与实际接收端匹配。它不能直接填写 Cloudflare HTTPS 域名。

- 同一局域网直连：后端显式监听 `0.0.0.0:8000`，设备填写接收电脑的LAN IPv4；仍要实测热点互访、防火墙和真实ACK。
- HTTPS远端：需要配置兼容的HTTP入口，或可靠的LAN→HTTPS转发网关。**本目录没有实现转发网关**；本机和云端数据库不会自动同步。
- Cloudflare Quick Tunnel可用于浏览器和Postman演示，临时地址可能在Tunnel重建后变化。

## Ubuntu 持续运行

根目录的 `install-bottlesorter-services.sh` 和 `show-bottlesorter-url.sh` 适配当前部署约定：`ubuntu`用户、`/home/ubuntu/bottlesorter`、`.venv312`。它们建立后端和Quick Tunnel两个systemd服务，保留原数据库和口令。新机器路径不同时必须先适配，不能直接在仓库任意目录执行。

详见 [常驻服务说明](docs/ubuntu-services.zh.md)。本次仓库上传不等于已经安装或验证远端服务。

## Postman 与自动测试

导入 `postman/` 中的合集和环境模板，配置自己接收端的密钥。先确认目标允许模拟写入，再设置 `allow_test_writes=true`，每轮按00至33执行。每轮生成新卡号和批次，只保存四笔有效模拟记录；不使用真实设备身份。详见 [Postman操作](docs/postman-guide.zh.md)。

在本目录运行独立测试：

```bash
mkdir -p outputs
./.venv312/bin/python -B -m unittest discover -s tests -v
node --test tests/test_view_model.mjs
```

测试在本目录的忽略目录outputs中创建独立数据库和本机服务，不写正式数据库。Windows临时目录权限受限时，需要在允许项目测试的终端运行。

已有本地验证：27项Python测试、7项前端显示逻辑测试；RFID Postman合集曾用隔离库执行两轮，每轮34请求和98项断言通过。覆盖重复／冲突／并发／乱序、真实SQLite事务失败、UID前导0和余额行为。实际结果须以当前提交的验证输出为准，不能据此声称真实硬件已经通过。

`tests/vendor/contract_test.py` 来自队友交接包 `Tools/contract_test.py`，保留原始工具内容。前端Inter字体和Lucide图标的许可证、来源信息保留在 `frontend/dist/assets/`。
