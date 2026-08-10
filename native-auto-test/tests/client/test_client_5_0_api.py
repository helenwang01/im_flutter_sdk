from __future__ import annotations

import pytest

from src import Cmd
from src.rest_api.token_api import fetch_login_token


pytestmark = [pytest.mark.client, pytest.mark.sdk_5_0, pytest.mark.second_channel]


def test_client_is_database_opened_after_session_login(device_a, assert_api):
    """
    SDK 5.0: 登录后数据库打开状态对外可查。
    对齐第二通道用例中“登录后可读取本地 DB”的消费侧前置。
    """
    resp = device_a.call("Client", Cmd.isDatabaseOpened.value, info={})
    assert_api.assert_success(resp)
    assert resp.get("manager") == "Client", resp
    assert resp.get("cmd") == Cmd.isDatabaseOpened.value, resp
    assert resp.get("device") == "deviceA", resp
    assert isinstance(resp.get("result"), bool), resp


def test_client_5_0_data_sync_and_database_callbacks_shape(device_a, user_a):
    """
    SDK 5.0: 数据同步和数据库打开回调通过 EventBridge 透传。
    回调是否出现取决于端侧 dataSyncTypes 与数据库状态；出现时字段结构必须稳定。
    """
    expected_event_types = {
        Cmd.onDataSyncStart.value,
        Cmd.onDataSyncFinish.value,
        Cmd.onDatabaseOpened.value,
    }
    events = []
    deadline_count = 6

    for _ in range(deadline_count):
        evt = device_a.receive_message(timeout=2.0)
        if evt is None:
            continue
        if evt.get("eventType") in expected_event_types:
            events.append(evt)

    for evt in events:
        event_type = evt.get("eventType")
        data = evt.get("data") or {}
        if event_type == Cmd.onDataSyncStart.value:
            assert isinstance(data.get("type"), int), evt
        elif event_type == Cmd.onDataSyncFinish.value:
            assert isinstance(data.get("type"), int), evt
            assert isinstance(data.get("errorCode"), int), evt
        elif event_type == Cmd.onDatabaseOpened.value:
            assert data.get("userId") in ("", user_a), evt


def test_client_5_0_kick_device_token_mode_reaches_sdk(device_a, assert_api, user_b):
    """SDK 5.0: kickDevice 兼容 token 鉴权入参；非法 resource 应由 SDK/服务端返回业务错误。"""
    token = fetch_login_token(user_b)
    resp = device_a.call(
        "Client",
        Cmd.kickDevice.value,
        info={
            "userId": user_b,
            "password": token,
            "resource": f"missing-resource-{user_b}",
            "isPwd": False,
        },
    )
    assert_api.assert_error(resp)
    err = assert_api.get_error(resp)
    assert "MissingPluginException" not in err.get("description", ""), resp
    assert "not supported" not in err.get("description", ""), resp


def test_client_5_0_kick_all_devices_token_mode_rejects_invalid_token(device_a, assert_api, user_b):
    """SDK 5.0: kickAllDevices 走 token 版本 API，非法 token 返回鉴权错误且不踢当前测试设备。"""
    resp = device_a.call(
        "Client",
        Cmd.kickAllDevices.value,
        info={
            "userId": user_b,
            "password": f"invalid-token-{user_b}",
            "isPwd": False,
        },
    )
    assert_api.assert_error(resp)
    err = assert_api.get_error(resp)
    assert "MissingPluginException" not in err.get("description", ""), resp
    assert "not supported" not in err.get("description", ""), resp
