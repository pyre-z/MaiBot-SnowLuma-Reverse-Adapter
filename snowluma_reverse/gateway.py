"""SnowLuma 消息网关组件。"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional

from maibot_sdk import MessageGateway

from .constants import SNOWLUMA_GATEWAY_NAME


class QQMessageGatewayMixin:
    @MessageGateway(
        name=SNOWLUMA_GATEWAY_NAME,
        route_type="duplex",
        platform="qq",
        protocol="snowluma",
        description="SnowLuma / NapCat 正向 WebSocket 双工消息网关",
    )
    async def handle_snowluma_gateway(
        self,
        message: Dict[str, Any],
        route: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """处理 Host 出站消息并按画像发送到对端客户端。

        Args:
            message: Host 侧标准 ``MessageDict``。
            route: Platform IO 生成的路由信息。
            metadata: Platform IO 附带的投递元数据。
            **kwargs: 预留扩展参数。

        Returns:
            Dict[str, Any]: 标准化后的发送结果。
        """
        del metadata
        del kwargs

        runtime_bundle = self._require_runtime_bundle()
        debug_logger = self._debug_logger
        internal_message_id = str(message.get("message_id") or "").strip()

        try:
            actions = await runtime_bundle.outbound_codec.prepare_outbound_actions(message, route or {})
        except Exception as exc:
            return {"success": False, "error": str(exc)}

        responses: List[Mapping[str, Any]] = []
        for action_name, params in actions:
            if debug_logger is not None:
                debug_logger.log_raw_outbound(internal_message_id, action_name, params)
            try:
                response = await runtime_bundle.action_service.call_action(action_name, params)
            except Exception as exc:
                return {"success": False, "error": str(exc), "metadata": {"action": action_name}}
            if not self._is_action_response_ok(response):
                return {
                    "success": False,
                    "error": str(response.get("wording") or response.get("message") or "send failed"),
                    "metadata": {"action": action_name, "retcode": response.get("retcode")},
                }
            responses.append(response)

        external_message_id = ""
        for response in responses:
            response_data = response.get("data", {})
            if isinstance(response_data, Mapping):
                external_message_id = str(response_data.get("message_id") or "")
                if external_message_id:
                    break

        adapter_callbacks = []
        if internal_message_id and external_message_id and internal_message_id != external_message_id:
            adapter_callbacks.append(
                {
                    "name": "message_id_echo",
                    "payload": {
                        "content": {
                            "type": "echo",
                            "echo": internal_message_id,
                            "actual_id": external_message_id,
                        }
                    },
                }
            )

        return {
            "success": True,
            "external_message_id": external_message_id or None,
            "metadata": {
                "action": actions[0][0] if len(actions) == 1 else "multiple",
                "actions": [action_name for action_name, _ in actions],
                "adapter_callbacks": adapter_callbacks,
            },
        }

