"""
Pytest fixtures：WebSocket 配置、topic、请求封装等。
全局登录/登出：session 开始时对所有设备登录，session 结束时登出，用例内不需要写 login/logout。
Allure：请求、响应、比对结果会写入报告（需安装 allure-pytest，运行 pytest --alluredir=...）。
"""
from __future__ import annotations

import json
import sys
import time
from contextlib import nullcontext
from pathlib import Path

import pytest

# 保证能 import src
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.tools.config import get_default_topic, get_topic, get_test_accounts
from src.rest_api.token_api import fetch_login_token
from src.rest_api.user_api import create_users
from src.tools.ws_client import (
    request as ws_request,
    request_and_wait_for_event as ws_request_and_wait_event,
    MessageListener,
    DeviceConnection,
)
from src.tools import assertions
from src import Cmd

# 5.0 已删除密码登录，测试登录统一先从业务接口换 token，再走 loginWithToken。
SESSION_PWD = "1"


# ----- Allure 工具 -----

def _allure_step(name: str):
    """安全获取 allure.step context manager；未安装时返回 nullcontext。"""
    try:
        import allure
        return allure.step(name)
    except ImportError:
        return nullcontext()


def _attach_request_response_allure(step_name: str, request_body: dict, response_body: dict) -> None:
    """将请求与响应以 JSON 附件形式写入 Allure 报告。"""
    try:
        import allure
        with allure.step(step_name):
            allure.attach(
                json.dumps(request_body, ensure_ascii=False, indent=2),
                "请求",
                allure.attachment_type.JSON,
            )
            allure.attach(
                json.dumps(response_body, ensure_ascii=False, indent=2, default=str),
                "响应",
                allure.attachment_type.JSON,
            )
    except ImportError:
        pass


# ----- 登录前清空回调 -----

def _drain_all_callbacks_before_cases(device: str, idle_timeout: float = 2.0, max_messages: int = 200) -> None:
    """登录后把该设备 topic 上残留的所有回调收掉并丢弃，避免影响后续用例。"""
    listener = MessageListener(topic=get_topic(device), device=device)
    listener.start()
    try:
        received = 0
        while received < max_messages:
            msg = listener.receive_message(timeout=idle_timeout)
            if msg is None:
                break
            received += 1
        listener.drain_buffer()
    finally:
        listener.stop()


# ----- Session 登录 / 登出（抽出为独立函数，结构清晰） -----

def login_with_token(device, username: str, password: str = SESSION_PWD) -> dict:
    """使用业务 token 登录。5.0 不再使用密码登录。"""
    token = fetch_login_token(username, password)
    return device.call(
        "Client",
        Cmd.login.value,
        info={"userId": username, "pwdOrToken": token, "isPassword": False},
    )


def _session_login(
    device_a,
    device_b,
    user_a: str,
    user_b: str,
    password: str = SESSION_PWD,
) -> None:
    """
    所有 test_* cases 执行前调用一次：deviceA 以 user_a、deviceB 以 user_b 登录，并清空该连接上的回调。
    """
    with _allure_step("Session token 登录"):
        resp_a = login_with_token(device_a, user_a, password)
        resp_b = login_with_token(device_b, user_b, password)

        def _ok(r: dict) -> bool:
            res = r.get("result")
            # 成功条件：
            # - True/1
            # - 非空字符串用户名
            # - 字典：无 code 字段，或 code==200（已登录）
            if res is True or res == 1:
                return True
            if isinstance(res, str) and res.strip():
                return True
            if isinstance(res, dict):
                code = res.get("code")
                if code is None or int(code) == 200:
                    return True
            return False

        if not (_ok(resp_a) and _ok(resp_b)):
            import pytest as _pytest
            _pytest.exit(
                "登录失败，已中止本次用例执行。\n"
                f"deviceA: {resp_a}\n"
                f"deviceB: {resp_b}\n"
                "排查建议：\n"
                "1) 确认 config.yaml 的 test_accounts 指向 token 接口可换取 token 的账号，默认 tst01/tst02/tst03。\n"
                "2) 检查 rest_api.base_url（会拼接 /token）、rest_api.token_ttl 与账号密码是否正确。\n"
                "3) 检查 config.yaml.websocket.base_url 与 topics 是否指向在线集成端。\n"
            )

    device_a.drain_events()
    device_b.drain_events()

    # 某些端需显式开启 Chat 消息回调；若 WS 端未实现可忽略报错
    try:
        device_a.call("Client", Cmd.startCallback.value, info={})
    except Exception:
        pass
    try:
        device_b.call("Client", Cmd.startCallback.value, info={})
    except Exception:
        pass

