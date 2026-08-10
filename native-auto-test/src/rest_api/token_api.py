"""Token 获取：5.0 登录统一使用 token，不再使用密码登录。"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from ..tools.config import get_token_api_ttl, get_token_api_url


def _extract_token(payload: Any) -> str:
    if not isinstance(payload, dict):
        return ""
    for key in ("access_token", "token", "userToken", "im_token"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            return value
    entity = payload.get("entity") or payload.get("data")
    if isinstance(entity, dict):
        return _extract_token(entity)
    return ""


def fetch_login_token(username: str, password: str = "1") -> str:
    """
    等价于：
      curl --location '<rest_api.base_url>/token' \
        --header 'Content-Type: application/json' \
        --data '{"grant_type":"password","username":"tst01","password":"1","ttl":6000000}'

    token URL 由 config.yaml 的 rest_api.base_url 拼接 /token 得到。
    """
    url = get_token_api_url()
    body = {
        "grant_type": "password",
        "username": username,
        "password": password,
        "ttl": get_token_api_ttl(),
    }
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        raw = e.read().decode() if e.fp else ""
        raise RuntimeError(f"获取登录 token 失败 HTTP {e.code}: {raw}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"获取登录 token 失败: {e.reason!r}") from e

    try:
        parsed = json.loads(raw) if raw.strip() else {}
    except json.JSONDecodeError as e:
        raise RuntimeError(f"获取登录 token 返回非 JSON: {raw}") from e
    token = _extract_token(parsed)
    if not token:
        raise RuntimeError(f"获取登录 token 响应中未找到 token 字段: {parsed!r}")
    return token
