# MaiBot SnowLuma Reverse Adapter

让 **SnowLuma 主动连入 MaiBot** 的 QQ 适配器插件。

上游 `MaiBot-SnowLuma-Adapter` 只能以 OneBot v11 **正向 WebSocket 客户端**身份连接对端
（适配器拨号 → SnowLuma 监听）。本项目把方向反过来：**适配器监听端口，SnowLuma 以
OneBot v11 反向 WebSocket 客户端身份连入**，适合 MaiBot 在容器/内网、SnowLuma 在另一台
机器且需要主动出站连通的部署。

## 1. 与上游的差异

| 维度 | 上游 | 本项目 |
| --- | --- | --- |
| 传输方向 | 仅正向 WS 客户端 | 仅反向 WS 服务端 |
| 连接发起方 | 适配器 | SnowLuma |
| TLS | 不支持（URL 硬编码 `ws://`） | 由反向代理终止，容器内保持明文 |
| 鉴权 | 出站携带 token | 入站校验 token + 来源 IP 白名单 |
| 健康检查 | 无 | `GET /healthz` 返回监听与连接状态 |

消息编解码、事件通知、LLM 工具（主动私聊、撤回、禁言、表情表态、合并转发）、QZone 等
业务能力全部沿用上游实现，未改动。

## 2. 拓扑

```
QQ 客户端
   │
   ▼
SnowLuma（WS 客户端，role=Universal）
   │  wss://bot.example.com/onebot/v11/ws   ← 出站连接，可穿越 NAT
   ▼
OpenResty / Caddy（终止 TLS，Upgrade 反代）
   │  ws://127.0.0.1:18002/onebot/v11/ws
   ▼
MaiBot 容器内的本插件（WS 服务端，监听 0.0.0.0:6727）
   │
   ▼
MaiBot Core
```

## 3. 部署

### 3.1 放置插件

把本仓库目录放到 MaiBot 的插件目录（Docker 部署通常挂载到 `/MaiMBot/plugins`）：

```bash
cp -r MaiBot-SnowLuma-Reverse-Adapter /path/to/MaiBot/data/MaiMBot/plugins/
```

### 3.2 暴露端口

在 MaiBot 的 `docker-compose.yml` 的 core 服务里加一条映射（只绑回环，对外走反代）：

```yaml
    ports:
      - "127.0.0.1:18001:8001"     # WebUI
      - "127.0.0.1:18002:6727"     # 本插件的反向 WS 监听
```

### 3.3 反向代理（OpenResty）

```nginx
location /onebot/v11/ws {
    proxy_pass http://127.0.0.1:18002;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_read_timeout 3600s;
    proxy_send_timeout 3600s;
}
```

`proxy_read_timeout` 必须放大：WebSocket 空闲超过默认 60 秒会被反代断开。

> 若反代与容器不在同一网络，`127.0.0.1` 需换成宿主机地址或容器名；此时
> `[server].allowed_ips` 看到的是反代地址而不是 SnowLuma 的真实 IP，建议改用 token 鉴权。

### 3.4 插件配置

WebUI → 插件 → 本适配器：

```toml
[plugin]
enabled = true
client_type = "auto"        # 对端实现：auto 自动探测，也可固定 napcat / snowluma

[server]
listen_host = "0.0.0.0"
listen_port = 6727
listen_path = "/onebot/v11/ws"
token = "换成足够长的随机串"        # 与 SnowLuma 侧一致
allowed_ips = []                    # 可选：填 SnowLuma 出口 IP 或 CIDR
expect_self_id = ""                 # 可选：限定机器人 QQ 号
heartbeat_interval = 30
action_timeout_sec = 30
max_message_size = 16777216
```

`token` 与 `allowed_ips` **至少配置一项**，两者都为空时插件拒绝启动监听。

> 从 2.x 升级：配置结构升到 `3.0.0`，`[plugin].transport_mode` 与 `[client]` 段已移除。
> 插件自动迁移（`client_type` 搬到 `[plugin]`，其余连接参数丢弃），无需手工改文件。

#### QQ 表情解析（`qq_face_parse_mode`）