def _session_logout(device_a, device_b) -> None:
    """
    所有 test_* cases 执行后调用一次：deviceA、deviceB 各登出一次。
    登出失败不阻断 teardown，仅记录到 Allure。
    """
    with _allure_step("Session 登出"):
        for name, dev in [("deviceA", device_a), ("deviceB", device_b)]:
            try:
                dev.call("Client", Cmd.logout.value, info={"unbindToken": False})
            except Exception as e:
                try:
                    import allure
                    allure.attach(str(e), f"登出失败 {name}", allure.attachment_type.TEXT)
                except ImportError:
                    pass


# ----- Fixtures -----

def pytest_addoption(parser):
    parser.addoption(
        "--ws-debug",
        action="store_true",
        default=False,
        help="Capture and print all WebSocket messages during chat tests for debugging.",
    )
    parser.addoption(
        "--ws-relax-success",
        action="store_true",
        default=False,
        help="When set, do not require exact eventType for onMessageSuccess; accept first incoming event and print its type.",
    )

    parser.addoption(
        "--ws-relax-received",
        action="store_true",
        default=False,
        help="When set, do not require exact eventType for onMessagesReceived; accept first incoming event and print its type.",
    )



    parser.addoption(
        "--ws-relax",
        action="store_true",
        default=False,
        help="Relax all event matching for chat tests (success/received).",
    )
@pytest.fixture(scope="session")
def ws_debug(request) -> bool:
    return bool(request.config.getoption("--ws-debug"))

@pytest.fixture(scope="session")
def ws_relax(request) -> bool:
    # unified flag; also respect older fine-grained flags if provided
    return bool(request.config.getoption("--ws-relax")
                or request.config.getoption("--ws-relax-success")
                or request.config.getoption("--ws-relax-received"))

@pytest.fixture(scope="session")
def ws_relax_success(request) -> bool:
    return bool(request.config.getoption("--ws-relax-success"))

@pytest.fixture(scope="session")
def ws_relax_received(request) -> bool:
    return bool(request.config.getoption("--ws-relax-received"))


@pytest.fixture(scope="session")
def ws_topic() -> str:
    """默认 WebSocket topic，与 Flutter 端一致。"""
    return get_default_topic()


@pytest.fixture(scope="session")
def ws_device() -> str | None:
    """多端测试时的设备标识，对应 config 中 topics 的 key。"""
    return None


@pytest.fixture(scope="session")
def api(ws_topic: str, ws_device: str | None):
    """
    封装一次请求的 helper：api.call(manager, cmd, info) -> response。
    session 内全局已登录，用例内无需再 login。
    """
    topic = get_topic(ws_device) if ws_device else ws_topic

    def _call(manager: str, cmd: str, info: dict | None = None, **kwargs):
        req = {"manager": manager, "cmd": cmd, "info": info or {}, "topic": topic, "device": ws_device, **kwargs}
        resp = ws_request(manager=manager, cmd=cmd, info=info, topic=topic, device=ws_device, **kwargs)
        _attach_request_response_allure(f"API 请求 {manager}.{cmd}", req, resp)
        return resp

    def _call_and_wait_event(manager: str, cmd: str, info: dict | None = None, *, event_type: str, event_timeout: float = 10.0, **kwargs):
        return ws_request_and_wait_event(
            manager=manager, cmd=cmd, info=info, topic=topic, device=ws_device,
            event_type=event_type, event_timeout=event_timeout, **kwargs,
        )

    class _API:
        call = staticmethod(_call)
        call_and_wait_event = staticmethod(_call_and_wait_event)
    return _API()


