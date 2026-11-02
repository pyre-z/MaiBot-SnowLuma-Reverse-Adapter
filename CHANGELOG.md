# Changelog

本项目从 `MaiBot-SnowLuma-Adapter` 1.1.8 派生，上游历史见 `UPSTREAM-CHANGELOG.md`。

## 4.6.1

### 变更

- `slot_idle_timeout_sec` 默认值从 300 改为 **0（不回收）**：默认行为回到「连上就长期复用」，
  避免未被选中的 `Api` 槽位每 5 分钟被关一次、SnowLuma 再重连一次的日志噪音
  （`sticky` 下只有部分会话会落到某条槽位，闲置很常见）。需要限制长期空闲连接时显式设置秒数，
  事件槽位始终不受回收影响。
- 配置项 hint/描述同步为「默认 0」，中英日三语文案一起改。

## 4.6.0

### 新增

- **多连接分流（slot 连接池）**：反向 WS 路径支持 `/onebot/v11/ws/{slot}`，每条连接拥有独立的
  发送锁与 echo 等待表。大表情/大图片只阻塞自己那条链路，不再把「正在输入」和文字消息一起卡到
  30 秒超时。snow 侧用 `Role=Api` 的连接承载发送，`Universal`/`Event` 连接保持唯一事件通道。
- 新增配置 `[server].slot_idle_timeout_sec`（默认 300 秒，0 关闭）、`max_slots`（默认 8，0 不限）、
  `slot_routing`（`sticky` / `round_robin`）。
- `/healthz` 增加 `slot_count` 与 `slots` 明细（需带 token）。

### 修复

- 同一条连接上的大帧传输会占住发送锁，导致后续动作排队到 30 秒超时的连带故障。

## 4.5.2

### 修复

- **禁言状态写进插件源码目录**：`ban_state_store` 之前用 `Path(__file__).parents[2] / "data"` 定位文件，
  状态落在插件源码目录下，插件升级或重装会一并丢失，宿主运行时还会持续告警「旧式数据目录」。
  现在由 `ctx.paths.data_dir` 注入统一持久目录（`/data/plugins/<插件 ID>`），
  旧文件存在时首次加载自动迁移并立即落盘；旧版 SDK 不提供 `paths` 时仍回落到源码目录 `data/`。

## 4.5.1

### 修复

- **语音转文字全量失败（网关 `invalid wav file`）**：SnowLuma 画像下 silk 语音此前被转成 **MP3**，
  而 MaiBot 的语音识别工具把上传文件硬编码命名为 `audio.wav`，网关按 WAV 头计算时长，
  内容不是 WAV 时直接 500（`error getting audio duration: invalid wav file`），
  消息降级成 `[语音消息，转录失败]`。
  现在 `media/voice.py` 统一产出**合法 WAV**：silk 走 pysilk 解 PCM 后用 `wave` 套 RIFF 头
  （不依赖 ffmpeg）；其他非 WAV 编码走 ffmpeg 落临时文件再读回（管道输出无法回填 RIFF 长度字段）。
  `_build_record_segment` 的判定条件从「是 silk 才转」改为「不是 WAV 就转」，兜住服务端返回 mp3 的情况。

### 说明

- 配置结构版本不变，`config.toml` 无需迁移。

## 4.5.0

### 变更

- **结构调整，行为零变更**：`config/sections.py`（1056 行、7 个配置类）拆成 `config/sections/` 包
  （`plugin_options` / `server` / `notice` / `filters` / `debug` / `mute` 等按配置段分文件）；
  `apis/group.py`（930 行、52 个方法）拆成 `apis/group/` 包（`QQGroupBanMixin` / `QQGroupMemberMixin` /
  `QQGroupNoticeMixin` / `QQGroupInfoMixin` / `QQGroupManageMixin`），由 `QQGroupApiMixin` 组合导出，
  `from snowluma_reverse.apis import QQGroupApiMixin` 与旧路径仍是同一个对象。
- `pyproject.toml` 版本号从 `2.1.0` 修正为 `4.5.0`，与 `_manifest.json` 对齐（此前长期漂移）。

### 说明

- 配置结构版本不变，仍为 4.4.0；`config.toml` 无需迁移，字段名、顺序、`label` / `hint` / `i18n` 全部保持原样。
- 升级时需**删除**旧的 `snowluma_reverse/config/sections.py` 与 `snowluma_reverse/apis/group.py`，
  否则旧模块会与同名包并存。

## 4.4.0

### 新增