| 取值 | 输出形态 | 说明 |
| --- | --- | --- |
| `description`（默认） | `[小表情·幽灵#187]` | 带中文名与表情 ID 的锚点，交给 `emoticon-vision` 插件替换成视觉描述 |
| `emoji` | `👻` / `[小表情·幽灵#187]` | 能对上 Unicode 的用真 emoji，否则回退同样的锚点 |

锚点格式是 `[小表情·<中文名>#<表情 ID>]`，未收录的表情渲染为 `[小表情·未知表情#<ID>]`。
配套插件 `pyre-z.emoticon-vision` 会把它替换成
`[小表情·幽灵：一只白色小幽灵上下漂浮、双眼发直|发呆|无语]`（全角冒号分段、半角竖线分情绪标签）。
**没装那个插件也不会坏**：模型看到的就是带名字和 ID 的锚点。

视觉描述的索引、素材抓取与 VLM 生成都在 `emoticon-vision` 插件里（含离线全量构建与运行时补算），
本适配器不再持有任何 VLM 配置或描述表。

### 3.5 SnowLuma 侧

在 SnowLuma WebUI 的 OneBot 连接里新建 **WebSocket 客户端（反向 WS）**：

- URL：`wss://bot.example.com/onebot/v11/ws`
- Access Token：与 `[server].token` 一致
- Role：`Universal`（收发都要；选 `Event` 只收不发）
- 重连间隔：默认 5 秒即可

SnowLuma 握手时携带 `X-Self-ID`（机器人 QQ 号）与 `Authorization`，插件据此识别账号。

## 4. 工作方式

1. SnowLuma 连入，握手通过后插件触发一次连接建立回调（画像探测、运行时状态初始化）。
2. QQ 消息到达 SnowLuma → 通过这条连接推送事件 → 插件转成 MaiBot 消息。
3. MaiBot 要发消息 → 插件在**同一条连接**上发送 `{"action": …, "params": …, "echo": …}`
   → SnowLuma 回带同名 `echo` 的响应。

同账号重连会替换旧连接（旧连接收到 1001）；不同 `X-Self-ID` 的并发连接会被拒绝（1008）。
本适配器沿用上游的单账号模型，一个插件实例只服务一个 QQ 号。

## 5. 安全

- 宿主侧端口映射只绑回环地址，容器内监听 `0.0.0.0` 由容器网络隔离；公网入口交给反代；
- token 用 `hmac.compare_digest` 比较，避免时序侧信道；
- `allowed_ips` 支持单 IP 与 CIDR；
- 未配置任何鉴权手段时拒绝启动，不会静默裸奔。

## 6. 开发与测试

项目使用 uv 管理依赖，开发环境与测试命令：

```bash
uv sync --extra dev
uv run pytest -q
uv run ruff check .
```

实现位于根目录 flat 包 `snowluma_reverse/`，根目录 `plugin.py` 保持 MaiBot 插件包加载入口。
更详细的模块职责和连接流程见 [docs/architecture.md](docs/architecture.md)。

## 7. 已验证行为

`uv run pytest -q` 使用 aiohttp 模拟反向客户端，并覆盖：

- 错误 token → 401；
- 事件上行到达 `on_payload`；
- `call_action` 下行并在同连接收到 echo 响应；
- 空闲 12 秒（超过 aiohttp 默认 10 秒回读超时）连接仍存活；
- 不同 `X-Self-ID` 并发 → 1008 拒绝；
- 同账号重连替换旧连接；
- 断线后 `call_action` 抛 `RuntimeError`；
- 同账号被新连接替换后，旧连接上挂起的 `call_action` 以 `RuntimeError("连接已中断")` 结束；
- bootstrap 回调抛错（如 `get_version_info` 失败）时事件按正常路径暴露错误，下一次连接可重新 bootstrap；
- 非法 CIDR 不导致启动失败，且不会误放行；
- 空消息、空段数组、`group_id=0`、非法 JSON 与非字典载荷不会使队列或读循环崩溃。

还覆盖双通道 token、IP/CIDR 白名单、`expect_self_id` 和 `/healthz` 信息保护，以及配置迁移。
测试数量以 `uv run pytest -q` 实时输出为准（当前为 68 passed）。