def _make_api(device: str):
    """按设备标识构造 api（topic 从 config topics 读取）。"""
    topic = get_topic(device)

    def _call(manager: str, cmd: str, info: dict | None = None, **kwargs):
        req = {"manager": manager, "cmd": cmd, "info": info or {}, "topic": topic, "device": device, **kwargs}
        resp = ws_request(manager=manager, cmd=cmd, info=info, topic=topic, device=device, **kwargs)
        _attach_request_response_allure(f"API 请求 {manager}.{cmd} (device={device})", req, resp)
        return resp

    class _API:
        call = staticmethod(_call)
    return _API()


@pytest.fixture(scope="session")
def api_device_a():
    """设备 A 的 api（config 中 topics.deviceA）；session 内已以 user_a 登录。"""
    return _make_api("deviceA")


@pytest.fixture(scope="session")
def api_device_b():
    """设备 B 的 api（config 中 topics.deviceB）；session 内已以 user_b 登录。"""
    return _make_api("deviceB")


def _test_usernames() -> tuple[str, str, str]:
    """返回固定测试账号，默认 tst01/tst02/tst03，可由 config.yaml 覆盖。"""
    accounts = get_test_accounts()
    return accounts["user_a"], accounts["user_b"], accounts["user_c"]


@pytest.fixture(scope="session")
def created_test_users():
    """
    Session 内使用固定测试账号，并在 token 登录前通过 REST 确保账号存在。
    SDK 5.0 已删除客户端创建账号和密码登录；测试侧先造号，再换 token 登录。
    """
    users = _test_usernames()
    with _allure_step("创建/确认测试用户"):
        create_resp = create_users([{"username": user, "password": SESSION_PWD} for user in users])
    if isinstance(create_resp, dict) and create_resp.get("error"):
        pytest.exit(
            "创建/确认测试用户失败，已中止本次用例执行。\n"
            f"{json.dumps(create_resp, ensure_ascii=False, indent=2, default=str)}\n"
            "排查建议：确认 config.yaml 的 rest_api.base_url 与 rest_api.auth_token 可创建测试账号。",
        )
    yield users


@pytest.fixture(scope="session")
def user_a(created_test_users):
    """设备 A 对应用户名（session 内创建，teardown 删除）。"""
    return created_test_users[0]


@pytest.fixture(scope="session")
def user_b(created_test_users):
    """设备 B 对应用户名（session 内创建，teardown 删除）。"""
    return created_test_users[1]

@pytest.fixture(scope="session")
def user_c(created_test_users):
    """设备 A 对应用户名（session 内创建，teardown 删除）。"""
    return created_test_users[2]

@pytest.fixture(scope="session", autouse=True)
def global_login_logout(device_a, device_b, created_test_users):
    """
    全 session 只执行一次（autouse=True）：
    - setup：用 created_test_users 的两人在 device_a/device_b 上登录并清空回调。
    - teardown：登出两设备。用户删除由 created_test_users 的 teardown 负责。
    """
    user_a, user_b, user_c = created_test_users
    _session_login(device_a, device_b, user_a, user_b, SESSION_PWD)
    yield
    _session_logout(device_a, device_b)


@pytest.fixture
def message_listener():
    """
    消息监听器工厂：传入设备标识返回对应的监听器。
    用法：listener = message_listener("deviceB")
    - .receive_message(match_cmd=..., match_event_type=..., timeout=...) 按条件取第一条。
    - 不匹配的消息会进缓冲；drain_buffer() 可一次性取出缓冲。
    - 用例结束自动 stop() 所有创建的监听器。
    """
    listeners = []

    def _create(device: str):
        topic = get_topic(device)
        listener = MessageListener(topic=topic, device=device)
        listener.start()
        listeners.append(listener)
        return listener

    yield _create

    for listener in listeners:
        listener.stop()


