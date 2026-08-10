from __future__ import annotations

import time
import uuid

import pytest

from src import Cmd
from src.rest_api.conversation_api import get_user_channel_unread_count
from tests.chat._utils import build_text
from tests.group.group_helpers import create_group, destroy_group, new_group_name
from tests.conftest import login_with_token


pytestmark = [pytest.mark.client, pytest.mark.chat, pytest.mark.sdk_5_0]


def _send_text_and_wait_success(
    device_a,
    device_b,
    assert_api,
    user_a: str,
    user_b: str,
    content: str,
    *,
    need_read_receipt: bool = False,
) -> dict:
    msg = build_text(user_a, user_b, content)
    msg["needGroupAck"] = need_read_receipt
    device_a.drain_events()
    device_b.drain_events()

    resp = device_a.call("ChatManager", Cmd.sendMessage.value, info=msg)
    assert_api.assert_success(resp)

    evt = device_a.receive_message(match_event_type=Cmd.onMessageSuccess.value, timeout=20.0)
    assert evt is not None, f"missing onMessageSuccess for content={content!r}"
    sent_msg = (evt.get("data") or {}).get("msg") or {}
    assert isinstance(sent_msg.get("msgId"), str) and sent_msg.get("msgId"), evt
    return sent_msg


def _conversation_info(conv_id: str) -> dict:
    return {"convId": conv_id, "type": 0, "createIfNeed": True}


def _wait_received_message(device, content: str, *, timeout: float = 20.0) -> dict:
    deadline = time.time() + timeout
    while time.time() < deadline:
        evt = device.receive_message(match_event_type=Cmd.onMessagesReceived.value, timeout=2.0)
        if not evt:
            continue
        for msg in ((evt.get("data") or {}).get("messages") or []):
            body = msg.get("body") or {}
            if isinstance(body, dict) and body.get("content") == content:
                return msg
    raise AssertionError(f"未收到目标消息: content={content!r}")


def _find_receipt(receipts: list[dict], msg_id: str) -> dict | None:
    for receipt in receipts:
        if receipt.get("msgId") == msg_id:
            return receipt
    return None


def _assert_op_success(resp: dict) -> None:
    assert resp.get("result") in (True, 1), resp


def _wait_first_event(device, event_types: tuple[str, ...], *, timeout: float = 20.0) -> dict | None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        for event_type in event_types:
            evt = device.receive_message(match_event_type=event_type, timeout=1.0)
            if evt is not None:
                return evt
    return None


def _wait_server_conversation_unread_count(
    *,
    username: str,
    target_user: str,
    expected,
    timeout: float = 30.0,
) -> int:
    deadline = time.time() + timeout
    last_count = -1
    while time.time() < deadline:
        last_count = get_user_channel_unread_count(username=username, target_user=target_user)
        if expected(last_count):
            return last_count
        time.sleep(1.0)
    raise AssertionError(
        "服务端会话未读数未达到预期: "
        f"username={username}, target_user={target_user}, last_count={last_count}"
    )


def test_chat_5_0_clear_single_conversation_unread_count(device_a, device_b, assert_api, user_a, user_b):
    """
    SDK 5.0: Conversation.markAllMessagesAsRead 在 Flutter 端适配为
    EMChatManager.clearConversationUnreadMessageCount，只清当前会话未读数。
    """
    conv_id = user_a

    device_b.call("ChatManager", Cmd.markAllChatMsgAsRead.value, info={})
    _send_text_and_wait_success(
        device_a,
        device_b,
        assert_api,
        user_a,
        user_b,
        f"sdk5-clear-one-{uuid.uuid4().hex[:6]}",
    )
    time.sleep(1.0)

    before = device_b.call("ConversationManager", Cmd.getUnreadMsgCount.value, info=_conversation_info(conv_id))
    assert_api.assert_response_matches(
        before,
        expected={
            "manager": "ConversationManager",
            "cmd": Cmd.getUnreadMsgCount.value,
            "device": "deviceB",
            "result": 1,
        },
        ignore_keys={"sequence"},
    )

    resp_clear = device_b.call("ConversationManager", Cmd.markAllMessagesAsRead.value, info=_conversation_info(conv_id))
    assert_api.assert_response_matches(
        resp_clear,
        expected={
            "manager": "ConversationManager",
            "cmd": Cmd.markAllMessagesAsRead.value,
            "device": "deviceB",
            "result": True,
        },
        ignore_keys={"sequence"},
    )

    after = device_b.call("ConversationManager", Cmd.getUnreadMsgCount.value, info=_conversation_info(conv_id))
    assert_api.assert_response_matches(
        after,
        expected={
            "manager": "ConversationManager",
            "cmd": Cmd.getUnreadMsgCount.value,
            "device": "deviceB",
            "result": 0,
        },
        ignore_keys={"sequence"},
    )