真实宿主端到端（MaiBot v1.3.14 / SDK 2.16 / aiohttp 3.14）：模拟客户端连入容器内监听，
依次触发 `get_version_info` → `get_login_info` → `get_group_info`，随后推送的群消息在
`mai_messages` 中落库（`platform=qq`），证明「SnowLuma → 适配器 → MaiBot」整条链路可用。

## 8. 已知限制

- 仅支持 WebSocket，不支持 OneBot HTTP 上报；
- 单账号；多 QQ 号需要多个 MaiBot 实例或后续做连接隔离；
- TLS 需由反向代理终止，插件自身不监听 `wss://`；
- 只提供反向 WS 服务端：上游的正向 WS 客户端已移除，旧 `[client]` 配置段不再生效
  （升级时仅迁移其中的 `client_type`，其余连接参数丢弃）。

## 8. 上游业务能力（沿用）

### 群消息发送确认

连接 SnowLuma 时，群消息及合并转发在动作返回后还会查询对应消息，只有消息 ID、目标群和
正数群消息序号均匹配，才向 MaiBot 报告发送成功。本地合成记录（序号为 0）、仅受理的异步
动作或查询失败会报告失败；“投递未确认”表示尚无真实群消息回执，适配器不会自动重发。

### 小表情 token（推荐）

`[plugin].enable_text_face_token = true`（默认开启）。发送文本里的 `[小表情#187]` 会转换为
QQ 原生小表情，混排、多个 token、群聊/私聊/合并转发都生效；token 由 `emoticon-vision`
插件的 `pick_qq_face` 工具产出，模型原样写进回复即可。

只有**数字且已收录**的 ID 会被转换：`[小表情#99999]`（未收录）、`[小表情#☀]`（非数字）、
`[小表情#]`（空 ID）一律保留原文。入站锚点 `[小表情·幽灵#187]` 带名字，**不会**被这条规则
误转，因此模型引用消息原文时安全。

### 文本转 QQ 表情（`/表情名`）

`[plugin].enable_text_face_conversion = true`（默认关闭，与上面的 token 独立）。
发送时 `/捂脸 /捂脸 /捂脸` 或 `/捂脸/捂脸` 会转换为对应 QQ 原生表情；名称必须完整匹配，
`/捂脸不存在` 不会被部分转换。⚠️ QQ 的表情名存在重名（如 `发呆` 同时对应 3 和 453），
名字写法只能命中其中一个，需要精确指定时用 `[小表情#453]`。

### 文本转 @

「插件设置」开启「启用文本转@」（默认关闭），对应 `[plugin].enable_text_at_conversion = true`。
群聊发送文本中的 `@QQ号`、`@群名片`、`@昵称` 必须完整、唯一匹配当前群成员才转换为实际 @；
未知名称、重名、邮箱及查询失败时保持原样，不自动转换 @全体成员。

### 其他插件调用 API

通过 SDK 的 `ctx.api.call` 调用，两种前缀均使用 `version="1"`：

```python
member = await self.ctx.api.call(
    "adapter.snowluma.group.get_group_member_info",
    version="1",
    group_id=123456,
    user_id=654321,
)
# 将 adapter.snowluma. 替换为 adapter.napcat.，调用行为完全相同。

data = await self.ctx.api.call(
    "adapter.snowluma.action.call_data",
    version="1",
    action_name="get_group_info",
    params={"group_id": 123456},
)
```

### 能力差异参考

| 维度 | napcat 画像 | snowluma 画像 |
| --- | --- | --- |
| 发送动作 | `send_group_msg` / `send_private_msg` | 通用 `send_msg` + `message_type` |
| 出站文件 | 内联 `file` 段 | 拆独立 `upload_group_file` / `upload_private_file` |
| 合并转发参数键 | `message` | `messages` |
| 语音 `get_record` 格式 | `wav` | `mp3`（silk 自动转码兜底） |
| QZone API | 不支持（显式报错） | 支持 |

## 9. 来源与许可

本项目是 [`Mai-with-u/MaiBot-SnowLuma-Adapter`](https://github.com/Mai-with-u/MaiBot-SnowLuma-Adapter)
的衍生作品：业务层代码来自上游，传输层与配置为新增实现。遵循上游 **GPL-3.0-or-later**，
上游版权归 MaiBot Team 所有。
