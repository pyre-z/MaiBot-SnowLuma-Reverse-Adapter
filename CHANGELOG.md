# Changelog

本项目从 `MaiBot-SnowLuma-Adapter` 1.1.8 派生，上游历史见 `UPSTREAM-CHANGELOG.md`。

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