def test_chat_5_0_message_read_receipt_fields_round_trip(device_a, device_b, assert_api, user_a, user_b):
    """
    SDK 5.0: Flutter 兼容字段 needGroupAck 映射到底层 isNeedReadReceipt；
    消息 JSON 应稳定返回 needGroupAck/hasReadAck/groupAckCount，供业务兼容旧字段名。
    """
    sent_msg = _send_text_and_wait_success(
        device_a,
        device_b,
        assert_api,
        user_a,
        user_b,
        f"sdk5-receipt-fields-{uuid.uuid4().hex[:6]}",
        need_read_receipt=True,
    )
    msg_id = sent_msg["msgId"]

    resp_msg = device_a.call("ChatManager", Cmd.getMessage.value, info={"msgId": msg_id})
    assert_api.assert_success(resp_msg)
    msg = resp_msg.get("result") or {}

    assert msg.get("msgId") == msg_id, resp_msg
    assert msg.get("needGroupAck") is True, resp_msg
    assert isinstance(msg.get("hasReadAck"), bool), resp_msg
    assert isinstance(msg.get("groupAckCount"), int), resp_msg


def test_chat_5_0_send_message_read_receipts_single_chat_success(device_a, device_b, assert_api, user_a, user_b):
    """SDK 5.0: sendMessageReadReceipts 批量接口可发送单聊消息已读回执。"""
    content = f"sdk5-single-receipt-{uuid.uuid4().hex[:6]}"
    sent_msg = _send_text_and_wait_success(
        device_a,
        device_b,
        assert_api,
        user_a,
        user_b,
        content,
        need_read_receipt=True,
    )
    recv_msg = _wait_received_message(device_b, content)
    assert recv_msg.get("msgId") == sent_msg.get("msgId"), recv_msg

    resp_ack = device_b.call(
        "ChatManager",
        Cmd.sendMessageReadReceipts.value,
        info={"msgIds": [recv_msg["msgId"]]},
    )
    _assert_op_success(resp_ack)

    evt = _wait_first_event(device_a, (Cmd.onMessageReadReceipts.value, Cmd.onMessagesRead.value), timeout=20.0)
    assert evt is not None, f"A 端未收到 onMessageReadReceipts: msgId={sent_msg['msgId']}"
    data = evt.get("data") or {}
    receipts = data.get("receipts") or data.get("messages") or []
    receipt = _find_receipt(receipts, sent_msg["msgId"])
    assert receipt is not None, evt
    assert receipt.get("convId") == user_b, evt
    assert isinstance(receipt.get("readCount"), int), evt
    assert isinstance(receipt.get("isPeerReceipt"), bool), evt


def test_chat_5_0_send_message_read_receipts_batch_same_conversation_success(device_a, device_b, assert_api, user_a, user_b):
    """SDK 5.0: sendMessageReadReceipts 支持同一单聊会话内多条消息批量发送。"""
    msg_ids = []
    for idx in range(2):
        content = f"sdk5-batch-receipt-{idx}-{uuid.uuid4().hex[:6]}"
        sent_msg = _send_text_and_wait_success(
            device_a,
            device_b,
            assert_api,
            user_a,
            user_b,
            content,
            need_read_receipt=True,
        )
        recv_msg = _wait_received_message(device_b, content)
        assert recv_msg.get("msgId") == sent_msg.get("msgId"), recv_msg
        msg_ids.append(recv_msg["msgId"])

    resp_ack = device_b.call(
        "ChatManager",
        Cmd.sendMessageReadReceipts.value,
        info={"msgIds": msg_ids},
    )
    _assert_op_success(resp_ack)