- **去掉结尾句号/冒号**（`[plugin].enable_trailing_punctuation_strip`，默认开启）：发送前删除正文末尾**单个**
  `。`、`：`（含半角 `:`），符合聊天口语。`好的。` → `好的`、`我总结一下：` → `我总结一下`。
  连续标点（`真的。。。`、`好吧。。`）视为刻意强调，原样保留；只处理整条消息最后一个文本段的结尾，
  句中标点、`？`、`！` 一律不动；删成空串时保留原文。
  主因是模型习惯把每条回复写成收尾完整的书面句，气泡末尾的句号和冒号很出戏。

### 说明

- 配置结构版本 4.3.0 → 4.4.0。

## 4.3.0

### 新增

- **盘古之白**（`[plugin].enable_pangu_spacing`，默认开启）：出站文本在中文与英文字母／数字之间补一个空格
  （`这是Flash吧` → `这是 Flash 吧`）。幂等，已带空格的不会再加；保护 `[小表情#ID]`、方括号短词
  （`[思考]`、`[图片]`）、URL、反引号内联代码与 `/表情名`。只动中英边界，不碰标点。
- `[plugin].enable_pangu_spacing_digits`（默认开启）：数字是否参与（`说了5个人` → `说了 5 个人`）；关闭后只处理字母。
- `[plugin].enable_private_at_strip`（默认开启）：私聊剥离 `at` 段改为可控开关，关闭后保持 4.2.1 之前的行为
  （at 原样下发，QQ 会整条拒收）。

### 说明

- 配置结构版本 4.2.0 → 4.3.0。

## 4.2.1

### 修复

- 私聊出站丢弃 `at` 段：QQ 对私聊消息里的 `at` 元素直接整条拒收
  （`message element "at" cannot be sent in a private chat`），模型给 `reply` 带 `attach_at` 时
  正文会一起丢掉。现在私聊场景剥离 `at`、正文照常发送；群聊行为不变；剥完为空时退回空文本段。

### 说明

- 配置结构版本不变（仍 4.2.0），无需改 `config.toml`。

## 4.2.0

### 新增

- 出站表情名兜底：文本里的 `[汗]`、`[吃瓜]` 这类中文表情名转换为 QQ 原生小表情，开关
  `[plugin].enable_text_face_name_token`（默认开启）。只匹配表情表里真实存在的名字（最长优先），
  `[图片]`、`[注]`、`[表情包]` 等普通方括号文本保持原文。
- 起因：模型常把 QQ 表情写成旧式 `[汗]` 而不是 `[小表情#ID]`，此前这类内容会原样发成字面文本。

### 说明

- 配置结构版本 4.1.0 → 4.2.0；该开关与 `enable_text_face_token` 独立，可按需关闭。
- 入站锚点 `[小表情·幽灵#187]` 与 `[小表情#ID]` 的解析行为不变。

## 4.1.0

### 新增

- 出站小表情 token：文本里的 `[小表情#187]` 转换为 QQ 原生小表情，开关
  `[plugin].enable_text_face_token`（默认开启）。混排、多个 token、群聊/私聊/合并转发均生效。
- 只有数字且已收录的 ID 会转换；未收录 ID、非数字 ID、空 ID 保留原文。
- 与入站锚点 `[小表情·幽灵#187]` 严格区分：模型引用消息原文不会被误转成真表情。

### 说明

- `enable_text_face_conversion`（`/表情名` 写法）默认关闭，与 token 开关独立；
  QQ 表情名存在重名（`发呆` → 3 / 453），精确指定请用 ID 写法。
- 配置结构版本 4.0.0 → 4.1.0。

## 4.0.0

### 破坏性变更

- **QQ 表情视觉描述整体移出**：删除 `media/face_vision_{assets,worker,store}.py`、`data/face_vision.py`、
  `data/face_vision.json`（537 条）、`scripts/build_face_vision.py` 与 `[face_vision]` 配置段；
  VLM 调用、素材下载、运行时补算改由独立插件 `pyre-z.emoticon-vision` 负责。
- `qq_face_parse_mode` 只剩 `description` / `emoji` 两个取值；旧配置里的 `vision` 自动回落到 `description`。
- `description` 模式的输出从 `[幽灵]` 改为锚点 `[小表情·幽灵#187]`（未收录为 `[小表情·未知表情#ID]`），
  由 `emoticon-vision` 插件在 `chat.receive.after_process` 里替换成
  `[小表情·幽灵：外观描述|发呆|无语]`。
- 配置结构版本 3.0.0 → 4.0.0。

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
