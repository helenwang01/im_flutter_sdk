"""REST 群组造数。"""
from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

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


def _extract_group_id(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("groupid", "groupId", "id"):
            value = payload.get(key)
            if isinstance(value, str) and value:
                return value
        for key in ("data", "entities"):
            value = payload.get(key)
            if isinstance(value, dict):
                gid = _extract_group_id(value)
                if gid:
                    return gid
            if isinstance(value, list):
                for item in value:
                    gid = _extract_group_id(item)
                    if gid:
                        return gid
    return ""


def create_group(*, owner: str, group_name: str, members: list[str] | None = None) -> tuple[str, dict]:
    """通过 REST 创建群，返回 group_id 和原始响应。"""
    base = get_rest_base_url().rstrip("/")
    auth = _authorization_header()
    if not base or not auth:
        raise RuntimeError("rest_api.base_url 与 auth_token 需在 config.yaml 的 rest_api 中配置")

    body = {
        "groupname": group_name,
        "desc": "native-auto-test second channel 101",
        "public": True,
        "allowinvites": True,
        "maxusers": 200,
        "approval": False,
        "owner": owner,
        "members": members or [],
    }
    req = urllib.request.Request(
        f"{base}/chatgroups",
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
            parsed = json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        raise RuntimeError(f"REST 创建群失败 HTTP {e.code}: {raw}") from e
    group_id = _extract_group_id(parsed)
    if not group_id:
        raise RuntimeError(f"REST 创建群响应中未找到 groupId: {parsed!r}")
    return group_id, parsed


def add_group_members(*, group_id: str, members: list[str]) -> dict:
    """通过 REST 批量添加群成员。"""
    base = get_rest_base_url().rstrip("/")
    auth = _authorization_header()
    if not base or not auth:
        raise RuntimeError("rest_api.base_url 与 auth_token 需在 config.yaml 的 rest_api 中配置")

    group_enc = urllib.parse.quote(group_id, safe="")
    req = urllib.request.Request(
        f"{base}/chatgroups/{group_enc}/users",
        data=json.dumps({"usernames": members}).encode("utf-8"),
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
        raise RuntimeError(f"REST 批量添加群成员失败 HTTP {e.code}: {raw}") from e
