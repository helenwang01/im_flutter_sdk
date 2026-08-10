from __future__ import annotations

import uuid

import pytest

from src import Cmd
from tests.group.group_helpers import create_group, destroy_group, new_group_name


pytestmark = [pytest.mark.client, pytest.mark.group, pytest.mark.sdk_5_0]


def _cursor_list(resp: dict) -> list[dict]:
    result = resp.get("result") or {}
    items = result.get("list")
    assert isinstance(items, list), f"cursor result list 非 list: {resp}"
    return [item for item in items if isinstance(item, dict)]


def _find_member(items: list[dict], user_id: str) -> dict | None:
    for item in items:
        if item.get("userId") == user_id:
            return item
    return None


def test_group_5_0_fetch_group_members_info_owner_fields(device_a, assert_api, user_a):
    """
    SDK 5.0: fetchGroupMembersInfo 返回 EMGroupMemberInfo 游标列表。
    Flutter 当前公开模型覆盖 userId/joinedTs/role，字段必须可正常读取。
    """
    group_id = ""
    try:
        group_id, _ = create_group(
            device_a,
            assert_api,
            owner=user_a,
            group_name=new_group_name("sdk5_member_info"),
            invite_members=[],
        )

        resp = device_a.call(
            "GroupManager",
            Cmd.fetchGroupMembersInfo.value,
            info={"groupId": group_id, "cursor": "", "limit": 50},
        )
        assert_api.assert_success(resp)
        assert resp.get("manager") == "GroupManager", resp
        assert resp.get("cmd") == Cmd.fetchGroupMembersInfo.value, resp
        assert resp.get("device") == "deviceA", resp

        result = resp.get("result") or {}
        assert isinstance(result.get("cursor"), str), resp
        owner_info = _find_member(_cursor_list(resp), user_a)
        assert owner_info is not None, f"fetchGroupMembersInfo 未返回群主: user_a={user_a}, resp={resp}"
        assert owner_info.get("userId") == user_a, owner_info
        assert isinstance(owner_info.get("joinedTs"), int) and owner_info.get("joinedTs") > 0, owner_info
        assert isinstance(owner_info.get("role"), int) and owner_info.get("role") >= 0, owner_info
        assert "userId" in str(owner_info), owner_info
    finally:
        if group_id:
            destroy_group(device_a, assert_api, group_id)


def test_group_5_0_update_group_avatar_then_read_local_group(device_a, assert_api, user_a):
    """
    SDK 5.0: 创建群支持 avatarUrl，且群主可更新群头像。
    更新后返回对象和本地 getGroupWithId 均应体现最新 avatarUrl。
    """
    group_id = ""
    avatar_url = f"https://example.com/native-auto-test/{uuid.uuid4().hex}.png"
    try:
        group_id, _ = create_group(
            device_a,
            assert_api,
            owner=user_a,
            group_name=new_group_name("sdk5_group_avatar"),
            invite_members=[],
        )

        resp_update = device_a.call(
            "GroupManager",
            Cmd.updateGroupAvatar.value,
            info={"groupId": group_id, "avatarUrl": avatar_url},
        )
        assert_api.assert_success(resp_update)
        updated_group = resp_update.get("result") or {}
        assert updated_group.get("groupId") == group_id, resp_update
        assert updated_group.get("avatarUrl") == avatar_url, resp_update

        resp_local = device_a.call("GroupManager", Cmd.getGroupWithId.value, info={"groupId": group_id})
        assert_api.assert_success(resp_local)
        local_group = resp_local.get("result") or {}
        assert local_group.get("groupId") == group_id, resp_local
        assert local_group.get("avatarUrl") == avatar_url, resp_local
    finally:
        if group_id:
            destroy_group(device_a, assert_api, group_id)


def test_group_5_0_update_group_options_max_count_and_ext(device_a, assert_api, user_a):
    """SDK 5.0: updateGroupOptions 可通过 EMGroupConfigs 更新指定配置项。"""
    group_id = ""
    ext = f"sdk5-ext-{uuid.uuid4().hex[:8]}"
    try:
        group_id, _ = create_group(
            device_a,
            assert_api,
            owner=user_a,
            group_name=new_group_name("sdk5_group_options"),
            invite_members=[],
        )

        resp_update = device_a.call(
            "GroupManager",
            Cmd.updateGroupOptions.value,
            info={
                "groupId": group_id,
                "options": {
                    "style": 0,
                    "maxCount": 201,
                    "inviteNeedConfirm": False,
                    "ext": ext,
                },
                "types": 40,
            },
        )
        assert_api.assert_success(resp_update)
        updated_group = resp_update.get("result") or {}
        assert updated_group.get("groupId") == group_id, resp_update
        assert updated_group.get("ext") == ext, resp_update
        assert updated_group.get("maxUserCount") == 201, resp_update

        resp_server = device_a.call(
            "GroupManager",
            Cmd.getGroupSpecificationFromServer.value,
            info={"groupId": group_id, "fetchMembers": True},
        )
        assert_api.assert_success(resp_server)
        server_group = resp_server.get("result") or {}
        assert server_group.get("ext") == ext, resp_server
        assert server_group.get("maxUserCount") == 201, resp_server
    finally:
        if group_id:
            destroy_group(device_a, assert_api, group_id)


