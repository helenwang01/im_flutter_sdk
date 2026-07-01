# 环信 im flutter sdk 开发与测试指南

本仓库是 Flutter SDK 联合插件工程，包含 Flutter 主插件、Android/iOS 原生实现以及 API 自动化测试工程。

## 目录说明

- `im_flutter_sdk/`：Flutter 主插件与 example 工程。
- `im_flutter_sdk_android/`：Android 平台实现。
- `im_flutter_sdk_ios/`：iOS 平台实现。
- `im_flutter_sdk_interface/`：平台接口层。
- `native-auto-test/`：WebSocket 驱动的 native 自动化测试 cases。
- `docs/specs/`：依赖切换、API 适配、升级流程规范。
- `docs/skills/speckit.md`：构建检查脚本说明。

## 启动 Flutter Android

前置条件：

- 已安装 Flutter、Android Studio、Android SDK。
- 有可用 Android 模拟器或真机。
- 已按当前依赖形态配置好 Android 本地或远程依赖。

常用命令：

```bash
cd im_flutter_sdk/example
flutter pub get
flutter devices
flutter run -d <android-device-id>
```

只编译 Android example：

```bash
cd im_flutter_sdk
./scripts/speckit.sh android
```

等价底层命令：

```bash
cd im_flutter_sdk/example/android
./gradlew assembleDebug
```

## 启动 Flutter iOS

前置条件：

- 已安装 Xcode、CocoaPods、Flutter iOS 环境。
- 有可用 iOS Simulator 或真机。
- 已按当前依赖形态配置好 iOS 本地或远程依赖。

首次或依赖变更后先安装 Pods：

```bash
cd im_flutter_sdk/example
flutter pub get
cd ios
LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 pod install
```

启动 iOS example：

```bash
cd im_flutter_sdk/example
flutter devices
flutter run -d <ios-device-id>
```

只编译 iOS 模拟器：

```bash
cd im_flutter_sdk
./scripts/speckit.sh ios-build
```

等价底层命令：

```bash
cd im_flutter_sdk/example/ios
LANG=en_US.UTF-8 LC_ALL=en_US.UTF-8 xcodebuild \
  -workspace Runner.xcworkspace \
  -scheme Runner \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  build
```

## 本地更新依赖后重新编译

依赖切换不使用 `IM_USE_LOCAL_DEPS` 等开关，统一通过手动编辑构建文件完成。详细规范见 `docs/specs/dependency-spec.md`。

### Android 本地依赖

本地依赖目录：

```text
im_flutter_sdk_android/android/libs/easemob-sdk/
```

要求：

- 目录名固定为 `easemob-sdk`，不要带版本号。
- `so` 和 `hyphenatechat_<version>.jar` 放在 `libs/` 下。
- `im_flutter_sdk_android/android/build.gradle` 只启用一种依赖：本地 `implementation files(...)` 或远程 `implementation 'io.hyphenate:hyphenate-chat:...'`。

重新编译：

```bash
cd im_flutter_sdk
./scripts/speckit.sh check
./scripts/speckit.sh android
```

### iOS 本地依赖

本地依赖目录：

```text
im_flutter_sdk_ios/ios/HyphenateChat.xcframework
im_flutter_sdk_ios/ios/ShengwangInfra_iOS/aosl.xcframework
```

要求：

- `im_flutter_sdk_ios/ios/im_flutter_sdk_ios.podspec` 只启用一种依赖：本地 `s.vendored_frameworks` 或远程 `s.dependency ...`。
- 切换本地 framework 后必须重新执行 `pod install`。

重新编译：

```bash
cd im_flutter_sdk
./scripts/speckit.sh check
./scripts/speckit.sh ios
./scripts/speckit.sh ios-build
```

### 一次性检查 Android + iOS

```bash
cd im_flutter_sdk
./scripts/speckit.sh check
./scripts/speckit.sh build-all
```

`speckit.sh build-all` 会依次执行 Android build、iOS pod install、iOS simulator build。

## 补充 native-auto-test cases

自动化测试工程在 `native-auto-test/`，通过 WebSocket 连接 Flutter example 端执行 SDK API。

### 配置测试环境

确认 `native-auto-test/config.yaml`：

```yaml
websocket:
  base_url: "ws://<server>/iov/websocket/dual"
  default_topic: "adc"

topics:
  deviceA: adc
  deviceB: adc01
```

Flutter example 端需要打开 WebSocket bridge，并使用与 `config.yaml` 一致的 topic/device。

### 新增 case 位置

按模块放到对应目录：

- `native-auto-test/tests/chat/`：消息发送、接收、附件、合并转发、下载等。
- `native-auto-test/tests/chatroom/`：聊天室生命周期、成员、管理、回调等。
- `native-auto-test/tests/group/`：群组生命周期、成员、权限、成员信息等。
- `native-auto-test/tests/client/`：Client 初始化、登录、登出等。

同步更新记录文档：

- `native-auto-test/docs/agents/chat/CASES_RECORD.zh.md`
- `native-auto-test/docs/agents/chatroom/CASES_RECORD.zh.md`
- `native-auto-test/docs/agents/group/CASES_RECORD.zh.md`
- 其他模块同理。

### 推荐新增流程

1. 先写最小 case，复用已有 helper。
2. 未确认现网返回时先 discovery：

```bash
cd native-auto-test
CASES_DISCOVER=1 WS_DEBUG=1 pytest -q tests/<module>/<file>.py::<case_name> -s
```

3. 根据 discovery 输出冻结严格断言。
4. 严格执行：

```bash
cd native-auto-test
CASES_DISCOVER=0 WS_DEBUG=0 pytest -q tests/<module>/<file>.py::<case_name> -s
```

5. 语法与收集检查：

```bash
python3 -m py_compile tests/<module>/<file>.py
pytest --collect-only -q tests/<module>/<file>.py
```

### 常用执行命令

执行单个 case：

```bash
cd native-auto-test
pytest -q tests/chat/test_chat_s423_message_callback_and_combine.py::test_send_text_message_with_webhook_env -s
```

执行某个文件：

```bash
cd native-auto-test
pytest -q tests/chatroom/test_chatroom_management_basics.py -s
```

执行某个模块标记：

```bash
cd native-auto-test
pytest -q -m chatroom -s
```

生成 Allure 结果：

```bash
cd native-auto-test
pytest -q tests -s --alluredir=out/allure-results
allure generate out/allure-results -o out/allure-report --clean
open out/allure-report/index.html
```

## 提交前建议检查

```bash
cd im_flutter_sdk
./scripts/speckit.sh check
./scripts/speckit.sh android
./scripts/speckit.sh ios
./scripts/speckit.sh ios-build

cd ../native-auto-test
pytest --collect-only -q tests
```

如果只改了测试 cases，可至少执行：

```bash
cd native-auto-test
python3 -m py_compile tests/<module>/<file>.py
pytest --collect-only -q tests/<module>/<file>.py
pytest -q tests/<module>/<file>.py::<case_name> -s
```

## 相关规范

- 依赖切换：`docs/specs/dependency-spec.md`
- API 适配：`docs/specs/api-adaptation-spec.md`
- 升级流程：`docs/specs/upgrade-flow.md`
- speckit：`docs/skills/speckit.md`
- native cases 规范：`native-auto-test/docs/spec/CASES_SPEC.md`
