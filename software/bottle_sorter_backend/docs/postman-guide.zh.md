# BottleSorter RFID Postman 测试合集

这套合集用于模拟设备上传并检查后端，不能替代真实 RFID、ESP8266 或手机热点测试。

## 1. 导入文件

在 Postman 中点击 Import，导入：

- `BottleSorter-RFID.postman_collection.json`：34 个请求及自动断言。
- `BottleSorter-RFID-Local-8000.postman_environment.json`：本机环境。
- `BottleSorter-RFID-Remote-Linux.postman_environment.json`：远端环境模板，可先不使用。

两个环境的密钥均为空，不含你的真实密钥。旧容量合集仍在原 `outputs/postman/`，本次没有覆盖。

## 2. 选择并填写本机环境

右上角选择 `BottleSorter RFID — Local-8000`，填写：

| 变量 | 本机值 | 原理 |
|---|---|---|
| base_url | http://127.0.0.1:8000 | 同一后端服务地址，不加 /docs，不加末尾斜线 |
| test_device | docs-test-sorter | 独立模拟设备，不能改成真实设备 ID |
| reward_device_key | 私有文件 devices → docs-test-sorter 对应的值 | 用于 POST 的 X-API-Key |
| reward_viewer_token | 私有文件 viewer_token 的值 | 用于 GET 的 Bearer 查看口令 |
| allow_test_writes | true | 明确允许把模拟记录写入当前选中的后端 |

本机私有文件：项目运行目录中的 `data/reward_credentials.json`。
只在自己的 Postman 中填写；不要把填写后的环境文件、控制台请求头或口令截图分享出去。请使用本地值／不要主动共享含口令的变量值；将变量标为 secret 只是显示保护，不等于可以公开导出。

如果使用 Postman 网页版测试 localhost，需要可访问本机的 Desktop Agent；使用桌面版更直接。

成功标准：先运行 00，HTTP 200 且 Test Results 通过。
如果脚本提示口令格式不对，先检查是否复制错字段、是否残留引号；如果网络连接失败，先确认原后端已经在 8000 启动。

## 3. 两种运行方式

### 手动学习

按 00 → 01 → 02 → 03 顺序发送，理解「初始化 → 首次写入 → 重发 → 查询」。随后继续 04 到 33。

- `Send`：发送当前请求。
- `Body`：POST 发送的八字段数据。
- `Scripts / Post-response`：自动核对响应的 JavaScript。
- `Test Results`：查看断言是否通过。

不要自己固定 test_uid 或修改自动生成的批次变量。00 每轮会生成新的、保留前导 0 的模拟卡号及一组批次，上一轮记录不会自动删除。
同一轮内可以重复发送某个请求；开始新一轮必须重新执行 00。不要同时在多个客户端／Runner 中并行运行同一测试设备。

### 一次运行全部

选择合集 → Run collection／Collection Runner → 勾选全部请求，保持顺序 → 选择对应环境 → Iterations 设为 1 → Run。

每一轮恰写入四笔有效模拟积分，针对同一张本轮卡号：首笔、较新一笔、晚到旧批次、全部拒收。
反复运行会增加历史测试记录，每轮使用新卡号；不要在生产库中无意运行大量轮次。

## 4. 测试目录与成功标准

| 编号 | 测什么 | 应看到什么 |
|---|---|---|
| 00 | 健康检查及准备本轮身份 | 200，生成本轮卡号和批次 |
| 01–04 | 首次保存、相同重发、字段顺序变化 | POST 200，精确 ACK；查流水只有一笔 |
| 05–06 | 同批次换 UID 或累计积分 | 409，原记录不覆盖 |
| 07–09 | 新批次、旧批次晚到、0 分拒收 | 都有正确 ACK |
| 10 | 四笔流水 | 恰好四笔，首笔接收时间未被重发改变 |
| 11 | 最新余额 | total=130，last_batch 为本轮最大批次 |
| 12–13 | 分页和无结果筛选 | 总数4，当页2；不存在卡号返回空数组 |
| 14–19 | 缺失／错误口令、设备身份不符 | 401 |
| 20–30 | 缺字段、多字段、布尔／小数、数量／积分关系等错误 | 400 |
| 31 | 最后再查流水 | 仍只有本轮四笔，非法请求未写入 |
| 32–33 | 原容量状态及测量历史只读回归 | 200，原接口结构正常 |

负面案例的 HTTP 400／401／409 是预期结果：断言通过才算测试成功，不要求每个请求都返回 200。

ACK 会检查正文末尾恰好一个 LF、Content-Length、text/plain、无分块／压缩、标头长度。Postman 使用它自身的 HTTP 实现；这些检查不能代替真实 Mega 的响应解析验证。原始 HTTP/1.0 契约及数据库并发／提交失败由项目 Python 测试单独验证。

## 5. 远端环境

选择 `Remote-Linux`，将 base_url 填为部署好的 HTTPS 地址，例如 `https://你的域名`（这是说明占位符，不能原样填写）。填写远端服务器生成的测试密钥和查看口令，并确认是否允许测试写入。

更换环境就是让同一套请求访问另一个后端；不需要重新修改每个请求。远端不能填 `127.0.0.1`，否则访问的是自己电脑。

如果远端按来源 IP 或反向代理登录限制访问，要先在服务器端给你的测试入口配置正确的访问范围。若收到 301／302／403／HTML，不能当作设备接口验收通过。

## 6. 不通过时怎样看

- 01 返回 401：检查 test_device 与所用密钥是否对应。设备密钥与查看口令不能互换。
- GET 返回 401：检查 reward_viewer_token。
- 01 返回 409：可能跳过了00、改动了本轮数据，或多个客户端复用了批次；先核对记录，不要覆盖旧记录。
- 提示 allow_test_writes：这是写入保护，确认当前后端是允许写入模拟数据的环境后再设为 true。
- 期望4笔但实际更多／更少：检查是否完整按顺序执行，是否重复执行00后只跑了部分请求。
- 503：检查远端私有口令文件、数据目录权限与数据库，不应靠重复加分或改成功响应来绕过。

历史隔离库验证为两轮、每轮34请求和98项断言通过；运行时以你自己的 Test Results 为准，历史结果不代表你填写后的远端环境已经通过。

参考：
- https://learning.postman.com/docs/tests-and-scripts/write-scripts/test-scripts/
- https://learning.postman.com/docs/tests-and-scripts/running-collections/intro-to-collection-runs
