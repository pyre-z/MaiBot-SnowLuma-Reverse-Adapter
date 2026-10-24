# Changelog

本项目从 `MaiBot-SnowLuma-Adapter` 1.1.8 派生，上游历史见 `UPSTREAM-CHANGELOG.md`。

## 3.0.0

### 破坏性变更

- 移除正向 WebSocket 客户端（`transport/forward_client.py` 与 `transport/factory.py`），
  适配器只保留反向 WS 服务端：SnowLuma / NapCat 连入，适配器监听。
- 移除 `[plugin].transport_mode` 与整个 `[client]` 配置段；`client_type` 迁至 `[plugin].client_type`，
  其余连接参数（server / port / token / reconnect_delay_sec / build_ws_url）随正向客户端一并删除。
- `transport_config()` 不再按模式分派，运行时状态上报改用 `[server]` 的 `connection_id` 与
  `endpoint_url()`。
- 配置结构版本升到 `3.0.0`，旧配置由迁移器自动改写：`[client].client_type` 搬到 `[plugin]`，
  其它 `[client]` 内容与旧版 `luma_client` / `napcat_server` / `connection` 段落直接丢弃并打 warning。

## 2.1.0

### 新特性

- `qq_face_parse_mode` 新增 `vision`：把 QQ 内置表情渲染成离线生成的视觉描述
  （`[QQ小表情·幽灵｜白色圆润的小幽灵上下漂浮眨眼…]`），补上「模型只拿到名字、误以为图片没加载」的语义缺口。
- 新增 `scripts/build_face_vision.py`：离线批量生成描述表。QFace 128px 静态图与 qzone 24px 动作帧条
  **同一次调用**送入 VLM（静态定形象、动作帧定动作），产物 `snowluma_reverse/data/face_vision.json`；
  幂等、可增量、缺表自动回退 `emoji` → `[中文名]`。

### 修复

- `.gitignore` 的 `data/` 会连带忽略 `snowluma_reverse/data/`，导致 `faces.py` / `emoji.py` 等
  必需模块从未进入仓库（新克隆无法运行）；改为 `/data/` 仅忽略根目录运行时数据。

## 2.0.0

### 结构重构

- 迁入 `snowluma_reverse/` flat 包，根目录 `plugin.py` 仅作为 `create_plugin()` 加载入口。
- 使用 uv、pytest 和可选依赖组管理开发及运行环境。
- 拆分配置、传输、协议、媒体、数据及运行时目录，新增架构说明和 GPL-3.0 LICENSE。

### 缺陷修复

- D1：反向握手校验 `expect_self_id`，缺少或不匹配时以 1008 拒绝。
- D2：记录传输模式，热切换时停止旧连接并通过传输工厂重建运行时。
- D3：活动传输的 `connection_id` 与 `heartbeat_interval` 统一从 `transport_config()` 获取。
- D4：`/healthz` 默认不暴露 `self_id`，正确令牌可查看。
- D5：修正文档监听地址说明并补齐 GPL-3.0 全文。
- D6：manifest 升至 2.0.0，Host 最大版本放宽至 999.999.999，SDK 范围保持不变。
- D7：动作服务使用 `Transport` 抽象接口。
- D8：提交 uv.lock，保留运行时配置与虚拟环境忽略规则。

## 1.0.0

### 新增

- 反向 WebSocket 传输层 `transport_server.py`：适配器监听端口，SnowLuma 以 OneBot v11
  反向 WS 客户端身份连入，事件与 action 复用同一条双工连接。
- `[plugin].transport_mode`：`client`（上游行为，默认）/ `server`（反向模式）。
- `[server]` 配置节：监听地址/端口/路径、token、来源 IP 白名单（支持 CIDR）、
  限定机器人账号、心跳、动作超时、最大消息长度。
- `GET /healthz`：返回监听与连接状态，便于容器探活与反代监控。
- 鉴权：`Authorization` 头与 `access_token` 参数双通道，`hmac.compare_digest` 比较；
  未配置 token 且未配置 IP 白名单时拒绝启动。
- 连接管理：同账号重连替换旧连接（1001），不同 `X-Self-ID` 并发拒绝（1008）。
- 就绪前事件排队：等网关激活后再注入，避免 `E_METHOD_NOT_ALLOWED`。
- `tests/test_transport_server.py`：不依赖 SDK 的端到端传输层测试。

### 修复（相对直接改造上游时会踩到的点）

- 连接建立回调与读循环并发执行，避免探测动作的 echo 无人接收而死锁。
- `WebSocketResponse` 显式 `receive_timeout=None`，避免 aiohttp 默认 10 秒空闲断连。
- 配置迁移白名单纳入 `[server]`，否则该节会被静默丢弃。
