from __future__ import annotations

import pytest

from src import Cmd
from src.test_flow import ContactTestFlow


pytestmark = [pytest.mark.client, pytest.mark.contact, pytest.mark.sdk_5_0, pytest.mark.second_channel]


def test_contact_5_0_sync_then_read_contacts_from_local_db(device_a, device_b, assert_api, user_a, user_b):
    """
    SDK 5.0: 联系人列表迁移为登录后数据同步，再读取本地 DB。
    本 case 不调用旧“删除 API”做编译验证，只验证推荐路径 getAllContactsFromDB。
    """
    flow = ContactTestFlow(assert_api)
    flow.establish_friends(device_a, device_b, user_a, user_b, reason="sdk5_local_contact")
    try:
        resp = device_a.call("ContactManager", Cmd.getAllContactsFromDB.value, info={})
        assert_api.assert_response_matches(
            resp,
            expected={
                "manager": "ContactManager",
                "cmd": Cmd.getAllContactsFromDB.value,
                "device": "deviceA",
            },
            ignore_keys={"sequence", "result"},
        )
        result = resp.get("result")
        assert isinstance(result, list), f"getAllContactsFromDB result 不是 list: {resp}"

        resp_server = device_a.call("ContactManager", Cmd.getAllContactsFromServer.value, info={})
        assert_api.assert_response_matches(
            resp_server,
            expected={
                "manager": "ContactManager",
                "cmd": Cmd.getAllContactsFromServer.value,
                "device": "deviceA",
                "result": [user_b],
            },
            ignore_keys={"sequence"},
        )
    finally:
        flow.delete_friend(device_a, user_b, keep_conversation=True)
