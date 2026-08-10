"""REST 消息造数。"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

from ..tools.config import get_rest_auth_token, get_rest_base_url, get_rest_verify_ssl


def _authorization_header() -> str:
    token = get_rest_auth_token()
    if not token:
        return ""
    return token if str(token).lower().startswith("bearer ") else f"Bearer {token}"


def _urlopen(req: urllib.request.Request, timeout: float = 30):
    if get_rest_verify_ssl():
        return urllib.request.urlopen(req, timeout=timeout)
    return urllib.request.urlopen(req, timeout=timeout, context=ssl._create_unverified_context())


def send_text_message(*, from_user: str, target_user: str, content: str) -> dict:
    """通过 REST 发送单聊文本消息。"""
    base = get_rest_base_url().rstrip("/")
    auth = _authorization_header()
    if not base or not auth:
        raise RuntimeError("rest_api.base_url 与 auth_token 需在 config.yaml 的 rest_api 中配置")

    body = {
        "target_type": "users",
        "target": [target_user],
        "msg": {"type": "txt", "msg": content},
        "from": from_user,
    }
    req = urllib.request.Request(
        f"{base}/messages?useMsgId=true",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": auth,
        },
    )
    try:
        with _urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        raise RuntimeError(f"发送 REST 单聊消息失败 HTTP {e.code}: {raw}") from e


def delete_all_user_roaming_messages(*, username: str, is_notify: bool = False) -> dict:
    """通过 REST 删除指定用户所有漫游消息/会话快照。"""
    base = get_rest_base_url().rstrip("/")
    auth = _authorization_header()
    if not base or not auth:
        raise RuntimeError("rest_api.base_url 与 auth_token 需在 config.yaml 的 rest_api 中配置")

    user_enc = urllib.parse.quote(username, safe="")
    notify = "true" if is_notify else "false"
    req = urllib.request.Request(
        f"{base}/sdk/message/roaming/user/{user_enc}/delete/all?isNotify={notify}",
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": auth,
        },
    )
    try:
        with _urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        raise RuntimeError(f"REST 删除用户漫游消息失败 HTTP {e.code}: {raw}") from e


def get_user_offline_message_count(*, username: str) -> int:
    """通过 REST 查询指定用户的服务端离线未读消息数。"""
    base = get_rest_base_url().rstrip("/")
    auth = _authorization_header()
    if not base or not auth:
        raise RuntimeError("rest_api.base_url 与 auth_token 需在 config.yaml 的 rest_api 中配置")

    user_enc = urllib.parse.quote(username, safe="")
    req = urllib.request.Request(
        f"{base}/users/{user_enc}/offline_msg_count",
        method="GET",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": auth,
        },
    )
    try:
        with _urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            payload = json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        raise RuntimeError(f"REST 查询离线未读数失败 HTTP {e.code}: {raw}") from e

    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        value = data.get(username)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    count = payload.get("count") if isinstance(payload, dict) else None
    if isinstance(count, int):
        return count
    raise RuntimeError(f"REST 查询离线未读数响应缺少 data.{username}: {payload!r}")
