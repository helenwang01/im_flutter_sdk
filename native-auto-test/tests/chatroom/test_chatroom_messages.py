from __future__ import annotations

import json
import uuid

import pytest

from src import Cmd
from tests.chat._utils import build_text
from tests.chatroom.chatroom_helpers import create_chatroom_or_skip, safe_delete_chatroom

pytestmark = [pytest.mark.client, pytest.mark.chatroom, pytest.mark.agorachat1_4_0]


def _log_chatroom_message_step(step: str, **payload) -> None:
    print(f"[CHATROOM_MESSAGE][{step}] {json.dumps(payload, ensure_ascii=False, default=str)}", flush=True)


def _drain(device_a, device_b) -> None:
    try:
        device_a.drain_events(timeout=1.0)
        device_b.drain_events(timeout=1.0)
    except Exception:
        pass


def _message_body_content(message: dict) -> str | None:
    body = message.get("body") if isinstance(message, dict) else None
    return body.get("content") if isinstance(body, dict) else None


def _join_chatroom_as_b(device_b, room_id: str) -> None:
    resp = device_b.call("ChatRoomManager", Cmd.joinChatRoom.value, info={"roomId": room_id})
    _log_chatroom_message_step("joinChatRoom.response", roomId=room_id, response=resp)
    assert resp.get("manager") == "ChatRoomManager", f"joinChatRoom manager 不匹配: {resp!r}"
    assert resp.get("cmd") == Cmd.joinChatRoom.value, f"joinChatRoom cmd 不匹配: {resp!r}"
    assert resp.get("device") == "deviceB", f"joinChatRoom device 不匹配: {resp!r}"
    assert "error" not in resp, f"joinChatRoom 返回错误: {resp!r}"
    assert resp.get("result") is not None, f"joinChatRoom 未返回 result: {resp!r}"


def _assert_send_success_event(evt: dict, *, from_user: str, room_id: str, content: str) -> str:
    assert evt and evt.get("type") == "event", f"未收到发送成功事件: {evt!r}"
    assert evt.get("eventType") == Cmd.onMessageSuccess.value, f"发送成功事件类型不匹配: {evt!r}"
    data = evt.get("data") or {}
    msg = data.get("msg") or {}
    msg_id = msg.get("msgId") or data.get("msgId")
    assert msg_id, f"onMessageSuccess 未返回 msgId: {evt!r}"
    assert msg.get("from") == from_user, f"发送方不匹配: {evt!r}"
    assert msg.get("to") == room_id, f"聊天室消息 to 应为 roomId: {evt!r}"
    assert msg.get("convId") == room_id, f"聊天室消息 convId 应为 roomId: {evt!r}"
    assert msg.get("chatType") == 2, f"聊天室消息 chatType 应为 2: {evt!r}"
    assert _message_body_content(msg) == content, f"聊天室消息内容不匹配: {evt!r}"
    return str(msg_id)


def _assert_room_message_received(evt: dict, *, from_user: str, room_id: str, content: str, msg_id: str | None = None) -> None:
    assert evt and evt.get("type") == "event", f"未收到聊天室消息接收事件: {evt!r}"
    assert evt.get("eventType") == Cmd.onMessagesReceived.value, f"接收事件类型不匹配: {evt!r}"
    messages = ((evt.get("data") or {}).get("messages") or [])
    assert isinstance(messages, list), f"onMessagesReceived.messages 应为 list: {evt!r}"
    matched = []
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        if msg.get("from") != from_user:
            continue
        if msg.get("to") != room_id:
            continue
        if msg.get("convId") != room_id:
            continue
        if msg.get("chatType") != 2:
            continue
        if _message_body_content(msg) != content:
            continue
        if msg_id and str(msg.get("msgId")) != str(msg_id):
            continue
        matched.append(msg)
    assert matched, f"接收事件未包含当前聊天室消息: msgId={msg_id}, roomId={room_id}, content={content}, evt={evt!r}"


