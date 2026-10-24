# 架构说明

## 模块职责

| 模块 | 职责 |
| --- | --- |
| `plugin.py` / `snowluma_reverse/plugin.py` | 插件加载入口、生命周期、工具与命令注册、网关衔接 |
| `config/` | 配置 section、迁移、校验与当前传输配置选择 |
| `transport/` | 反向服务端与握手鉴权 |
| `protocol/` | OneBot 入站消息、出站消息和通知编解码 |
| `runtime/` | 运行时依赖构建、事件路由、连接状态与心跳 |
| `services/` / `apis/` | 动作查询、管理服务与公开 QQ API |
| `media/` / `data/` | Silk 语音处理与 QQ 静态表情数据 |

## 连接生命周期

1. 反向模式收到合法 WebSocket 握手后，校验来源 IP、令牌和 `X-Self-ID`。
2. 连接回调并发探测 `get_version_info` 等画像信息；读循环同时接收动作 echo。
3. 画像探测完成后激活消息网关并上报账号状态。
4. 建立期间到达的事件暂存队列；网关就绪后 worker 依序解码、过滤并注入 Host。

```text
SnowLuma → 握手鉴权 → 画像探测 → 网关激活 → 事件队列 → 解码/过滤 → MaiBot
                             ↕ action / echo ↕
```

## 传输方向

只保留反向 WebSocket 服务端：适配器监听端口，SnowLuma 主动连入，配置来自 `[server]`。
上游的正向客户端（适配器拨号）已移除，`[client]` 段不再存在，`client_type` 迁到 `[plugin]`
用于声明对端实现（auto / napcat / snowluma）。action、编解码与网关运行时全部复用同一套实现。

## 拉取向导

1. 在 `[plugin]` 启用插件，按需固定 `client_type`（默认 auto）。
2. 配置 `[server]` 监听地址、端口、令牌或 IP 白名单。
3. SnowLuma 反向连接配置对应 URL 与相同令牌，并提供 `X-Self-ID`。
4. 用 `/healthz` 检查监听状态；携带令牌时可查看已连接账号。
5. 按 README 中的部署示例配置宿主端口映射和反向代理。
