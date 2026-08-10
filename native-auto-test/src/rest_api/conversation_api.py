"""REST 会话列表造数与状态更新。"""
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


def pin_user_channel_top(*, username: str, target_user: str, conversation_type: str = "chat") -> dict:
    """通过 REST 将指定用户的单聊/群聊会话置顶。"""
    base = get_rest_base_url().rstrip("/")
    auth = _authorization_header()
    if not base or not auth:
        raise RuntimeError("rest_api.base_url 与 auth_token 需在 config.yaml 的 rest_api 中配置")

    user_enc = urllib.parse.quote(username, safe="")
    body = {"type": conversation_type, "to": target_user}
    req = urllib.request.Request(
        f"{base}/user/{user_enc}/user_channel/top",
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
        raise RuntimeError(f"REST 置顶用户会话失败 HTTP {e.code}: {raw}") from e


def get_user_channels(
    *,
    username: str,
    limit: int = 50,
    need_empty_session: bool = True,
    need_mark: bool = True,
) -> dict:
    """通过 REST 拉取指定用户的服务端会话列表。"""
    base = get_rest_base_url().rstrip("/")
    auth = _authorization_header()
    if not base or not auth:
        raise RuntimeError("rest_api.base_url 与 auth_token 需在 config.yaml 的 rest_api 中配置")

    user_enc = urllib.parse.quote(username, safe="")
    query = urllib.parse.urlencode(
        {
            "limit": limit,
            "needEmptySession": str(need_empty_session).lower(),
            "need_mark": str(need_mark).lower(),
        }
    )
    req = urllib.request.Request(
        f"{base}/sdk/user/{user_enc}/user_channels/list?{query}",
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
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        raise RuntimeError(f"REST 获取用户会话列表失败 HTTP {e.code}: {raw}") from e


def get_user_channel_unread_count(
    *,
    username: str,
    target_user: str,
    conversation_type: str = "chat",
    limit: int = 50,
) -> int:
    """通过 REST 会话列表查询指定会话的服务端未读数。"""
    payload = get_user_channels(username=username, limit=limit)
    data = payload.get("data") if isinstance(payload, dict) else None
    channel_infos = data.get("channel_infos") if isinstance(data, dict) else None
    if not isinstance(channel_infos, list):
        raise RuntimeError(f"REST 会话列表响应缺少 data.channel_infos: {payload!r}")

    for item in channel_infos:
        if not isinstance(item, dict):
            continue
        if item.get("session_type") != conversation_type:
            continue
        if item.get("session_to") != target_user:
            continue
        unread = item.get("unread_num", 0)
        if isinstance(unread, int):
            return unread
        if isinstance(unread, str) and unread.isdigit():
            return int(unread)
        raise RuntimeError(f"REST 会话未读数字段非法: {item!r}")
    return 0