def test_chat_5_0_send_message_read_receipts_invalid_message_rejected(device_b, assert_api):
    """SDK 5.0: sendMessageReadReceipts 对空列表和不存在的消息 ID 应返回错误。"""
    resp_empty = device_b.call(
        "ChatManager",
        Cmd.sendMessageReadReceipts.value,
        info={"msgIds": []},
    )
    assert_api.assert_error(resp_empty)

    resp_missing = device_b.call(
        "ChatManager",
        Cmd.sendMessageReadReceipts.value,
        info={"msgIds": [f"missing-{uuid.uuid4().hex}"]},
    )
    assert_api.assert_error(resp_missing)


def test_chat_5_0_clear_conversation_unread_count_new_api(device_a, device_b, assert_api, user_a, user_b):
    """SDK 5.0: clearConversationUnreadMessageCount 只清指定会话未读数。"""
    device_b.call("ChatManager", Cmd.clearAllConversationUnreadMessageCount.value, info={})
    _send_text_and_wait_success(
        device_a,
        device_b,
        assert_api,
        user_a,
        user_b,
        f"sdk5-clear-one-new-{uuid.uuid4().hex[:6]}",
    )
    time.sleep(1.0)

    before = device_b.call("ConversationManager", Cmd.getUnreadMsgCount.value, info=_conversation_info(user_a))
    assert before.get("result") == 1, before

    resp_clear = device_b.call(
        "ChatManager",
        Cmd.clearConversationUnreadMessageCount.value,
        info={"convId": user_a},
    )
    _assert_op_success(resp_clear)

    after = device_b.call("ConversationManager", Cmd.getUnreadMsgCount.value, info=_conversation_info(user_a))
    assert after.get("result") == 0, after


def test_chat_5_0_clear_conversation_unread_count_clears_server_offline_count(
    device_a,
    device_b,
    assert_api,
    user_a,
    user_b,
):
    """SDK 5.0: clearConversationUnreadMessageCount 后，本地未读和服务端会话未读数均收敛为 0。"""
    content = f"sdk5-clear-server-unread-{uuid.uuid4().hex[:6]}"
    assert_api.assert_success(device_b.call("Client", Cmd.logout.value, info={"unbindToken": False}))
    device_b.drain_events(timeout=1.0)

    try:
        msg = build_text(user_a, user_b, content)
        device_a.drain_events()
        resp_send = device_a.call("ChatManager", Cmd.sendMessage.value, info=msg)
        assert_api.assert_success(resp_send)

        server_before = get_user_channel_unread_count(username=user_b, target_user=user_a)
        assert isinstance(server_before, int), server_before

        assert_api.assert_success(login_with_token(device_b, user_b))
        _wait_received_message(device_b, content, timeout=30.0)

        before = device_b.call("ConversationManager", Cmd.getUnreadMsgCount.value, info=_conversation_info(user_a))
        assert before.get("result", 0) >= 1, before

        resp_clear = device_b.call(
            "ChatManager",
            Cmd.clearConversationUnreadMessageCount.value,
            info={"convId": user_a},
        )
        _assert_op_success(resp_clear)

        after = device_b.call("ConversationManager", Cmd.getUnreadMsgCount.value, info=_conversation_info(user_a))
        assert after.get("result") == 0, after
        server_after = _wait_server_conversation_unread_count(
            username=user_b,
            target_user=user_a,
            expected=lambda count: count == 0,
        )
        assert server_after == 0
    finally:
        assert_api.assert_success(login_with_token(device_b, user_b))
        device_b.call("ChatManager", Cmd.clearConversationUnreadMessageCount.value, info={"convId": user_a})


