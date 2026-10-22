# 代码质量审计报告（第 6 轮）

审计范围：`snowluma_reverse/`（重点 transport / runtime / services）、`plugin.py`、配置模型、测试与文档。
基线：59 passed → 本轮新增 5 个关键路径测试，当前 64 passed。

## P0（0 条）

未发现会导致数据丢失、消息错乱、安全漏洞、进程崩溃或静默失效的缺陷。

反向链路的关键既有保护均已在测试中确认有效：
- 恒时 token 比较（`hmac.compare_digest`，`snowluma_reverse/transport/auth.py:35`）；
- 同账号重连替换旧连接、不同 `X-Self-ID` 并发拒绝（1008）；
- 断连 / 连接替换时 `_fail_pending_actions()` 使挂起动作以 `RuntimeError("连接已中断")` 结束（`snowluma_reverse/transport/reverse_server.py:350`，本轮补测试）；
- 连接替换后旧 `payload_queue` / worker 被 `task.cancel()` 清理，新连接重建队列（`reverse_server.py:303-306, 343-345`）；
- bootstrap 失败不会永久卡死：`_bootstrap_and_mark_ready()` 在 `finally` 中置位就绪事件（`reverse_server.py:359-364`），事件按正常路径暴露真实错误，下一次连接会重新触发 `on_connection_opened` 并重新 bootstrap（本轮补测试验证恢复路径）；
- 心跳 ping、`recv` 超时与慢对端：读循环只在 TEXT 帧上做 JSON 解析，异常帧/超长消息由 aiohttp 限制（`max_message_size`），JSON 失败仅 warning 后跳过，不会拖垮读循环；
- 非法 CIDR 被静默跳过但不会导致启动失败或误放行（本轮补测试验证）。

## P1（2 条，均已修）

### P1-1 pytest-cov 缺失导致覆盖率无法度量
- 位置：`pyproject.toml`（dev extras）
- 现象：`uv run pytest --cov=...` 报 `unrecognized arguments`，无法按任务要求输出覆盖率。
- 证据：修复前命令输出 `ERROR: usage: pytest ... unrecognized arguments: --cov=snowluma_reverse`。
- 修复：dev extras 增加 `pytest-cov>=5`，`uv sync --extra dev` 后覆盖率命令可用。
- 测试：不适用（工具链变更）。

### P1-2 ruff 规则过窄，暴露 13 处真实问题
- 位置：`pyproject.toml`（ruff select）；`snowluma_reverse/config/base.py:143-145`、`snowluma_reverse/config/__init__.py`、`snowluma_reverse/config/sections.py`、`snowluma_reverse/protocol/inbound/envelope.py` 等 10+ 文件
- 现象：仅启用 `E9/F63/F7/F82` 时，重复导入 `SUPPORTED_CONFIG_VERSION`（F811 + E402）、10 处未使用导入、1 处未使用循环变量均未被发现。
- 证据：放宽为 `["E4", "E7", "E9", "F", "B"]` 后 `uv run ruff check .` 输出 13 errors，其中 `snowluma_reverse/config/base.py:146` 存在同常量的重复导入。
- 修复：`ruff --fix` 清理未使用导入；`base.py` 保留公共版本标记导出并加 `# noqa: E402, F401`（语义未变）；`config/__init__.py` 用 `__all__` 声明 `SUPPORTED_CONFIG_VERSION` 仍然可从 `snowluma_reverse.config` 导入；`tests/test_business_apis.py` 循环变量改名 `_name`。
- 测试：全部既有测试通过（64 passed），导入路径行为由 `tests/test_config.py`、`tests/test_transport_auth.py` 覆盖。

## P2（3 条，文档类已修，2 条为加固性说明不修）

### P2-1 README「已验证行为」与测试数量/覆盖项不一致（已修）
- 位置：`README.md` §7
- 现象：只描述早期传输测试，未反映本轮新增的连接替换、bootstrap 恢复、非法 CIDR、空/异常载荷等覆盖项。
- 修复：补充当前测试覆盖清单，并注明统计数字以 `uv run pytest -q` 实时输出为准（当前 64 passed）。

### P2-2 `on_config_update` 非法配置异常路径（不修，理由如下）
- 位置：`snowluma_reverse/plugin.py:87-100`
- 现象：`set_plugin_config(config_data)` 内部走 `QQPluginSettings.model_validate`，非法配置会抛 `ValueError`。Host 侧 `on_config_update` 若不捕获，会把异常上抛；但该路径同时是“拒绝非法配置”的正确信号，吞掉反而可能让非法配置静默生效为默认值。
- 不修理由：抛错是守卫行为而非缺陷；改为吞异常会破坏“非法配置必须显式失败”的约定。已补测试确认非法配置会以 `ValueError` 显式失败且合法配置仍可用（`tests/test_config.py::test_hot_update_invalid_config_does_not_crash`）。若 Host 要求插件自身兜底，应在上层适配，而不是在插件内吞。

### P2-3 空 `segments` / `group_id=0` / 空 `message` 处理（不修，理由如下）
- 位置：`snowluma_reverse/protocol/inbound/envelope.py`、`snowluma_reverse/runtime/router.py`
- 现象：空载荷不会被丢弃，`group_id=0` 会按原值透传给编解码层，由既有字段校验/过滤链处理。强行“拒收”会改变上游 OneBot 语义（某些事件确实可能带 0 值字段）。
- 不修理由：属于协议兼容行为，贸然收紧会破坏上游事件流。已补测试锁定当前行为：非法 JSON / 非字典 / 空段 / `group_id=0` 不崩溃、不挂起队列（`tests/test_transport_reverse.py::test_empty_and_malformed_payloads_are_ignored`）。

## 不修项汇总

| 条目 | 理由 |
| --- | --- |
| P2-2 热更新异常吞与不吞 | 吞异常会让非法配置静默生效，显式抛错是守卫行为 |
| P2-3 空 segment / 0 值 ID 收紧校验 | 会改变上游 OneBot 兼容语义，风险大于收益 |