def _device_topic(device: str) -> str:
    """与 api_device_a / api_device_b 一致的 topic：根据设备从 config 的 topics 读取。"""
    return get_topic(device)


@pytest.fixture(scope="session")
def listener_a(ws_debug):
    """
    设备 A 的纯接收监听器，与 api_device_a 共用同一 topic（config 中 topics.deviceA）。
    - 发送请求-等待响应：使用 api_device_a.call(...)。
    - 主动获取推送消息：使用本 listener 的 .receive_message(...)。
    """
    topic = _device_topic("deviceA")
    listener = MessageListener(topic=topic, device="deviceA", debug=ws_debug)
    listener.start()
    yield listener
    listener.stop()


@pytest.fixture(scope="session")
def listener_b(ws_debug):
    """
    设备 B 的纯接收监听器，与 api_device_b 共用同一 topic（config 中 topics.deviceB）。
    - 发送请求-等待响应：使用 api_device_b.call(...)。
    - 主动获取推送消息：使用本 listener 的 .receive_message(...)。
    """
    topic = _device_topic("deviceB")
    listener = MessageListener(topic=topic, device="deviceB", debug=ws_debug)
    listener.start()
    yield listener
    listener.stop()


class _DeviceChannelWrapper:
    """
    对 DeviceConnection 的封装：同一连接上发请求-等响应 + 收推送，并挂 Allure。
    保证 A 的 addContact 与 onFriendRequestAccepted 走同一条连接，能收到回调。
    """

    def __init__(self, conn: DeviceConnection, device: str):
        self._conn = conn
        self._device = device
        self.topic = conn.topic

    def call(self, manager: str, cmd: str, info: dict | None = None, **kwargs):
        req = {"manager": manager, "cmd": cmd, "info": info or {}, "device": self._device, **kwargs}
        resp = self._conn.call(manager, cmd, info, **kwargs)
        _attach_request_response_allure(
            f"API 请求 {manager}.{cmd} (device={self._device})",
            req,
            resp,
        )
        return resp

    def receive_message(self, *, match_cmd=None, match_event_type=None, timeout=10.0):
        return self._conn.receive_message(
            match_cmd=match_cmd,
            match_event_type=match_event_type,
            timeout=timeout,
        )

    def drain_events(self, timeout: float = 2.0) -> None:
        self._conn.drain_events(timeout=timeout)


@pytest.fixture(scope="session")
def device_a(ws_debug):
    """
    设备 A 的单连接双工通道：同一 WebSocket 上 .call() 发请求、.receive_message() 收推送。
    登录、addContact、onFriendRequestAccepted 等均走该连接，保证能收到服务端回调。
    """
    conn = DeviceConnection(device="deviceA")
    conn.start()
    try:
        yield _DeviceChannelWrapper(conn, "deviceA")
    finally:
        conn.stop()


@pytest.fixture(scope="session")
def device_b(ws_debug):
    """
    设备 B 的单连接双工通道：同一 WebSocket 上 .call() 发请求、.receive_message() 收推送。
    """
    conn = DeviceConnection(device="deviceB")
    conn.start()
    try:
        yield _DeviceChannelWrapper(conn, "deviceB")
    finally:
        conn.stop()


@pytest.fixture
def assert_api():
    """提供断言方法的 fixture：assert_api.assert_success(resp), assert_api.get_result(resp) 等。"""
    return assertions


def pytest_configure(config):
    """注册自定义 marker；报告见 README（pytest-html / allure）。"""
    config.addinivalue_line("markers", "client: Client manager API tests")
    config.addinivalue_line("markers", "chat: ChatManager API tests")
    config.addinivalue_line("markers", "group: GroupManager / group API tests")
    config.addinivalue_line("markers", "contact: ContactManager / friend API tests")
    config.addinivalue_line("markers", "presence: PresenceManager / online status tests")
    config.addinivalue_line("markers", "multi_device: tests requiring multiple devices/topics")
