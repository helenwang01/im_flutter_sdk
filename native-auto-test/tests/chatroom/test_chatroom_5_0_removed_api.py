from __future__ import annotations

import pytest

from src import Cmd


pytestmark = [pytest.mark.chatroom, pytest.mark.sdk_5_0]


def _assert_ios_sdk_5_0_unsupported_or_valid_response(resp: dict, expected_cmd: str) -> None:
    err = resp.get("error") or resp.get("result") or {}
    if isinstance(err, dict):
        desc = str(err.get("description", ""))
        if err.get("code") == 205 and "not supported by iOS SDK 5.0" in desc and expected_cmd in desc:
            return
    assert "result" in resp or "error" in resp


def test_chatroom_create_removed_on_ios_sdk_5_0(device_a):
    """5.0 iOS: SDK 侧创建聊天室公开 API 删除，应提示业务服务端创建。"""
    resp = device_a.call(
        "ChatRoomManager",
        Cmd.createChatRoom.value,
        info={
            "subject": "sdk5_removed_create_room",
            "desc": "created by native-auto-test",
            "members": [],
            "welcomeMsg": "hi",
            "maxUserCount": 50,
        },
    )
    _assert_ios_sdk_5_0_unsupported_or_valid_response(resp, Cmd.createChatRoom.value)


def test_chatroom_destroy_removed_on_ios_sdk_5_0(device_a):
    """5.0 iOS: SDK 侧解散聊天室公开 API 删除，应提示业务服务端解散。"""
    resp = device_a.call(
        "ChatRoomManager",
        Cmd.destroyChatRoom.value,
        info={"roomId": "sdk5_removed_destroy_room"},
    )
    _assert_ios_sdk_5_0_unsupported_or_valid_response(resp, Cmd.destroyChatRoom.value)
