from __future__ import annotations

import uuid

import pytest

from src import Cmd
from tests.chat._utils import build_text
from tests.group.group_helpers import create_group, destroy_group, new_group_name


pytestmark = [pytest.mark.client, pytest.mark.chat, pytest.mark.sdk_5_0]


def test_chat_5_0_group_conversation_name_avatar_exposed(device_a, assert_api, user_a):
    """SDK 5.0: EMConversation.conversationName/conversationAvatar 通过 Flutter 会话模型透出。"""
    group_id = ""
    group_name = new_group_name("sdk5_conv_name_avatar")
    avatar_url = f"https://example.com/native-auto-test/{uuid.uuid4().hex}.png"
    try:
        group_id, _ = create_group(
            device_a,
            assert_api,
            owner=user_a,
            group_name=group_name,
            invite_members=[],
        )
        resp_avatar = device_a.call(
            "GroupManager",
            Cmd.updateGroupAvatar.value,
            info={"groupId": group_id, "avatarUrl": avatar_url},
        )
        assert_api.assert_success(resp_avatar)

        msg = build_text(user_a, group_id, f"sdk5-conv-name-avatar-{uuid.uuid4().hex[:6]}", chat_type=1)
        resp_send = device_a.call("ChatManager", Cmd.sendMessage.value, info=msg)
        assert_api.assert_success(resp_send)
        evt_success = device_a.receive_message(match_event_type=Cmd.onMessageSuccess.value, timeout=20.0)
        assert evt_success is not None, resp_send

        resp_conv = device_a.call(
            "ChatManager",
            Cmd.getConversation.value,
            info={"convId": group_id, "type": 1, "createIfNeed": True},
        )
        assert_api.assert_success(resp_conv)
        conv = resp_conv.get("result") or {}
        assert conv.get("convId") == group_id, resp_conv
        assert "conversationName" in conv, resp_conv
        assert "conversationAvatar" in conv, resp_conv
        assert conv.get("conversationName") == group_name, resp_conv
        assert conv.get("conversationAvatar") == avatar_url, resp_conv
    finally:
        if group_id:
            destroy_group(device_a, assert_api, group_id)
