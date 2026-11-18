# RFID 设备上传接口 reward-v1

接收端运行在HTTP端口8000；设备必须能实际访问该IP与端口。HTTPS网页地址不等于当前固件可连接的IPv4 HTTP入口。这里的地址和密钥都不包含真实部署配置。

## 请求

```text
POST /api/rewards
Content-Type: application/json
X-API-Key: <对应设备的32位小写十六进制密钥>
```

```json
{
  "device": "docs-test-sorter",
  "batch": 42,
  "uid": "DEADBEEF",
  "earned": 20,
  "total": 120,
  "bottles": 1,
  "cans": 1,
  "rejected": 0
}
```

示例设备为独立手动测试身份；真实设备需事先登记并使用自己的密钥。请求只能包含上述8字段，不能额外要求时间、姓名、容量或版本号。

| 字段 | 要求及意义 |
|---|---|
| device | 1–32字符，仅A–Z、a–z、0–9、下划线、连字符；大小写敏感 |
| batch | 整数1–4294967295，设备全局持久批次；不是每卡从1开始 |
| uid | 大写十六进制字符串，长度8／14／20；保留前导0 |
| earned | 整数0–4294967295，本批已发放的新增积分 |
| total | 整数0–4294967295，包含本批earned的绝对累计值 |
| bottles, cans, rejected | 各整数0–5，本批瓶／罐／其他件数 |

总件数1–5；earned<=total；有效件bottles+cans为0时earned必须为0，否则earned为正且可被有效件数整除。拒绝布尔、浮点和数字字符串；不固定每件10分。旧历史可能未上传，不能要求total等于服务器已接收earned之和。

设备上报粒度是完成分类、清扫、刷卡领奖并本地保存成功后的批次事件，不是每扫到一张卡或经过一个物品就发送。

## 成功确认与幂等

唯一键是(device,batch)。相同键的8字段相同：不新增记录，不改首次接收时间，返回同一ACK；字段顺序不影响比较。相同键的合法内容不同：409，不覆盖。

仅在SQLite提交成功，或确认完全相同的已提交记录存在后，返回HTTP200，正文为ASCII `ACK ` + batch十进制数字 + 一个LF。例如42的正文是 `ACK 42\n`，7字节。

要求HTTP/1.0或1.1、正确Content-Length，无JSON包装、重定向、压缩、Transfer-Encoding或chunked；每行响应头不超过127个非CRLF字节。真实公网代理路径也必须独立验证。

| 状态 | 含义 |
|---|---|
| 400 | 字段、类型或业务关系错误 |
| 401 | 密钥缺少／错误，或与device不对应 |
| 409 | 同设备同批次内容冲突 |
| 503 | 口令配置或数据库不可用，写入／提交失败 |

错误不能ACK。现有固件收到4xx不会自动丢掉队首，需修复根因，不能改device/batch绕过冲突；离线队列行为必须在真实设备上验证。

## 查询

GET /api/rewards：积分流水，支持device、uid、limit(1–100)、offset(>=0)。按服务器收录顺序倒序。

GET /api/reward-balances：按(device,uid)取最大batch对应的total及last_batch。较小批次晚到只增加历史，不覆盖新余额。同UID跨设备不自动合并，不重复累加total或earned。

两个GET都需要 `Authorization: Bearer <独立viewer_token>`。它是统一查看凭证，不是每位持卡人的登录系统，也不能作为设备上传密钥。

received_at由后端以UTC写入，表示首次接收时间，不是实际投料／刷卡时间。原容量接口继续独立使用measurement和heartbeat协议。