def test_chat_5_0_clear_all_conversation_unread_count_new_api(device_a, device_b, assert_api, user_a, user_b):
    """SDK 5.0: clearAllConversationUnreadMessageCount 清理总未读数。"""
    device_b.call("ChatManager", Cmd.clearAllConversationUnreadMessageCount.value, info={})
    _send_text_and_wait_success(
        device_a,
        device_b,
        assert_api,
        user_a,
        user_b,
        f"sdk5-clear-all-new-{uuid.uuid4().hex[:6]}",
    )
    time.sleep(1.0)

    before = device_b.call("ChatManager", Cmd.getUnreadMessageCount.value, info={})
    assert before.get("result", 0) >= 1, before

    resp_clear = device_b.call("ChatManager", Cmd.clearAllConversationUnreadMessageCount.value, info={})
    _assert_op_success(resp_clear)

    after = device_b.call("ChatManager", Cmd.getUnreadMessageCount.value, info={})
    assert after.get("result") == 0, after


def test_chat_5_0_group_message_read_receipts_summary_and_page(device_a, device_b, assert_api, user_a, user_b):
    """SDK 5.0: 群消息已读回执支持批量发送、摘要查询和分页查询。"""
    group_id = ""
    try:
        group_id, _ = create_group(
            device_a,
            assert_api,
            owner=user_a,
            group_name=new_group_name("sdk5_group_receipt"),
            invite_members=[user_b],
        )
        device_a.drain_events()
        device_b.drain_events()

        content = f"sdk5-group-receipt-{uuid.uuid4().hex[:6]}"
        msg = build_text(user_a, group_id, content, chat_type=1)
        msg["needGroupAck"] = True
        resp_send = device_a.call("ChatManager", Cmd.sendMessage.value, info=msg)
        assert_api.assert_success(resp_send)
        evt_success = device_a.receive_message(match_event_type=Cmd.onMessageSuccess.value, timeout=20.0)
        sent_msg = (evt_success.get("data") or {}).get("msg") or {}
        msg_id = sent_msg.get("msgId")
        assert isinstance(msg_id, str) and msg_id, evt_success

        recv_msg = _wait_received_message(device_b, content)
        assert recv_msg.get("msgId") == msg_id, recv_msg

        resp_ack = device_b.call(
            "ChatManager",
            Cmd.sendMessageReadReceipts.value,
            info={"msgIds": [recv_msg["msgId"]]},
        )
        _assert_op_success(resp_ack)

        evt_update = _wait_first_event(device_a, (Cmd.onMessageReadReceipts.value,), timeout=20.0)
        assert evt_update is not None, f"A 端未收到群已读回执事件: msgId={msg_id}"

        resp_summary = device_a.call(
            "ChatManager",
            Cmd.getGroupMessageReadReceipts.value,
            info={"msgIds": [msg_id]},
        )
        assert_api.assert_success(resp_summary)
        summary = resp_summary.get("result") or []
        receipt = _find_receipt(summary, msg_id)
        assert receipt is not None, resp_summary
        assert receipt.get("convId") == group_id, resp_summary
        assert receipt.get("readCount", 0) >= 1, resp_summary

        resp_page = device_a.call(
            "ChatManager",
            Cmd.fetchGroupMessageReadReceipts.value,
            info={"msgId": msg_id, "group_id": group_id, "pageSize": 20, "ack_id": ""},
        )
        assert_api.assert_success(resp_page)
        page_result = resp_page.get("result") or {}
        assert isinstance(page_result.get("cursor"), str), resp_page
        items = page_result.get("list") or []
        assert any(item.get("from") == user_b for item in items if isinstance(item, dict)), resp_page
    finally:
        if group_id:
            destroy_group(device_a, assert_api, group_id, device_b=device_b)


def test_chat_5_0_group_message_read_receipts_invalid_message_rejected(device_a, assert_api):
    """SDK 5.0: 群消息回执摘要查询对不存在的消息 ID 应返回错误。"""
    resp = device_a.call(
        "ChatManager",
        Cmd.getGroupMessageReadReceipts.value,
        info={"msgIds": [f"missing-{uuid.uuid4().hex}"]},
    )
    assert_api.assert_error(resp)