def test_group_5_0_update_group_options_partial_does_not_overwrite_ext(device_a, assert_api, user_a):
    """SDK 5.0: 只更新 maxCount 时，不应覆盖未声明更新的 ext。"""
    group_id = ""
    ext = f"sdk5-partial-ext-{uuid.uuid4().hex[:8]}"
    try:
        group_id, _ = create_group(
            device_a,
            assert_api,
            owner=user_a,
            group_name=new_group_name("sdk5_group_partial"),
            invite_members=[],
        )

        resp_ext = device_a.call("GroupManager", Cmd.updateGroupExt.value, info={"groupId": group_id, "ext": ext})
        assert_api.assert_success(resp_ext)

        resp_update = device_a.call(
            "GroupManager",
            Cmd.updateGroupOptions.value,
            info={
                "groupId": group_id,
                "options": {
                    "style": 0,
                    "maxCount": 202,
                    "inviteNeedConfirm": False,
                    "ext": "should-not-apply",
                },
                "types": 8,
            },
        )
        assert_api.assert_success(resp_update)
        updated_group = resp_update.get("result") or {}
        assert updated_group.get("maxUserCount") == 202, resp_update

        resp_server = device_a.call(
            "GroupManager",
            Cmd.getGroupSpecificationFromServer.value,
            info={"groupId": group_id, "fetchMembers": True},
        )
        assert_api.assert_success(resp_server)
        server_group = resp_server.get("result") or {}
        assert server_group.get("ext") == ext, resp_server
        assert server_group.get("maxUserCount") == 202, resp_server
    finally:
        if group_id:
            destroy_group(device_a, assert_api, group_id)


def test_group_5_0_update_group_options_allow_invites_only(device_a, assert_api, user_a):
    """SDK 5.0: updateGroupOptions types=ALLOW_INVITES 只更新成员邀请开关。"""
    group_id = ""
    ext = f"sdk5-allow-invite-ext-{uuid.uuid4().hex[:8]}"
    try:
        group_id, _ = create_group(
            device_a,
            assert_api,
            owner=user_a,
            group_name=new_group_name("sdk5_group_allow_invites"),
            invite_members=[],
        )
        resp_ext = device_a.call("GroupManager", Cmd.updateGroupExt.value, info={"groupId": group_id, "ext": ext})
        assert_api.assert_success(resp_ext)

        resp_update = device_a.call(
            "GroupManager",
            Cmd.updateGroupOptions.value,
            info={
                "groupId": group_id,
                "options": {
                    "style": 1,
                    "maxCount": 260,
                    "inviteNeedConfirm": False,
                    "ext": "should-not-apply",
                },
                "types": 4,
            },
        )
        assert_api.assert_success(resp_update)
        updated_group = resp_update.get("result") or {}
        assert updated_group.get("isMemberAllowToInvite") is True, resp_update

        resp_server = device_a.call(
            "GroupManager",
            Cmd.getGroupSpecificationFromServer.value,
            info={"groupId": group_id, "fetchMembers": True},
        )
        assert_api.assert_success(resp_server)
        server_group = resp_server.get("result") or {}
        assert server_group.get("isMemberAllowToInvite") is True, resp_server
        assert server_group.get("ext") == ext, resp_server
        assert server_group.get("maxUserCount") == 200, resp_server
    finally:
        if group_id:
            destroy_group(device_a, assert_api, group_id)


def test_group_5_0_update_group_options_public_join_approval_bits(device_a, assert_api, user_a):
    """SDK 5.0: updateGroupOptions types=IS_PUBLIC|JOIN_APPROVAL_REQUIRED 更新公开群入群审批位。"""
    group_id = ""
    try:
        group_id, _ = create_group(
            device_a,
            assert_api,
            owner=user_a,
            group_name=new_group_name("sdk5_group_public_bits"),
            invite_members=[],
        )

        resp_update = device_a.call(
            "GroupManager",
            Cmd.updateGroupOptions.value,
            info={
                "groupId": group_id,
                "options": {
                    "style": 2,
                    "maxCount": 261,
                    "inviteNeedConfirm": False,
                    "ext": "should-not-apply",
                },
                "types": 3,
            },
        )
        assert_api.assert_success(resp_update)

        resp_server = device_a.call(
            "GroupManager",
            Cmd.getGroupSpecificationFromServer.value,
            info={"groupId": group_id, "fetchMembers": True},
        )
        assert_api.assert_success(resp_server)
        server_group = resp_server.get("result") or {}
        assert server_group.get("isMemberOnly") is True, resp_server
        assert server_group.get("maxUserCount") == 200, resp_server
        assert server_group.get("ext") == "auto-ext", resp_server
    finally:
        if group_id:
            destroy_group(device_a, assert_api, group_id)


def test_group_5_0_update_group_options_invite_confirm_only(device_a, assert_api, user_a):
    """SDK 5.0: updateGroupOptions types=INVITE_NEED_CONFIRM 可单独更新邀请确认配置。"""
    group_id = ""
    try:
        group_id, _ = create_group(
            device_a,
            assert_api,
            owner=user_a,
            group_name=new_group_name("sdk5_group_invite_confirm"),
            invite_members=[],
        )

        resp_update = device_a.call(
            "GroupManager",
            Cmd.updateGroupOptions.value,
            info={
                "groupId": group_id,
                "options": {
                    "style": 0,
                    "maxCount": 262,
                    "inviteNeedConfirm": True,
                    "ext": "should-not-apply",
                },
                "types": 16,
            },
        )
        assert_api.assert_success(resp_update)

        resp_server = device_a.call(
            "GroupManager",
            Cmd.getGroupSpecificationFromServer.value,
            info={"groupId": group_id, "fetchMembers": True},
        )
        assert_api.assert_success(resp_server)
        server_group = resp_server.get("result") or {}
        assert server_group.get("maxUserCount") == 200, resp_server
        assert server_group.get("ext") == "auto-ext", resp_server
        assert server_group.get("isMemberAllowToInvite") is False, resp_server
    finally:
        if group_id:
            destroy_group(device_a, assert_api, group_id)