def test_chatroom_send_text_message_received_by_member(device_a, device_b, assert_api, user_a, user_b):
    room_id, _ = create_chatroom_or_skip(owner=user_a, name_prefix="msg_txt", desc_prefix="msg_txt")
    try:
        _join_chatroom_as_b(device_b, room_id)
        _drain(device_a, device_b)

        content = f"chatroom-text-{uuid.uuid4().hex[:8]}"
        info = build_text(user_a, room_id, content, chat_type=2)
        _log_chatroom_message_step("sendMessage.request", roomId=room_id, fromUser=user_a, to=room_id, chatType=2, content=content, info=info)
        resp = device_a.call("ChatManager", Cmd.sendMessage.value, info=info)
        _log_chatroom_message_step("sendMessage.response", roomId=room_id, content=content, response=resp)

        evt_success = device_a.receive_message(match_event_type=Cmd.onMessageSuccess.value, timeout=20.0)
        _log_chatroom_message_step("sendMessage.onMessageSuccess", roomId=room_id, content=content, event=evt_success)
        msg_id = _assert_send_success_event(evt_success, from_user=user_a, room_id=room_id, content=content)
        evt_received = device_b.receive_message(match_event_type=Cmd.onMessagesReceived.value, timeout=20.0)
        _log_chatroom_message_step("sendMessage.onMessagesReceived", roomId=room_id, content=content, msgId=msg_id, event=evt_received)
        _assert_room_message_received(evt_received, from_user=user_a, room_id=room_id, content=content, msg_id=msg_id)
    finally:
        safe_delete_chatroom(room_id)


def test_chatroom_send_text_message_with_type_received_by_member(device_a, device_b, assert_api, user_a, user_b):
    room_id, _ = create_chatroom_or_skip(owner=user_a, name_prefix="msg_type", desc_prefix="msg_type")
    try:
        _join_chatroom_as_b(device_b, room_id)
        _drain(device_a, device_b)

        content = f"chatroom-type-{uuid.uuid4().hex[:8]}"
        info = {
            "type": "txt",
            "payload": {"targetId": room_id, "content": content},
            "chatType": 2,
        }
        _log_chatroom_message_step("sendMessageWithType.request", roomId=room_id, fromUser=user_a, targetId=room_id, chatType=2, content=content, info=info)
        resp = device_a.call("ChatManager", Cmd.sendMessageWithType.value, info=info)
        _log_chatroom_message_step("sendMessageWithType.response", roomId=room_id, content=content, response=resp)
        if resp.get("success") is False and "MissingPluginException" in str((resp.get("error") or {}).get("description", "")):
            pytest.skip("MissingPlugin: sendMessageWithType 未在当前集成端实现")
        assert resp.get("manager") == "ChatManager", f"sendMessageWithType manager 不匹配: {resp!r}"
        assert resp.get("cmd") == Cmd.sendMessageWithType.value, f"sendMessageWithType cmd 不匹配: {resp!r}"
        assert resp.get("device") == "deviceA", f"sendMessageWithType device 不匹配: {resp!r}"
        assert "error" not in resp, f"sendMessageWithType 返回错误: {resp!r}"
        result = resp.get("result") or {}
        assert result.get("to") == room_id, f"sendMessageWithType to 应为 roomId: {resp!r}"
        assert result.get("convId") == room_id, f"sendMessageWithType convId 应为 roomId: {resp!r}"
        assert result.get("chatType") == 2, f"sendMessageWithType chatType 应为 2: {resp!r}"
        assert _message_body_content(result) == content, f"sendMessageWithType 内容不匹配: {resp!r}"

        evt_success = device_a.receive_message(match_event_type=Cmd.onMessageSuccess.value, timeout=20.0)
        _log_chatroom_message_step("sendMessageWithType.onMessageSuccess", roomId=room_id, content=content, event=evt_success)
        msg_id = _assert_send_success_event(evt_success, from_user=user_a, room_id=room_id, content=content)
        evt_received = device_b.receive_message(match_event_type=Cmd.onMessagesReceived.value, timeout=20.0)
        _log_chatroom_message_step("sendMessageWithType.onMessagesReceived", roomId=room_id, content=content, msgId=msg_id, event=evt_received)
        _assert_room_message_received(evt_received, from_user=user_a, room_id=room_id, content=content, msg_id=msg_id)
    finally:
        safe_delete_chatroom(room_id)
