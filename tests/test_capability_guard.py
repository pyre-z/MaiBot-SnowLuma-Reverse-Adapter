from snowluma_reverse.profile import NAPCAT_PROFILE, ProfileState, SNOWLUMA_PROFILE
from snowluma_reverse.protocol.actions import SNOWLUMA_UNSUPPORTED
from snowluma_reverse.services.action_service import QQActionService


class Transport:
    def __init__(self):
        self.calls = 0

    async def call_action(self, action, params):
        self.calls += 1
        return {"status": "ok", "retcode": 0, "data": {}}


async def test_unsupported_actions_are_locally_blocked_only_for_snowluma(logger):
    assert len(SNOWLUMA_UNSUPPORTED) == 9
    for action in SNOWLUMA_UNSUPPORTED:
        transport = Transport()
        service = QQActionService(logger, transport, ProfileState(SNOWLUMA_PROFILE))
        response = await service.call_action(action, {})
        assert response["retcode"] == 1404
        assert action in response["message"]
        assert transport.calls == 0

        napcat_transport = Transport()
        napcat_service = QQActionService(logger, napcat_transport, ProfileState(NAPCAT_PROFILE))
        await napcat_service.call_action(action, {})
        assert napcat_transport.calls == 1
